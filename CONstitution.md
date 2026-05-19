# Constitution — ETF 数据采集系统

> 项目级基础约定，所有开发必须遵守
> 最后更新：2026-05-20
> 版本：0.2（新增容器化章节 10）

---

## 0. 前置声明

本文档是项目的「宪法」，优先级高于 PRD、低于实际代码运行时遇到的物理限制。
如遇冲突，先记录问题，再沟通确认，不允许明知冲突还硬做。

---

## 1. 质量铁律（强制执行）

### 1.1 TDD（测试驱动开发）

**每一条铁律中的规则都附带检查方法，不是「感觉做到了」而是「有证据」。**

| 规则 | 检查方法 |
|------|---------|
| 公共模块必须有单元测试 | 测试文件 `tests/test_*.py` 存在且通过 `pytest` |
| 每个函数先写测试再写实现 | git log 中测试 commit 先于功能 commit |
| 异常路径必须测 | 降级逻辑、缓存过期、接口超时必须有对应的 `test_*_error`、`test_*_fallback` |

### 1.2 依赖安全

| 规则 | 检查方法 |
|------|---------|
|不允许未修复的高危 CVE（CVSS ≥ 7.0）通过|`pip audit` 无 HIGH/CRITICAL 告警|
| 新增依赖必须经过 `pip audit` + `pip review` | 手动执行并记录结果 |
| 最小依赖集 | 只用 `akshare`、`pandas`、`requests` 三个数据依赖 |

### 1.3 类型安全

| 规则 | 检查方法 |
|------|---------|
| 所有函数必须有 type hint | `mypy --strict` 无错误（阶段一只检查公共接口） |
| 公共接口输入输出用 pydantic model 校验 | `Model.validate()` 测试存在且通过 |

### 1.4 日志即文档

| 规则 | 检查方法 |
|------|---------|
| 每条日志带 `task/version/source/status` | `log_collect()` 调用包含所有字段 |
| 异常日志必须带 `trace_id`（本次运行的唯一 ID） | 测试验证日志包含 `run_id` |

---

## 2. 架构铁律

### 2.1 配置外置

- 所有配置（ETF 列表、API 地址、阈值、路径）必须放在 `config.py`
- **禁止硬编码**：不允许在任何模块中直接写死配置值
- 环境变量用于敏感信息（APIKEY 等），通过 `os.environ` 读取

### 2.2 单一职责

每个模块只做一件事，模块间通过标准化接口通信：

| 模块 | 职责边界 |
|------|---------|
| `config.py` | 只提供配置，不做业务逻辑 |
| `akshare_client.py` | 只封装 AkShare 调用，不做数据处理 |
| `ttfund_client.py` | 只封装天天基金 API，不做数据处理 |
| `validator.py` | 只校验数据质量，不读写文件 |
| `storage.py` | 只负责文件读写，不做数据采集 |
| `logger.py` | 只负责日志记录和告警，不做其他 |

### 2.3 接口冻结（一期）

一期定稿后，以下接口签名**不修改**（如有变更需走需求变更流程）：

```python
# akshare_client.py
get_etf_snapshot() -> DataFrame
get_north_flow(symbol: str, months: int) -> DataFrame
get_etf_history(code: str) -> DataFrame

# ttfund_client.py
get_nav_history(fund_id: str, range: str) -> DataFrame
get_index_info(index_id: str, scope: str) -> dict

# storage.py
save_csv(df: DataFrame, filepath: str) -> None
load_csv(filepath: str) -> DataFrame
exists_today(filepath: str) -> bool
```

### 2.4 本地优先

- 不引入 Redis、MySQL、PostgreSQL 等额外服务
- 缓存用文件系统（CSV/JSON）
- 未来如需数据库，必须走架构评审

---

## 3. 数据铁律

### 3.1 时序完整性

