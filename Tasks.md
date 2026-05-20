# Tasks.md — ETF 数据采集系统

> Story → Task 拆分 | 基于 Plan.md v1.0-draft
> 版本：1.0 | 2026-05-21 | 已交付

---

## Task 依赖图

| TASK | Blocks | Blocked by |
|------|--------|------------|
| TASK-101 | TASK-102, TASK-103, TASK-104, TASK-105, TASK-106 | — |
| TASK-102 | TASK-103 | TASK-101 |
| TASK-103 | TASK-104 | TASK-102 |
| TASK-104 | TASK-105, TASK-106 | TASK-103 |
| TASK-105 | TASK-107 | TASK-104 |
| TASK-106 | TASK-107 | TASK-104 |
| TASK-107 | TASK-108 | TASK-105, TASK-106 |
| TASK-108 | TASK-109, TASK-110, TASK-111 | TASK-107 |
| TASK-109 | — | TASK-108 |
| TASK-110 | — | TASK-108 |
| TASK-111 | — | TASK-108 |
| TASK-112 | — | — |
| TASK-113 | — | TASK-112 |
| TASK-114 | — | TASK-113 |
| TASK-115 | — | — |
| TASK-116 | — | TASK-115 |
| TASK-117 | — | — |
| TASK-118 | — | — |
| TASK-119 | — | — |
| TASK-120 | — | — |
| TASK-121 | — | — |
| TASK-122 | — | — |
| TASK-123 | — | — |
| TASK-124 | — | — |
| TASK-125 | — | — |
| TASK-126 | — | — |
| TASK-127 | — | — |
| TASK-128 | — | — |
| TASK-129 | — | — |
| TASK-130 | — | — |
| TASK-131 | — | — |
| TASK-132 | — | — |
| TASK-133 | — | TASK-112 |
| TASK-134 | — | — |

**Deadlock Check:** 无循环依赖 ✅

---

## MVP-001: 公共基础模块

### Story-001: 配置中心 config.py
**Status:** `done` | **Story ID:** Story-001

---

## Task: TASK-101 — config.py 基础配置结构
**Status:** `done`
**Completed At:** 2026-05-20 15:08

**Story:** Story-001
**Status:** `done`
**Type:** `feat`
**Module:** `src/config.py`

### Functionality
创建 `config.py`，包含：
- `ETF_WATCH_LIST` — 22 只核心 ETF（code/name/index）
- `INDEX_WATCH_LIST` — 20 只指数名称列表
- `TTFUND_API_URL` — 天天基金 API 地址
- `TTFUND_APIKEY` — 从环境变量 `TTFUND_APIKEY` 读取
- `DATA_DIR` — `/root/secureshare/files/ETF轮动分析框架/data`
- `SLOW_API_TIMEOUT` — 默认 45 秒

### Boundaries
- 不做业务逻辑
- 不读写文件
- 不调用任何 API

### Dependencies
- 无依赖，独立完成

### Test Cases
```python
# tests/test_config.py
def test_etf_watch_list_not_empty():
    assert len(ETF_WATCH_LIST) >= 20
    assert all(k in e for e in ETF_WATCH_LIST for k in ['code', 'name', 'index'])

def test_index_watch_list_not_empty():
    assert len(INDEX_WATCH_LIST) >= 16

def test_ttfund_api_key_from_env(monkeypatch):
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")
    # re-import to pick up env var
    import importlib; importlib.reload(config)
    assert config.TTFUND_APIKEY == "test-key"

def test_data_dir_correct():
    assert "ETF轮动分析框架" in DATA_DIR
```

### Verification
- [ ] `pytest tests/test_config.py` — 通过
- [ ] `ruff check src/config.py` — 无错误
- [ ] commit: `feat(config): base config with ETF/INDEX lists and env var`

---

## Task: TASK-102 — CACHE_TTL 和 VALIDATION_RULES

**Story:** Story-001
**Status:** `done`
**Type:** `feat`
**Module:** `src/config.py`

### Functionality
在 `config.py` 中补充：
- `CACHE_TTL` — 各数据类型的缓存有效期（小时）
  - `etf_snapshot`: 24（当日）
  - `macro_north_flow`: 168（7天）
  - `etf_scale`: 168（7天）
  - `margin`: 24（1天）
  - `macro_pmi/cpi/ppi/m2/lpr/shrzgm/gdp/industrial`: 720（30天）
  - `macro_gdp`: 2160（90天）
  - 其他：按需定义
- `VALIDATION_RULES` — 各数据类型的校验规则（pydantic model 或 dict）
  - 范围校验：min/max
  - 非空字段列表

### Dependencies
- [ ] TASK-101（完成后解锁）

### Test Cases
```python
def test_cache_ttl_has_required_keys():
    assert 'etf_snapshot' in CACHE_TTL
    assert 'macro_pmi' in CACHE_TTL
    assert CACHE_TTL['etf_snapshot'] == 24

def test_validation_rules_has_required_keys():
    assert 'PMI' in VALIDATION_RULES
    assert 'PE_PERCENTILE' in VALIDATION_RULES
```

---

