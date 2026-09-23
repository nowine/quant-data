# quant-data 修复与结构优化 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 修复前任 agent 遗留的环境硬编码、测试隔离缺陷和重复代码，使 quant-data 在任意机器上 `pytest` 全绿、可通过 GitHub PR 协作开发。

**Architecture:** 自底向上修复——先修测试基础设施（pytest.ini / 依赖），再修配置路径硬编码（DATA_DIR / CONFIG_PATH 环境变量化），然后修测试隔离缺陷（reload+patch 失配、HOME 泄漏），最后提取公共模块去重。每个任务独立提交，全程以测试通过为验收标准。

**Tech Stack:** Python 3.11, pytest 8, pandas, akshare, ruff（已在 requirements）。

**关键约定：**
- 测试运行命令统一为（在 repo 根目录）：
  ```bash
  cd ~/projects/quant-data && mv 'PRD_数据采集系统.md' /tmp/PRD_broken_symlink && QUANT_DATA_DIR=/tmp/quant-data-test PYTHONPATH=. .venv/bin/python -m pytest tests/ -q -p no:cacheprovider; mv /tmp/PRD_broken_symlink 'PRD_数据采集系统.md'
  ```
  （`PRD_数据采集系统.md` 是指向不存在路径的坏符号链接，会阻断 pytest 根目录扫描；Task 0 修好 pytest.ini 后不再需要移动。）
- 工作分支：`fix/cleanup-baseline`，从 develop 切出，完成后 PR 到 main。
- 每个任务一个 commit，格式 `fix(scope): ...` / `refactor(scope): ...`。
- 验收基线：修复前 302 passed / 17 failed / 3 skipped；目标 **全绿（0 failed）**，最终在无 `QUANT_DATA_DIR` 时也能全绿。

---

## Task 0: pytest.ini + 依赖修复（测试基础设施）

**Objective:** 建立 pytest 配置，绕开坏符号链接收集错误，补齐缺失依赖。

**Files:**
- Create: `pytest.ini`
- Modify: `requirements.txt`
- Modify: `.gitignore`（追加 `~/.cache/quant-data/` 相关条目不适用——那是 HOME 下的；追加 `.venv/`）

**Step 1: 创建 pytest.ini**

```ini
[pytest]
testpaths = tests
norecursedirs = .venv .git docs examples scripts
addopts = -p no:cacheprovider
```

关键点：`testpaths = tests` 让 pytest 不再扫描仓库根目录，坏符号链接 `PRD_数据采集系统.md` 不再触发 PermissionError。

**Step 2: requirements.txt 追加 pyyaml**（test_docker.py `import yaml`，当前缺失）

```
pyyaml>=6.0
```

**Step 3: 验证**

Run: `cd ~/projects/quant-data && .venv/bin/pip install -q pyyaml && .venv/bin/python -m pytest tests/ -q`
Expected: 正常收集，不再有 `PermissionError: PRD_数据采集系统.md`；无需移动符号链接、无需 PYTHONPATH 手动注入。

**Step 4: 若 `ModuleNotFoundError: No module named 'src'` 仍出现，在 pytest.ini 加**

```ini
pythonpath = .
```

**Step 5: Commit**

```bash
git add pytest.ini requirements.txt .gitignore
git commit -m "fix(test-infra): add pytest.ini (skip broken symlink) + pyyaml dep"
```

---

## Task 1: 工作分支

**Objective:** 从 develop 切出修复分支。

```bash
cd ~/projects/quant-data
git checkout develop && git pull origin develop
git checkout -b fix/cleanup-baseline
```

**验证:** `git branch --show-current` → `fix/cleanup-baseline`

---

## Task 2: DATA_DIR 默认值去硬编码

**Objective:** 消灭 `/root/secureshare/...` 硬编码默认路径，改为"必须显式提供"的 fail-fast 语义 + 项目内安全默认。