| 规则 | 说明 |
|------|------|
| 文件名含日期 | `{data_type}_{YYYYMMDD}.csv` |
| 内部日期格式 | 统一使用 `YYYY-MM-DD`，不用时间戳 |
| 原始数据不修改 | 采集的原始数据只追加不覆盖 |

### 3.2 Schema 校验

- 数据写入前用 pydantic model 校验字段类型和范围
- 校验失败写入 `data/validate_failed/{date}.csv`，不影响原始数据

### 3.3 缓存 TTL 精确

| 数据类型 | TTL |
|---------|-----|
| 当日数据（ETF行情等） | 当日有效，隔日失效 |
| 日频宏观（融资融券等） | 1-7 天 |
| 月频宏观（CPI/PPI/PMI等） | 30-90 天 |
| 季频/年频（行业配置等） | 90-360 天 |

### 3.4 CSV 格式规范

| 规则 | 说明 |
|------|------|
| UTF-8 编码 | 无 BOM |
| 首行是列名 | 无额外元数据行 |
| 空值留空 | 不用 `N/A`、`null` 等占位符 |
| 数值不加千分位 | `1234567.89` 而非 `1,234,567.89` |

---

## 4. 运维铁律

### 4.1 幂等性

- 同一任务重复运行，结果一致
- `partial rerun` 模式下，已成功的文件不重复请求 API
- 日志文件使用追加模式

### 4.2 慢接口隔离

| 规则 | 说明 |
|------|------|
| >20 秒的接口单独处理 | 不阻塞其他数据采集 |
| 慢接口强制缓存 | 即使未过期也写缓存，避免重复超时 |

### 4.3 失败分级

| 级别 | 定义 | 处理 |
|------|------|------|
| `cache_hit` | 今日数据已存在 | 跳过，写入 cache_hit 日志 |
| `success` | 接口成功，数据有效 | 保存，写入 success 日志 |
| `fallback` | 首选源失败，备选源成功 | 保存，写入 fallback 日志，告警 warn |
| `failed` | 所有源失败 | 标记缺失，告警 error，继续其他任务 |
| `degraded` | 数据校验失败但保存了 | 单独标记，告警 warn，继续 |

### 4.4 可追溯

- 每次采集记录来源（akshare/ttfund）、耗时、状态
- 异常数据可追溯到具体接口调用
- 使用 `run_id`（时间戳+随机字符串）串联同一次运行的所有日志

---

## 5. 安全铁律

### 5.1 密钥管理

| 规则 | 说明 |
|------|------|
| APIKEY 不写在配置文件 | 通过环境变量注入 |
| 日志不记录 API 响应原文 | 只记录字段名和状态，不记录具体数值 |

### 5.2 日志脱敏

日志中禁止出现：
- API 请求/响应原文
- 具体交易数据、持仓数据
- 异常堆栈中可能包含的敏感路径

---

## 6. 变更管理

### 6.1 Constitution 修改流程

1. 提出变更申请，说明理由
2. 项目owner（哈总/皮皮/九节任一）评审
3. 通过后更新本文档，commit message 标注 `[constitution]`
4. 通知所有开发者

### 6.2 PRD 修改流程

1. 提出变更申请，说明理由和影响范围
2. 确认是否影响 Constitution
3. 通过后更新 PRD，commit message 标注 `[prd]`
4. 如影响 Constitution，一并更新

### 6.3 需求冻结

一期（数据采集）开发阶段，以下内容冻结：
- `config.py` 中的 ETF/指数列表
- 四个采集脚本的接口列表
- CSV 文件的列名和格式

如有变更，走需求变更流程。

---

## 7. 开发流程

### 7.1 TDD 循环

```
每开发一个函数：
1. 写失败的测试（red）
2. 写最小实现通过测试（green）
3. 重构（refactor）
4. commit
```

### 7.2 开发顺序