## Task: TASK-103 — requirements.txt 初始化

**Story:** Story-001
**Status:** `done`
**Type:** `config`
**Module:** `requirements.txt`

### Functionality
创建 `requirements.txt`，包含所有 Python 依赖：
```
akshare>=2.0.0
pandas>=2.0.0
requests>=2.31.0
pydantic>=2.0.0
pytest>=8.0.0
ruff>=0.4.0
```

### Dependencies
- [ ] TASK-101（完成后解锁）

### Verification
- [ ] `pip install -r requirements.txt` 成功
- [ ] `pip audit` 无告警
- [ ] commit: `chore(deps): add requirements.txt`

---

## Task: TASK-201 — logger.py 基础结构

**Story:** Story-002
**Status:** `done`
**Type:** `feat`
**Module:** `src/logger.py`

### Functionality
- 创建 `src/logger.py`
- `log_collect(task, source, status, rows, elapsed_sec, message)` — 写入 `data/logs/collect_{YYYYMMDD}.csv`
  - 字段：timestamp, task, source, status, rows, elapsed_sec, message, run_id
  - 追加模式
  - UTF-8 无 BOM
- `get_run_id()` — 生成时间戳+随机字符串作为 `run_id`
- 全局 `run_id` 在模块加载时生成，同一次运行共享

### Dependencies
- [ ] TASK-101（config DATA_DIR）
- [ ] TASK-103（requirements.txt 安装后）

### Test Cases
```python
def test_log_collect_writes_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    log_collect("test_task", "akshare", "success", 100, 1.5, "")
    log_file = tmp_path / "data/logs/collect_{date}.csv"
    assert log_file.exists()
    content = log_file.read_text()
    assert "test_task" in content
    assert "akshare" in content

def test_run_id_is_unique():
    rid1 = get_run_id()
    rid2 = get_run_id()
    assert rid1 != rid2
    assert len(rid1) > 20
```

---

## Task: TASK-204 — alert() 函数

**Story:** Story-002
**Status:** `done`
**Type:** `feat`
**Module:** `src/logger.py`

### Functionality
- `alert(level, message)` — 写入 `data/logs/alert_{YYYYMMDD}.csv`
  - level: `warn` / `error`
  - 字段：timestamp, level, message, run_id
  - 追加模式

### Dependencies
- [ ] TASK-201（logger 基础结构完成后解锁）

### Test Cases
```python
def test_alert_writes_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    alert("error", "API timeout")
    alert_file = tmp_path / "data/logs/alert_{date}.csv"
    assert alert_file.exists()
    content = alert_file.read_text()
    assert "error" in content
    assert "API timeout" in content
```

---

## Task: TASK-301 — storage.py save_csv / load_csv

**Story:** Story-003
**Status:** `done`
**Type:** `feat`
**Module:** `src/storage.py`

### Functionality
- `save_csv(df, filepath)` — DataFrame 保存为 CSV（UTF-8 无 BOM，首行列名）
- `load_csv(filepath)` — 读取 CSV 返回 DataFrame
- 目录不存在时自动创建
- `append=False` 时覆盖（用于数据文件）

### Dependencies
- [ ] TASK-201（logger 基础）
- [ ] TASK-103（requirements.txt）

### Test Cases
```python
def test_save_and_load_csv(tmp_path):
    df = pd.DataFrame({"date": ["2026-05-19"], "close": [100.5]})
    path = tmp_path / "test.csv"
    save_csv(df, str(path))
    loaded = load_csv(str(path))
    assert loaded["close"][0] == 100.5
    assert loaded.columns.tolist() == ["date", "close"]

def test_save_csv_no_bom(tmp_path):
    path = tmp_path / "test.csv"
    save_csv(pd.DataFrame({"a": [1]}), str(path))
    with open(path, "rb") as f:
        header = f.read(3)
    assert header != b'\\xef\\xbb\\xbf'  # no BOM
```

---

## Task: TASK-302 — storage.py save_json / load_json

**Story:** Story-003
**Status:** `done`
**Type:** `feat`
**Module:** `src/storage.py`

### Functionality
- `save_json(data, filepath)` — dict/list 保存为 JSON
- `load_json(filepath)` — 读取 JSON

### Dependencies
- [ ] TASK-301（save_csv/load_csv 完成后解锁）

### Test Cases
```python
def test_save_and_load_json(tmp_path):
    data = {"fund_id": "001", "nav": 1.234}
    path = tmp_path / "test.json"
    save_json(data, str(path))
    loaded = load_json(str(path))
    assert loaded["fund_id"] == "001"
```

---

## Task: TASK-303 — storage.py partial rerun 核心逻辑

**Story:** Story-003
**Status:** `done`
**Type:** `feat`
**Module:** `src/storage.py`

### Functionality
- `exists_today(filepath)` — 检查今日数据文件是否存在且有效（非空，日期匹配）
- `collect_if_missing(filepath, fetch_fn, *args, **kwargs)` — 核心 partial rerun 逻辑
  - 已存在今日有效文件 → 读缓存，写 cache_hit 日志，返回数据
  - 不存在 → 调用 fetch_fn()，保存，写 success 日志，返回数据