**Files:**
- Modify: `src/config.py:164-180`（DATA_DIR 解析块）
- Modify: `tests/test_config.py`（`test_data_dir_contains_project_name` 改为验证新语义）
- Modify: `tests/test_data_dir_env.py:31`（`_HOST_DEFAULT` 常量同步更新）

**Step 1: 改 src/config.py**

```python
# DATA_DIR 解析：
#   1. env QUANT_DATA_DIR（容器内由 compose 设置）
#   2. 默认：<repo>/data （相对仓库根，不再依赖任何机器的绝对路径）
_DATA_DIR_DEFAULT = str(Path(__file__).resolve().parent.parent / "data")
DATA_DIR = os.getenv("QUANT_DATA_DIR") or _DATA_DIR_DEFAULT
```

顶部补 `from pathlib import Path`。容器行为不变（compose 仍设 `QUANT_DATA_DIR=/data/data`）。

**Step 2: 更新 tests/test_config.py**

```python
def test_data_dir_default_is_repo_relative(self):
    """默认 DATA_DIR 指向仓库内 data/，而非硬编码主机路径。"""
    from src.config import DATA_DIR
    assert not DATA_DIR.startswith("/root/")
    assert DATA_DIR.endswith("data")
```

**Step 3: 更新 tests/test_data_dir_env.py** 中 `_HOST_DEFAULT` 为新默认值，保持其余断言逻辑。

**Step 4: 验证**

Run: `QUANT_DATA_DIR=/tmp/quant-data-test .venv/bin/python -m pytest tests/test_config.py tests/test_data_dir_env.py -q`
Expected: PASS（test_data_dir_contains_project_name 的断言已换新语义）

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py tests/test_data_dir_env.py
git commit -m "fix(config): replace hardcoded /root data dir with repo-relative default"
```

---

## Task 3: 测试内 /root 硬编码路径修复

**Objective:** `test_collector_no_date_gate.py` 三处 `/root/secureshare/.../config/etf_config.json` 改为 tmp_path 生成的临时 config。

**Files:**
- Modify: `tests/test_collector_no_date_gate.py`（3 处，行 63/99/131 附近）

**Step 1:** 该测试类已有 `_reload(monkeypatch, tmp_path)` fixture。在每个 subprocess 调用前用 tmp_path 生成最小合法 config：

```python
config_file = tmp_path / "etf_config.json"
config_file.write_text(json.dumps({
    "etf_watch_list": [], "user_holdings": [],
    "index_watch_list": [], "sector_mapping": {}
}), encoding="utf-8")
# subprocess 参数改为: "--config", str(config_file)
```

注意：collector 是子进程执行，需传 `env={**os.environ, "QUANT_DATA_DIR": str(tmp_path / "data")}`，否则子进程仍会落到默认 data 目录。

**Step 2: 验证**

Run: `QUANT_DATA_DIR=/tmp/quant-data-test .venv/bin/python -m pytest tests/test_collector_no_date_gate.py -q`
Expected: 4 passed（当前 3 failed 1 passed）

**Step 3: Commit**

```bash
git add tests/test_collector_no_date_gate.py
git commit -m "fix(tests): replace /root hardcoded config path with tmp_path fixture"
```

---

## Task 4: reload+patch 失配修复（测试隔离核心缺陷）

**Objective:** 修复 `test_extra_holdings_integration.py` 的顺序依赖——`patch("src.collector_daily.X")` 字符串寻址落在 reload 后的新模块，而被测引用是旧模块，导致真实网络调用。

**Files:**
- Modify: `tests/test_extra_holdings_integration.py`（3 处字符串 patch → monkeypatch 对象寻址）

**Step 1: 替换 patch 方式**

```python
# Before:
with patch("src.collector_daily.build_extra_holdings_set", return_value=...):
    result = cd._resolve_extra_holdings(...)

