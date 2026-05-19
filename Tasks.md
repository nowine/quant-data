# Tasks.md — ETF 数据采集系统

> Story → Task 拆分 | 基于 Plan.md v1.0-draft
> 版本：1.0-draft | 2026-05-20

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
**Status:** `pending` | **Story ID:** Story-001

---

## Task: TASK-101 — config.py 基础配置结构

**Story:** Story-001
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
**Status:** `pending`
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
| Story-001 | TASK-101, TASK-102, TASK-103 | `pending` |
| Story-002 | TASK-201, TASK-204 | `pending` |
| Story-003 | TASK-301, TASK-302, TASK-303 | `pending` |
| Story-004 | TASK-401 | `pending` |
| Story-005 | TASK-501, TASK-502, TASK-503 | `pending` |
| Story-006 | TASK-601, TASK-602 | `pending` |
| Story-007 | TASK-701~71x | `pending` |
| Story-008 | TASK-801~80x | `pending` |
| Story-009 | TASK-901~90x | `pending` |
| Story-010 | TASK-1001~100x | `pending` |
| Story-011 | TASK-1101 | `pending` |
| Story-012 | TASK-1201 | `pending` |
| Story-013 | TASK-1301 | `pending` |