### Dependencies
- [ ] TASK-301（save_csv/load_csv）
- [ ] TASK-201（log_collect）

### Test Cases
```python
def test_exists_today_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert not exists_today(str(tmp_path / "nonexist.csv"))

def test_collect_if_missing_cache_hit(tmp_path, monkeypatch):
    # 当文件已存在时，fetch_fn 不应被调用
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    df = pd.DataFrame({"date": ["2026-05-20"], "value": [1]})
    save_csv(df, str(tmp_path / "test.csv"))
    fetch_called = False
    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"date": ["2026-05-20"], "value": [2]})
    result = collect_if_missing(str(tmp_path / "test.csv"), fake_fetch)
    assert not fetch_called
    assert result["value"][0] == 1  # 缓存值

def test_collect_if_missing_fetch_and_save(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    def fake_fetch():
        return pd.DataFrame({"date": ["2026-05-20"], "value": [99]})
    result = collect_if_missing(str(tmp_path / "new.csv"), fake_fetch)
    assert result["value"][0] == 99
```

---

## Task: TASK-401 — validator.py ValidationResult + 空值/范围校验

**Story:** Story-004
**Status:** `done`
**Type:** `feat`
**Module:** `src/validator.py`

### Functionality
- `class ValidationResult` — pydantic model
  - `passed: bool`
  - `warnings: list[str]`
  - `errors: list[str]`
- `validate(df, rules)` — 五类校验：
  - 空值检查（关键字段不能全为 nan）
  - 范围检查（数值在 min/max 区间内）
  - 时效检查（日期不过期）
  - 完整性检查（行数不低于阈值）
  - 一致性检查（同数据多源偏差<5%）
- `check_stale(filepath, max_age_hours)` — 检查缓存文件是否过期

### Dependencies
- [ ] TASK-301（storage）
- [ ] TASK-103（pydantic）

### Test Cases
```python
def test_validation_result_model():
    r = ValidationResult(passed=True, warnings=[], errors=[])
    assert r.passed is True

def test_validate_range_error():
    df = pd.DataFrame({"pct": [150.0]})  # PE分位超100%
    rules = {"pct": {"min": 0, "max": 100}}
    result = validate(df, rules)
    assert not result.passed
    assert any("range" in e.lower() for e in result.errors)

def test_validate_empty_df():
    df = pd.DataFrame()
    result = validate(df, {})
    assert not result.passed

def test_check_stale_fresh(tmp_path):
    path = tmp_path / "fresh.csv"
    save_csv(pd.DataFrame({"a": [1]}), str(path))
    assert not check_stale(str(path), max_age_hours=24)

def test_check_stale_old(tmp_path):
    path = tmp_path / "old.csv"
    # 文件创建时间为 2 天前（手动设置 mtime）
    save_csv(pd.DataFrame({"a": [1]}), str(path))
    os.utime(path, (time.time() - 2*86400, time.time() - 2*86400))
    assert check_stale(str(path), max_age_hours=24)
```

---

## Task: TASK-501 — akshare_client.py 基础 + _with_cache

**Story:** Story-005
**Status:** `done`
**Type:** `feat`
**Module:** `src/akshare_client.py`

### Functionality
- 创建 `src/akshare_client.py`
- `_with_cache(cache_key, ttl_hours, fetch_fn)` — 统一缓存装饰/封装逻辑
  - 检查 `data/cache/{cache_key}.csv` 是否存在且在 TTL 内
  - 命中 → 读缓存，写 cache_hit 日志
  - 未命中 → 调用 fetch_fn()，成功后写入缓存
- 所有方法基于 akshare 封装，统一异常处理（超时/网络错误 → 抛出，调用方决定降级）

### Dependencies
- [ ] TASK-303（collect_if_missing）
- [ ] TASK-401（validator）
- [ ] TASK-103（requirements.txt）

### Test Cases
```python
# mock akshare API 测试，不依赖真实接口
def test_with_cache_hit(monkeypatch, tmp_path):
    # 缓存存在且有效，直接返回，不调用 fetch_fn
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fetch_called = False
    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"value": [99]})
    result = _with_cache("test_key", 24, fake_fetch, cache_dir=tmp_path/"cache")
    # 已有缓存文件时，不应调用
    # 注意：需要预先写入缓存文件才测 cache_hit

def test_with_cache_miss(monkeypatch, tmp_path):
    fetch_called = False
    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"value": [42]})
    result = _with_cache("new_key", 24, fake_fetch, cache_dir=tmp_path/"cache")
    assert fetch_called
    assert result["value"][0] == 42
```

---

## Task: TASK-502 — akshare_client.py 行情接口

**Story:** Story-005
**Status:** `done`
**Type:** `feat`
**Module:** `src/akshare_client.py`

### Functionality
- `get_etf_snapshot()` → `fund_etf_category_sina()`，当日缓存
- `get_north_flow(symbol, months)` → `stock_hsgt_hist_em()`，缓存 7 天
- `get_etf_history(code)` → 首选 `fund_etf_hist_sina`，失败降级 `fund_etf_hist_em`
- `get_etf_scale()` → `fund_etf_scale_sse()`，缓存 7 天
- `get_margin_sh()` → `macro_china_market_margin_sh()`，缓存 1 天