# After:
monkeypatch.setattr(cd, "build_extra_holdings_set", lambda codes: _akshare_enrichment(codes))
result = cd._resolve_extra_holdings(...)
```

对 `TestResolveExtraHoldings`（3 处）和所有 `patch("src.collector_daily._resolve_extra_holdings")` 调用点统一替换为 `monkeypatch.setattr(cd, ...)`。

**Step 2: 网络封锁复验（关键验证）**

Run:
```bash
rm -f ~/.cache/quant-data/fund_name.csv
HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
  QUANT_DATA_DIR=/tmp/quant-data-test PYTHONPATH=. \
  .venv/bin/python -m pytest tests/ --ignore=tests/test_entrypoint_routing.py --ignore=tests/test_collector_no_date_gate.py -q
```
Expected: integration 测试全过；`~/.cache/quant-data/` 保持为空（证明无真实网络调用泄漏）。

**Step 3: Commit**

```bash
git add tests/test_extra_holdings_integration.py
git commit -m "fix(tests): patch via module object to survive importlib.reload in other tests"
```

---

## Task 5: cwd 依赖测试修复

**Objective:** `test_requirements.py` 用相对路径访问 requirements.txt，改为基于测试文件位置的绝对路径。

**Files:**
- Modify: `tests/test_requirements.py`

**Step 1:**

```python
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
REQ = REPO_ROOT / "requirements.txt"

def test_requirements_file_exists():
    assert REQ.exists(), "requirements.txt not found"
```

（同理修 `test_entrypoint_routing.py` 中任何相对路径假设——该文件 subprocess bash 调用依赖容器内 python3，改为：子进程 env 注入 `.venv/bin/python3` PATH 前置，或在无 pandas 环境显式 skip：`pytest.mark.skipif(shutil.which("python3") ...)`。**推荐前者**：entrypoint.sh 用 `python3`，测试里构造 `env["PATH"] = str(REPO_ROOT / ".venv" / "bin") + ":" + env["PATH"]`。）

**Step 2: 验证**

Run: `QUANT_DATA_DIR=/tmp/quant-data-test PYTHONPATH=. .venv/bin/python -m pytest tests/test_requirements.py tests/test_entrypoint_routing.py -q`
Expected: 全部通过（entrypoint 子进程能 import pandas）

**Step 3: Commit**

```bash
git add tests/test_requirements.py tests/test_entrypoint_routing.py
git commit -m "fix(tests): resolve repo paths from __file__; venv python for entrypoint subprocess"
```

---

## Task 6: ruff 自动修复 + 手工收尾

**Objective:** 清掉 239 个 lint 问题（168 个可自动修复），手工处理 F811 重定义。

**Files:**
- Modify: 多个 src/ tests/ 文件（机械修复）
- Create: `ruff.toml`（固化规则，关闭与项目风格冲突的规则）

**Step 1: 建 ruff.toml**

```toml
line-length = 100
[lint]
select = ["E", "F", "I", "W", "UP", "B"]
ignore = ["BLE001"]  # blind-except 是本项目有意的 best-effort 语义（ADR-003）
```

**Step 2: 自动修复**

```bash
.venv/bin/python -m ruff check src/ tests/ --fix
```

**Step 3: 手工修 F811**：`src/collector_daily.py:304` 删除函数内冗余的 `from src.tech_indicator import calc_premium_rate`（顶部已导入）。

**Step 4: 验证**

```bash
.venv/bin/python -m ruff check src/ tests/   # 0 errors
.venv/bin/python -m pytest tests/ -q          # 无回归
```

**Step 5: Commit**

```bash
git add -A
git commit -m "style: ruff autofix imports/unused + dedupe F811; add ruff.toml"
```

---

## Task 7: 提取 collectors/common.py 去重

**Objective:** 4 个 collector 中复制粘贴的 `_record_error`（4 份）与 `_classify_exception`（4 份）提取到 `src/collectors_common.py`。

**Files:**
- Create: `src/collectors_common.py`
- Modify: `src/collector_daily.py`, `src/collector_weekly.py`, `src/collector_monthly.py`, `src/collector_quarterly.py`

**Step 1: 先写失败测试** `tests/test_collectors_common.py`：断言 4 个模块的 `_record_error is collectors_common.record_error`（别名导入保证现有测试兼容）。

**Step 2: 提取实现**——把 `collector_daily.py` 的版本移入 `src/collectors_common.py`（`record_error`, `classify_exception`），4 个 collector 顶部改为：

```python
from src.collectors_common import record_error as _record_error, classify_exception as _classify_exception
```

（保留原名，调用点零改动，现有 461 行 collector_daily 测试是安全网。）

**Step 3: 验证**

Run: `QUANT_DATA_DIR=/tmp/quant-data-test PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 全绿，总行数净减 ~150+。