```
Phase 1: 公共模块（按依赖顺序）
  config.py → logger.py → storage.py → validator.py → akshare_client.py → ttfund_client.py

Phase 2: 采集脚本
  collector_daily.py → collector_weekly.py → collector_monthly.py → collector_quarterly.py

Phase 3: 集成测试 + Cron 配置
```

### 7.3 Commit 规范

```
feat: 新功能
fix: Bug 修复
test: 测试相关
refactor: 重构
docs: 文档更新
chore: 构建/工具/配置
```

每个 commit 必须附上关联的任务编号（如有）。

### 7.4 分支模型

```bash
# 主分支
main          - 生产就绪代码
develop       - 开发集成分支

# 功能分支
feature/TASK-XXX-<简短描述>   # 功能开发
bugfix/TASK-XXX-<简短描述>    # Bug 修复
hotfix/<描述>                 # 紧急修复

# 创建分支
git checkout -b feature/TASK-001-collector-daily develop

# 完成任务后合并回 develop
git checkout develop
git merge --no-ff feature/TASK-001-collector-daily
git branch -d feature/TASK-001-collector-daily
git push origin develop
```

---

## 8. 检查清单

每次 commit 前检查：

- [ ] `pytest` 全部通过
- [ ] `mypy --strict` 无错误（公共接口）
- [ ] `pip audit` 无 HIGH/CRITICAL
- [ ] 日志格式符合 Constitution 规范
- [ ] 无硬编码配置
- [ ] commit message 符合规范

---

## 9. 参考文档

- [Constitution原文](./CONstitution.md)（本文件）
- [PRD](./PRD_数据采集系统.md)
- [验证结果_T1_akshare宏观](../../../../secureshare/files/ETF轮动分析框架/验证结果_T1_akshare宏观.md)
- [验证结果_T2_akshare市场](../../../../secureshare/files/ETF轮动分析框架/验证结果_T2_akshare市场.md)
- [验证结果_T3_天天基金API](../../../../secureshare/files/ETF轮动分析框架/验证结果_T3_天天基金API.md)

---

## 10. 容器化（强制）

> 所有交付服务必须容器化，这是交付标准的一部分。

### 10.1 交付检查清单

一个可部署的服务必须包含：

| 检查项 | 说明 |
|--------|------|
| `Dockerfile` | 多阶段构建，builder + runner 两阶段 |
| `.dockerignore` | 排除不必要文件（`__pycache__`、`.git`、`.env` 等）|
| `docker-compose.yml` | 开发环境完整（包含 PostgreSQL 等依赖服务）|
| 健康检查端点 | `GET /health` 返回 200 + service status |
| 非 root 用户运行 | 容器内不使用 root |
| 镜像大小优化 | 最终镜像 < 500MB |

### 10.2 Dockerfile 要求

```dockerfile
# 阶段 1: builder
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir --prefix=/install requirements.txt

# 阶段 2: runner
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY . /app
WORKDIR /app
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
CMD ["python", "collector_daily.py"]
```

### 10.3 docker-compose.yml 要求

必须包含：
- `app` 服务（主应用）
- 日志目录挂载（`./data/logs:/app/data/logs`）
- 环境变量注入（APIKEY 等）
- 健康检查

### 10.4 健康检查端点


所有 `collector_*.py` 必须支持 `--health` 参数：

```python
def health_check():
    """返回服务健康状态"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "last_run": get_last_run_timestamp(),
        "data_freshness": check_data_freshness()
    }
```

### 10.5 镜像构建验证

每次 `main` 分支更新后必须验证：

```bash
# 本地构建
podman build -t quant-data:latest .

# 健康检查
podman run --rm quant-data:latest python collector_daily.py --health


# docker-compose 启动
podman-compose up -d
podman-compose ps
curl http://localhost:8080/health
```

### 10.6 Git Hooks（推荐）

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/ -q
ip audit -r requirements.txt || exit 1
```


---
_「做对的事情，把事情做对。」 — Constitution_