### Dependencies
- [ ] TASK-501（基础 + _with_cache）

### Test Cases
```python
# mock 测试，验证接口签名和降级逻辑
def test_get_etf_history_fallback(monkeypatch):
    # 模拟 fund_etf_hist_sina 失败，自动降级 fund_etf_hist_em
    monkeypatch.setattr(akshare, "fund_etf_hist_sina", side_effect=Exception("fail"))
    monkeypatch.setattr(akshare, "fund_etf_hist_em", lambda **k: pd.DataFrame({"close": [100]}))
    result = get_etf_history("510300")
    assert len(result) > 0
```

---

## Task: TASK-503 — akshare_client.py 宏观接口

**Story:** Story-005
**Status:** `done`
**Type:** `feat`
**Module:** `src/akshare_client.py`

### Functionality
- `get_pmi()` → `macro_china_pmi()`，缓存 30 天
- `get_cpi()` → `macro_china_cpi_yearly()`，缓存 30 天
- `get_ppi()` → `macro_china_ppi_yearly()`，缓存 30 天
- `get_m2()` → `macro_china_money_supply()`，缓存 30 天
- `get_lpr()` → `macro_china_lpr()`，缓存 7 天
- `get_shrzgm()` → `macro_china_shrzgm()`，缓存 30 天
- `get_gdp()` → `macro_china_gdp()`，缓存 90 天
- `get_industrial()` → `macro_china_industrial_production_yoy()`，缓存 30 天
- `get_industry_alloc(year)` → `fund_portfolio_industry_allocation_em()`，缓存 90 天

### Dependencies
- [ ] TASK-501（基础 + _with_cache）

### Test Cases
```python
# mock 测试，验证接口返回格式
def test_get_pmi_returns_dataframe(monkeypatch):
    monkeypatch.setattr(akshare, "macro_china_pmi", lambda: pd.DataFrame({"value": [51.5]}))
    result = get_pmi()
    assert isinstance(result, pd.DataFrame)
```

---

## Task: TASK-601 — ttfund_client.py 基础结构

**Story:** Story-006
**Status:** `done`
**Type:** `feat`
**Module:** `src/ttfund_client.py`

### Functionality
- 创建 `src/ttfund_client.py`
- 统一 HTTP 请求封装（requests.Session）
- API 调用间隔控制（≥1 秒）
- 统一错误处理（超时/限流/网络错误）
- 支持 partial rerun（复用 storage.collect_if_missing）

### Dependencies
- [ ] TASK-303（collect_if_missing）
- [ ] TASK-103（requirements.txt）

### Test Cases
```python
def test_api_call_interval(monkeypatch):
    # 连续调用应被间隔控制（通过 mock time 验证）
    import time
    calls = []
    original_time = time.time
    def mock_time():
        return original_time()
    monkeypatch.setattr(time, "time", mock_time)
    # ...验证调用间隔
```

---

## Task: TASK-602 — ttfund_client.py 8 个接口封装

**Story:** Story-006
**Status:** `done`
**Type:** `feat`
**Module:** `src/ttfund_client.py`

### Functionality
- `get_fund_info(fcode)` → Skill `FUND_BASE_INFOS`
- `get_nav_history(fund_id, range)` → Skill `FUND_NAV_INFO`
- `get_index_info(index_id, scope)` → Skill `FUND_INDEX_INFO`
- `get_holdings(fund_id, holding_type)` → Skill `FUND_HOLDING_INFO`
- `search_funds(page, page_num, order)` → Skill `FUND_CONDITION_SELECT`
- `get_manager_info(name)` → Skill `FUND_MANAGER_INFO`
- `get_gold_info(scope)` → Skill `FUND_HUAAN_GOLD_INFO`
- `get_strategy(name, scope)` → Skill `FUND_TG_STRATEGY_INFO`

### Dependencies
- [ ] TASK-601（基础结构）

### Test Cases
```python
# mock 测试，验证 API 请求/响应格式
def test_get_nav_history_returns_dataframe(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: MockResponse({"data": []}))
    result = get_nav_history("001", "y")
    assert isinstance(result, (pd.DataFrame, dict))
```

---

## Test Task Extraction