**Step 4: Commit**

```bash
git add src/collectors_common.py src/collector_*.py tests/test_collectors_common.py
git commit -m "refactor(collectors): extract shared _record_error/_classify_exception to collectors_common"
```

---

## Task 8: 文档合并与 README 修正

**Objective:** 消除双"宪法"，README 结构描述对齐现实。

**Files:**
- Modify: `Constitution.md`（保留为唯一宪法，吸收 CONstitution.md 的容器化章节 10）
- Delete: `CONstitution.md`
- Modify: `README.md`（删除 ttfund_client 引用、修正 `cd /root/.openclaw/...` 示例路径为相对路径、补充 `QUANT_DATA_DIR` 说明）

**Step 1:** diff 两份宪法，将 CONstitution.md 独有章节并入 Constitution.md，保留其"版本：0.2-upgrade"头部。
**Step 2:** README 修正如上三点。
**Step 3: 验证** — `grep -rn "ttfund_client\|/root/" README.md Constitution.md` → 0 命中（历史 ADR 文档中的引用保留，它们是历史记录）。
**Step 4: Commit**

```bash
git add -A
git commit -m "docs: merge duplicate constitutions, fix stale README references"
```

---

## Task 9: 全量验收 + PR

**Objective:** 最终验证并走 PR 流程（首次真正用上 main 分支）。

**Step 1: 全量测试（无特殊环境变量，模拟新机器）**

```bash
cd ~/projects/quant-data && .venv/bin/python -m pytest tests/ -q
```
Expected: 0 failed（允许与 network 相关的 skip）

**Step 2: 网络封锁复验**（同 Task 4 Step 2，确认无网络泄漏、缓存目录为空）

**Step 3: 推送 + PR**

```bash
git push -u origin fix/cleanup-baseline
gh pr create --base main --title "fix: environment hardcoding, test isolation, code dedup" --body-file - <<'EOF'
- repo-relative DATA_DIR default (was /root/secureshare hardcoded)
- pytest.ini: skip broken symlink, pythonpath=.
- test isolation: module-object patching survives importlib.reload
- tmp_path configs replace /root hardcoded test paths
- collectors_common.py: dedupe _record_error/_classify_exception (4x)
- ruff clean (239 -> 0), pyyaml added to requirements
- docs: single Constitution, README updated
EOF
```

**验证:** PR 在 GitHub 上可打开、diff 完整、CI（若有）通过。

---

## Risks & Notes

1. **容器兼容性**：Task 2 改默认值不影响容器（compose 显式设 `QUANT_DATA_DIR=/data/data`）；但若用户的 cron 直接在宿主机跑而未设该变量，数据会落到 `<repo>/data`——需在 DEPLOY.md 提一句（并入 Task 8）。
2. **reload 型测试的脆弱性**：Task 4 只修 integration 文件的 patch 方式；`_reload()` 模式本身仍是隐患，但重写它超出本次范围（记录到 docs/phase-2-followup.md）。
3. **entrypoint 测试**：venv PATH 注入方案在无 `.venv` 的 CI 上会失败——Task 5 需加 `has_venv = (REPO_ROOT/".venv").exists()` 守卫，否则 skip。
4. **坏符号链接** `PRD_数据采集系统.md` 建议后续从 git 移除或指向真实文件（用户决定），本次不动它。