| Test Task | Story | Test Type | Description |
|-----------|-------|----------|-------------|
| TEST-101 | Story-001 | Unit | ETF/INDEX 列表配置测试 |
| TEST-201 | Story-002 | Unit | log_collect / alert 写入测试 |
| TEST-202 | Story-002 | Unit | run_id 唯一性测试 |
| TEST-301 | Story-003 | Unit | CSV 读写 + partial rerun 逻辑测试 |
| TEST-302 | Story-003 | Unit | JSON 读写测试 |
| TEST-401 | Story-004 | Unit | 校验规则 + check_stale 测试 |
| TEST-501 | Story-005 | Unit | _with_cache 缓存命中/未命中测试 |
| TEST-502 | Story-005 | Unit | 行情接口 + 降级链路测试 |
| TEST-503 | Story-005 | Unit | 宏观接口测试 |
| TEST-601 | Story-006 | Unit | API 调用间隔测试 |
| TEST-602 | Story-006 | Unit | 8 个接口 mock 测试 |
| TEST-701 | Story-007 | Integration | collector_daily 端到端测试 |
| TEST-801 | Story-008 | Integration | collector_weekly 端到端测试 |
| TEST-901 | Story-009 | Integration | collector_monthly 端到端测试 |
| TEST-1001 | Story-010 | Integration | collector_quarterly 端到端测试 |
| TEST-1101 | Story-011 | Smoke | 容器构建 + 健康检查测试 |

---

## Story → Task 汇总

| Story | Tasks | Status |
|-------|-------|--------|
| Story-001 | TASK-101, TASK-102, TASK-103 | `done` |
| Story-002 | TASK-201, TASK-204 | `done` |
| Story-003 | TASK-301, TASK-302, TASK-303 | `done` |
| Story-004 | TASK-401 | `done` |
| Story-005 | TASK-501, TASK-502, TASK-503 | `done` |
| Story-006 | TASK-601, TASK-602 | `done` |
| Story-007 | TASK-701 | `done` |
| Story-008 | TASK-801 | `done` |
| Story-009 | TASK-901 | `done` |
| Story-010 | TASK-1001 | `done` |
| Story-011 | TASK-1101 | `done` |
| Story-012 | TASK-1201 | `done` |
| Story-013 | TASK-1301 | `done` |
---

## Story-007: 日度采集 collector_daily.py
**Status:** `done` | **Story ID:** Story-007

### Task: TASK-701 — collector_daily.py 主脚本
**Story:** Story-007 | **Status:** `done` | **Type:** `feat` | **Module:** `src/collector_daily.py`

#### Functionality
创建 `collector_daily.py`，支持两种运行模式：

**Mode: `close`（交易日 15:30）**
| # | 数据 | 来源 | 调用 | 存储 |
|---|------|------|------|------|
| 1 | ETF 全市场行情快照 | AkShare | `akshare_client.get_etf_snapshot()` | `daily/etf_snapshot_{date}.csv` |
| 2 | 融资融券余额 | AkShare | `akshare_client.get_margin_sh()` | `daily/margin_sh_{date}.csv` |
| 3 | 核心 ETF 净值 | 天天基金 | `ttfund_client.get_nav_history(code, "y")` 遍历 ETF_WATCH_LIST | `daily/nav_{code}_{date}.csv` |
| 4 | 北向资金近 3 月 | AkShare | `akshare_client.get_north_flow("沪股通", 3)` | `daily/north_flow_{date}.csv` |

**Mode: `morning`（每日 08:00）**
| # | 数据 | 来源 | 调用 | 存储 |
|---|------|------|------|------|
| 1 | 黄金 + 宏观指标 | 天天基金 | `ttfund_client.get_gold_info("all")` | `daily/gold_macro_{date}.json` |
| 2 | 核心指数估值分位 | 天天基金 | `ttfund_client.get_index_info(idx, "all")` 遍历 INDEX_WATCH_LIST | `daily/index_valuation_{date}.json` |

**核心逻辑：**
1. 检查今天是否交易日（排除周末和节假日）
2. 逐项采集，每项调用 `storage.collect_if_missing()` 实现 partial rerun
3. 每项采集后执行 `validator.validate()` 校验
4. 校验通过 → 保存文件；失败 → 告警 + 标记异常，继续其他任务
5. 汇总输出：采集成功率、各接口状态
6. 日志写入 `data/logs/collect_{date}.csv`

**CLI 用法：**
```bash
python collector_daily.py --mode=close   # 交易日收盘后
python collector_daily.py --mode=morning # 每日早间
```

#### Dependencies
- TASK-501（akshare_client 行情接口）
- TASK-601, TASK-602（ttfund_client）
- TASK-303（collect_if_missing）
- TASK-401（validator）
- TASK-201, TASK-204（logger）

#### Test Cases
```python
# TEST-701 — collector_daily 端到端测试（mock）
def test_collector_daily_close_modes(monkeypatch, tmp_path):
    """测试 close 模式：全部 cache_hit 时不调用真实 API"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # 预先写入缓存文件，验证不重复请求
    ...

def test_collector_daily_morning_modes(monkeypatch, tmp_path):
    """测试 morning 模式"""
    ...

def test_collector_daily_partial_rerun(monkeypatch, tmp_path):
    """部分数据已存在时，只补全缺失项"""
    ...

def test_collector_daily_holiday_skip(monkeypatch):
    """节假日不执行采集"""
    ...
```

---

## Story-008: 周度采集 collector_weekly.py
**Status:** `done` | **Story ID:** Story-008

### Task: TASK-801 — collector_weekly.py 主脚本
**Story:** Story-008 | **Status:** `done` | **Type:** `feat` | **Module:** `src/collector_weekly.py`

#### Functionality
创建 `collector_weekly.py`，运行时间：每周日 20:00

| # | 数据 | 来源 | 调用 | 存储 |
|---|------|------|------|------|
| 1 | ETF 规模/份额 | AkShare | `akshare_client.get_etf_scale()` | `weekly/etf_scale_{date}.csv` |
| 2 | 条件选基排名 | 天天基金 | `ttfund_client.search_funds(1, 50, "5_6_-1")` | `weekly/fund_rank_{date}.csv` |
| 3 | 重点基金经理信息 | 天天基金 | `ttfund_client.get_manager_info(name)` 遍历经理列表 | `weekly/manager_{name}_{date}.json` |

**核心逻辑：**
1. 运行前检查是否上周已采集（exists_today）
2. 调用各数据源，使用 `collect_if_missing` partial rerun
3. 每项校验 + 日志记录
4. 汇总报告

**CLI 用法：**
```bash
python collector_weekly.py
```

#### Dependencies
- TASK-501（akshare_client.get_etf_scale）
- TASK-602（ttfund_client.search_funds, get_manager_info）
- TASK-303（collect_if_missing）
- TASK-401（validator）

#### Test Cases
```python
# TEST-801 — collector_weekly 端到端测试（mock）
def test_collector_weekly_runs_all_sources(monkeypatch, tmp_path):
    ...

def test_collector_weekly_partial_rerun(monkeypatch, tmp_path):
    ...
```

---

## Story-009: 月度采集 collector_monthly.py
**Status:** `done` | **Story ID:** Story-009

### Task: TASK-901 — collector_monthly.py 主脚本
**Story:** Story-009 | **Status:** `done` | **Type:** `feat` | **Module:** `src/collector_monthly.py`

#### Functionality
创建 `collector_monthly.py`，运行时间：每月1日 02:00

| # | 数据 | 来源 | 调用 | 存储 |
|---|------|------|------|------|
| 1 | PMI | AkShare | `akshare_client.get_pmi()` | `monthly/macro_pmi_{month}.csv` |
| 2 | CPI | AkShare | `akshare_client.get_cpi()` | `monthly/macro_cpi_{month}.csv` |
| 3 | PPI | AkShare | `akshare_client.get_ppi()` | `monthly/macro_ppi_{month}.csv` |
| 4 | M2/M1/M0 | AkShare | `akshare_client.get_m2()` | `monthly/macro_m2_{month}.csv` |
| 5 | 社融增量 | AkShare | `akshare_client.get_shrzgm()` | `monthly/macro_shrzgm_{month}.csv` |
| 6 | GDP | AkShare | `akshare_client.get_gdp()` | `monthly/macro_gdp_{month}.csv` |
| 7 | 工业增加值 | AkShare | `akshare_client.get_industrial()` | `monthly/macro_industrial_{month}.csv` |
| 8 | LPR 利率 | AkShare | `akshare_client.get_lpr()` | `monthly/macro_lpr_{month}.csv` |
| 9 | 核心 ETF 持仓 | 天天基金 | `ttfund_client.get_holdings(code)` 遍历 ETF_WATCH_LIST | `monthly/holding_{code}_{month}.json` |

**⚠️ 注意：** CPI/PPI/工业增加值接口耗时 20-40 秒，月度脚本不着急，逐个运行即可。

**核心逻辑：**
1. 使用 `collect_if_missing` 避免重复请求（TTL 720h = 30 天）
2. 慢接口优先使用缓存（已存在则直接读缓存，不触发 API）
3. 每项校验 + 日志记录
4. 汇总报告（注明哪些走了缓存、哪些触发了 API）

**CLI 用法：**
```bash
python collector_monthly.py
```

#### Dependencies
- TASK-503（akshare_client 宏观接口）
- TASK-602（ttfund_client.get_holdings）
- TASK-303（collect_if_missing）
- TASK-401（validator）

#### Test Cases
```python
# TEST-901 — collector_monthly 端到端测试（mock）
def test_collector_monthly_slow_apis_cached(monkeypatch, tmp_path):
    """慢接口第二次运行走缓存，不触发真实 API"""
    ...

def test_collector_monthly_runs_all_sources(monkeypatch, tmp_path):
    ...
```

---

## Story-010: 季度采集 collector_quarterly.py
**Status:** `done` | **Story ID:** Story-010

### Task: TASK-1001 — collector_quarterly.py 主脚本
**Story:** Story-010 | **Status:** `done` | **Type:** `feat` | **Module:** `src/collector_quarterly.py`

#### Functionality
创建 `collector_quarterly.py`，运行时间：每季初1日 03:00

| # | 数据 | 来源 | 调用 | 存储 |
|---|------|------|------|------|
| 1 | 行业配置 | AkShare | `akshare_client.get_industry_alloc(year)` | `quarterly/industry_alloc_{year}.csv` |
| 2 | 投顾策略 | 天天基金 | `ttfund_client.get_strategy(name)` | `quarterly/strategy_{name}_{year}.json` |
| 3 | 持有人结构 | 天天基金 | `ttfund_client.get_fund_info(code)` 提取持有人字段 | `quarterly/holder_structure_{code}_{year}.json` |

**核心逻辑：**
1. `get_industry_alloc` — 缓存 2160h（90 天），季度更新一次
2. `get_strategy` — 遍历配置的策略名列表
3. `get_fund_info` — 批量获取 ETF 持有人结构
4. 使用 `collect_if_missing` partial rerun
5. 汇总报告

**CLI 用法：**
```bash
python collector_quarterly.py
```

#### Dependencies
- TASK-503（akshare_client.get_industry_alloc）
- TASK-602（ttfund_client.get_strategy, get_fund_info）
- TASK-303（collect_if_missing）
- TASK-401（validator）

#### Test Cases
```python
# TEST-1001 — collector_quarterly 端到端测试（mock）
def test_collector_quarterly_runs_all_sources(monkeypatch, tmp_path):
    ...
```

---

## Story-011: 容器化部署
**Status:** `done` | **Story ID:** Story-011

### Task: TASK-1101 — Dockerfile + docker-compose
**Story:** Story-011 | **Status:** `done` | **Type:** `feat` | **Module:** `Dockerfile`, `docker-compose.yml`

#### Functionality
1. **Dockerfile** — 多阶段构建
   - 基础镜像：`python:3.12-slim`
   - 安装系统依赖（gcc, git）
   - 安装 Python 依赖：`pip install -r requirements.txt`
   - 非 root 用户运行（创建 `app` 用户）
   - 健康检查：`python -c "import src.collector_daily"`
   - 入口脚本：`python collector_daily.py`

2. **docker-compose.yml** — 本地开发 + Cron 模拟
   - 服务：`collector`（容器内 Python 运行 Cron）
   - 宿主机目录挂载：`/root/secureshare/files/ETF轮动分析框架/`
   - 环境变量注入：`TTFUND_APIKEY`

#### Dependencies
- TASK-103（requirements.txt 完成后）
- 所有采集脚本完成（TASK-701, TASK-801, TASK-901, TASK-1001）

#### Test Cases
```python
# TEST-1101 — 容器构建 + 健康检查（smoke test）
def test_dockerfile_builds(tmp_path):
    """验证 Dockerfile 能成功构建"""
    ...

def test_docker_compose_up(monkeypatch, tmp_path):
    """验证 docker-compose up 能正常启动"""
    ...
```

---

## Story-012: 天天基金接口调试与优化
**Status:** `done` | **Story ID:** Story-012

### Task: TASK-1201 — 接口调通 + 降级链路验证
**Story:** Story-012 | **Status:** `done` | **Type:** `fix` | **Module:** `src/ttfund_client.py`, `docs/ttfund_api_field_mapping.md`

#### Functionality
基于 Story-006 完成的 `ttfund_client.py`，实际调用天天基金 API，验证并修复以下问题：

1. **调通 8 个接口的实际调用**
   - `get_fund_info("510300")` → 验证返回字段
   - `get_nav_history("510300", "y")` → 验证净值数据
   - `get_index_info("沪深300", "all")` → 验证估值分位
   - `get_holdings("510300")` → 验证持仓字段
   - `search_funds(1, 50, "5_6_-1")` → 验证选基结果
   - `get_manager_info("张坤")` → 验证经理信息
   - `get_gold_info("all")` → 验证黄金数据
   - `get_strategy("稳健", "all")` → 验证策略数据

2. **记录接口响应格式和字段映射**
   - 写入 `docs/ttfund_api_field_mapping.md`，供 Story-007~010 采集脚本使用

3. **修复发现的问题**
   - 字段名不匹配 → 更新接口封装
   - 数据为空 → 记录并告警（不影响其他接口）
   - API 限流 → 增加间隔或添加重试逻辑

#### Dependencies
- TASK-602（8 个接口封装完成）

#### Test Cases
```python
# TEST-1201 — 天天基金接口自动化测试

# Unit Tests (mock) — 验证接口封装逻辑，不调用真实 API
def test_get_fund_info_mock(monkeypatch):
    """验证 get_fund_info 请求格式和响应解析"""
    mock_response = {
        "code": 0,
        "message": "success",
        "data": {
            "skill_id": "FUND_BASE_INFOS",
            "raw_result": {
                "status_code": 200,
                "body": {
                    "success": True,
                    "errorCode": 0,
                    "data": {
                        "fund_info": {"fcode": "510300", "name": "沪深300ETF华泰柏瑞"}
                    }
                }
            }
        }
    }
    monkeypatch.setattr(requests, "post", lambda *a, **k: MockResponse(mock_response))
    result = get_fund_info("510300")
    assert result["fcode"] == "510300"

def test_get_nav_history_mock(monkeypatch):
    """验证 get_nav_history 请求格式和响应解析"""
    ...

# Integration Tests (real API) — 验证真实 API 调用
def test_get_nav_history_real():
    """验证 FUND_NAV_INFO 真实调用返回有效数据"""
    result = get_nav_history("510300", "y")
    assert len(result) > 0
    assert "DWJZ" in result.columns  # 单位净值字段存在

def test_get_index_info_real():
    """验证 FUND_INDEX_INFO 真实调用"""
    result = get_index_info("沪深300", "all")
    assert result is not None

def test_get_gold_info_real():
    """验证 FUND_HUAAN_GOLD_INFO 真实调用"""
    result = get_gold_info("all")
    assert result is not None

# Contract Tests — 验证响应字段稳定性
def test_nav_history_contract():
    """验证 nav_history 响应字段未发生变化（兼容性测试）"""
    required_fields = ["FSRQ", "DWJZ", "JZZZL", "LJJZ"]
    result = get_nav_history("510300", "y")
    for field in required_fields:
        assert field in result.columns, f"字段 {field} 缺失，接口可能已变更"
```

---

## Story-013: 季度分析报告生成
**Status:** `done` | **Story ID:** Story-013

### Task: TASK-1301 — 报告生成脚本框架
**Story:** Story-013 | **Status:** `done` | **Type:** `feat` | **Module:** `src/generate_quarterly_report.py`

#### Functionality
在 `collector_quarterly.py` 完成后，扩展生成季度分析报告的数据汇总：

1. **生成季度数据汇总文件**
   - 读取 `quarterly/` 下本季度的所有数据文件
   - 生成 `quarterly/report_{year}Q{n}_summary.json`：
     - 行业配置变化（相比上季度）
     - ETF 规模变化趋势
     - 北向资金季度流入
     - 宏观指标（GDP/PPI/M2 等）季度对比

2. **输出格式**
   - JSON 文件，供 LLM 读取生成报告
   - 字段：`quarter`, `industry_alloc`, `etf_scale_trend`, `north_flow`, `macro_indicators`

3. **可选：生成 Markdown 报告**
   - 调用 LLM API 生成分析报告（依赖外部 LLM）
   - 输出 `quarterly/report_{year}Q{n}.md`

**CLI 用法：**
```bash
python generate_quarterly_report.py --year 2026 --quarter 2
```

#### Dependencies
- TASK-1001（collector_quarterly 完成）
- Story-007~010 的所有数据采集完成

#### Test Cases
```python
# TEST-1301 — 报告生成测试
def test_generate_quarterly_summary(monkeypatch, tmp_path):
    """验证季度汇总文件生成"""
    ...
```

---

## 更新后的 Test Task 汇总

| Test Task | Story | Test Type | Description |
|-----------|-------|-----------|------------|
| TEST-101 | Story-001 | Unit | ETF/INDEX 列表配置测试 |
| TEST-201 | Story-002 | Unit | log_collect / alert 写入测试 |
| TEST-202 | Story-002 | Unit | run_id 唯一性测试 |
| TEST-301 | Story-003 | Unit | CSV 读写 + partial rerun 逻辑测试 |
| TEST-302 | Story-003 | Unit | JSON 读写测试 |
| TEST-401 | Story-004 | Unit | 校验规则 + check_stale 测试 |
| TEST-501 | Story-005 | Unit | _with_cache 缓存命中/未命中测试 |
| TEST-502 | Story-005 | Unit | 行情接口 + 降级链路测试 |
| TEST-503 | Story-005 | Unit | 宏观接口测试 |
| TEST-601 | Story-006 | Unit | API 调用间隔测试 |
| TEST-602 | Story-006 | Unit | 8 个接口 mock 测试 |
| TEST-701 | Story-007 | Integration | collector_daily 端到端测试 |
| TEST-801 | Story-008 | Integration | collector_weekly 端到端测试 |
| TEST-901 | Story-009 | Integration | collector_monthly 端到端测试 |
| TEST-1001 | Story-010 | Integration | collector_quarterly 端到端测试 |
| TEST-1101 | Story-011 | Smoke | 容器构建 + 健康检查测试 |
| TEST-1201 | Story-012 | Unit + Integration | 天天基金接口 mock + 真实 API 测试 + contract 测试 |
| TEST-1301 | Story-013 | Integration | 季度报告生成测试 |

---

## 更新后的 Story → Task 汇总

| Story | Tasks | Status | 详细描述 |
|-------|-------|--------|---------|
| Story-001 | TASK-101, TASK-102, TASK-103 | `done` | ✅ 完整 |
| Story-002 | TASK-201, TASK-204 | `done` | ✅ 完整 |
| Story-003 | TASK-301, TASK-302, TASK-303 | `done` | ✅ 完整 |
| Story-004 | TASK-401 | `done` | ✅ 完整 |
| Story-005 | TASK-501, TASK-502, TASK-503 | `done` | ✅ 完整 |
| Story-006 | TASK-601, TASK-602 | `done` | ✅ 完整 |
| Story-007 | TASK-701 | `done` | ✅ 已补充 |
| Story-008 | TASK-801 | `done` | ✅ 已补充 |
| Story-009 | TASK-901 | `done` | ✅ 已补充 |
| Story-010 | TASK-1001 | `done` | ✅ 已补充 |
| Story-011 | TASK-1101 | `done` | ✅ 已补充 |
| Story-012 | TASK-1201 | `done` | ✅ 已补充 |
| Story-013 | TASK-1301 | `done` | ✅ 已补充 |

---
