# Agent Manual — ETF 数据采集框架

> 本手册面向 **调用本框架的 AI Agent**，说明如何正确使用已采集的数据，以及如何扩展新的数据源。
> 面向用户：需要 LLM 分析结果、报告输出的 AI Agent。

---

## 目录

1. [快速开始](#1-快速开始)
2. [数据文件路径速查](#2-数据文件路径速查)
3. [各数据源详解](#3-各数据源详解)
4. [数据格式](#4-数据格式)
5. [错误传播机制（errors 字段）](#5-错误传播机制errors-字段)
6. [缓存与重跑机制](#6-缓存与重跑机制)
7. [如何扩展新数据源](#7-如何扩展新数据源)
8. [常见问题](#8-常见问题)
9. [文件清单](#9-文件清单)

---

## 1. 快速开始

### 环境变量

```bash
export TTFUND_APIKEY="ttf_sk_l..."   # 天天基金 API 密钥（必需）
export PYTHONPATH=.
```

### 采集命令一览

| 命令 | 用途 | 典型运行时间 |
|------|------|-------------|
| `python src/collector_daily.py --mode=close` | 收盘采集：ETF快照/融资融券/北向/ETF净值/指数估值 | 交易日 15:30 |
| `python src/collector_daily.py --mode=morning` | 盘前采集：黄金宏观/指数估值 | 每日 08:00 |
| `python src/collector_weekly.py` | 周度采集：ETF规模/北向周计/行业配置 | 每周日 20:00 |
| `python src/collector_monthly.py` | 月度采集：PMI/CPI/PPI/M2/LPR/GDP/工业增加值 | 每月1日 02:00 |
| `python src/collector_quarterly.py` | 季度采集：基金持仓/指数估值/行业配置 | 每季1日 03:00 |

### 健康检查

```bash
python src/collector_daily.py --mode=morning --health
# 返回 0 表示健康
```

### 返回值结构

所有 `run_*(date)` 函数返回一个 **dict**，始终包含 `errors` 字段：

```python
{
    "data": { ... },       # 各数据采集结果（key 因 mode 而异）
    "errors": [            # ⚠️ 重点：即使全部成功也返回 []，失败时有内容
        "{task}: {detail}; suggestion: {fallback_action}",
        ...
    ]
}
```

**errors 字段含义：**
- `errors = []` — 所有数据源均成功，无任何错误
- `errors = ["..."]` — 部分或全部数据源失败，但框架仍返回了退化数据（可能来自缓存或不完整采集）
- **每个错误条目格式：** `"{task}: {exception_message}; suggestion: {LLM_fallback_action}"`

**如何使用 errors 做 fallback：**
```python
result = run_close_mode()

if result["errors"]:
    # 有数据源失败，LLM 应考虑用其他途径补全
    for err in result["errors"]:
        task = err.split(": ")[0]          # e.g. "us_stock_index"
        suggestion = err.split("suggestion: ")[1]  # LLM 可执行的 fallback 指令
        print(f"数据源 [{task}] 失败，建议：{suggestion}")
else:
    # 所有数据源成功
    pass
```

---

## 2. 数据文件路径速查

所有数据存放在：`/root/secureshare/files/ETF轮动分析框架/data/`

```
data/
├── daily/                    # 每日数据 (collector_daily.py)
│   ├── etf_snapshot_{date}.csv          # ETF 实时行情快照
│   ├── margin_sh_{date}.csv             # 上海融资融券
│   ├── north_flow_{date}.csv            # 北向资金历史
│   ├── nav/                            # 基金净值目录
│   │   ├── nav_510300.csv               # 每只ETF一个文件
│   │   └── ...
│   └── index_valuation/                 # 指数估值目录
│       ├── 沪深300.csv
│       ├── 上证50.csv
│       └── ...
│
├── weekly/                   # 周度数据 (collector_weekly.py)
│   ├── etf_scale_{date}.csv            # ETF 规模/份额
│   ├── north_flow_week_{date}.csv      # 北向资金周统计
│   └── industry_alloc_{date}.csv       # ETF 行业配置
│
├── monthly/                  # 月度数据 (collector_monthly.py)
│   ├── cpi_{date}.csv                  # 居民消费价格指数
│   ├── ppi_{date}.csv                  # 工业生产者出厂价格指数
│   ├── pmi_{date}.csv                  # 采购经理指数
│   ├── gdp_{date}.csv                  # 国内生产总值
│   ├── m2_{date}.csv                   # 货币供应量
│   ├── lpr_{date}.csv                  # 贷款市场报价利率
│   ├── industrial_{date}.csv           # 工业增加值
│   └── holdings/                      # 基金持仓目录（ETF持仓）
│
├── quarterly/                # 季度数据 (collector_quarterly.py)
│   ├── holdings/                           # 基金持仓（按代码）
│   │   ├── holdings_510300_2025Q1.csv
│   │   └── ...
│   ├── index_valuation_{date}.csv         # 指数估值快照
│   ├── strategy_{name}_{date}.json        # 投顾策略
│   └── holder_structure_{code}_{date}.json # 持有人结构
│
├── validate_failed/          # 校验失败的数据（不影响原始文件）
│   └── {date}.csv
│
└── logs/
    ├── collect_{YYYYMMDD}.csv   # 采集日志
    └── alert_{YYYYMMDD}.csv     # 告警日志
```

---

## 3. 各数据源详解

### 3.1 AkShare 数据（免费，无需 API Key）

AkShare 数据源在 `src/akshare_client.py`，通过 `get_akshare_data()` 统一封装。

#### ETF 行情

```python
from src.akshare_client import get_etf_snapshot, get_etf_history, get_etf_scale

# ETF 实时快照（当日列表）
df = get_etf_snapshot()            # fund_etf_category_ths，覆盖 1576 只 ETF
                                   # 代码列为纯数字（如 "510300"），与 config 直接匹配
                                   # 注意：无成交额/成交量字段（THS 只提供净值+增长率）
                                   # 缓存当日，cache key: etf_snapshot_ths

# ETF 历史行情（K线）
df = get_etf_history("510300")     # 首选 fund_etf_hist_sina，自动降级 fund_etf_hist_em
                                   # 沪市 ETF（5开头）自动加 sh 前缀
                                   # 深市 ETF（1开头）自动加 sz 前缀
                                   # 缓存 24 小时

# ETF 规模（上海）
df = get_etf_scale()              # fund_etf_scale_sse，缓存 7 天
```

#### 北向资金

```python
from src.akshare_client import get_north_flow

df = get_north_flow("510300", 3)   # 获取沪深股通历史，months=3，缓存 7 天
# 返回列：date, open, high, low, close, volume, amount, change_pct
```

#### 融资融券

```python
from src.akshare_client import get_margin_sh

df = get_margin_sh()              # macro_china_market_margin_sh，上海市场，缓存 1 天
```

#### 宏观数据

```python
from src.akshare_client import (
    get_pmi, get_cpi, get_ppi, get_m2,
    get_lpr, get_shrzgm, get_gdp, get_industrial
)

df = get_pmi()      # 制造业PMI，缓存 30 天
df = get_cpi()      # CPI，缓存 30 天
df = get_ppi()      # PPI，缓存 30 天
df = get_m2()       # 货币供应量M2，缓存 30 天
df = get_lpr()      # LPR贷款市场报价利率，缓存 30 天
df = get_shrzgm()   # 社会融资规模，缓存 30 天
df = get_gdp()      # GDP季度数据，缓存 90 天
df = get_industrial() # 工业增加值，缓存 30 天
```

> ⚠️ CPI/PPI/工业增加值 数据源更新较慢，akshare 层面可能返回空 DataFrame。

#### 行业配置

```python
from src.akshare_client import get_industry_alloc

df = get_industry_alloc(2025)  # 基金行业配置（东方财富），缓存 90 天
```

---

### 3.2 天天基金数据（需要 TTFUND_APIKEY）

天天基金数据源在 `src/ttfund_client.py`，所有接口调用间隔 ≥1 秒（防限流）。

```python
from src.ttfand_client import (
    get_fund_info,          # 基金基本信息
    get_nav_history,        # 基金净值历史
    get_index_info,         # 指数信息/估值
    get_holdings,           # 基金持仓
    search_funds,           # 条件选基
    get_manager_info,       # 基金经理信息
    get_gold_info,          # 黄金数据
    get_strategy,           # 投顾策略
)

# 基金净值历史（重要！）
df = get_nav_history("510300", "y")    # 近1年净值，range: y/3y/5y/10y/n/y/M/D/W
# 返回列：FSRQ(date), DWJZ(nav), JZZZL(daily_return%), LJJZ(cumulative_nav), NAVTYPE, RATE

# 指数估值（重要！）
dict_resp = get_index_info("000300", "all")  # 沪深300，所有指标
# 返回嵌套 dict，结构:
# {
#   "index_valuation": {
#     "沪深300": {"pe", "pb", "roe", "dividend_yield", "turnover_rate", "status": "ok"},
#     "上证50": {...},
#     ...
#   }
# }

# 基金基本信息
dict_resp = get_fund_info("510300")

# 基金持仓（股票/债券/全部）
dict_resp = get_holdings("510300", "stock")   # holding_type: stock/bond/all

# 条件选基
df = search_funds(page=1, page_num=20, order="desc")

# 基金经理信息
dict_resp = get_manager_info("张弘")

# 黄金数据
dict_resp = get_gold_info("all")   # scope: all/gold/macro/risk

# 投顾策略
dict_resp = get_strategy("红利", "all")  # strategy_name + scope
```

---

## 4. 数据格式

### CSV 格式

- 编码：UTF-8，无 BOM
- 首行：列名
- 无额外元数据行
- 分隔符：逗号

### JSON 格式

- 标准 JSON（list 或 dict）
- UTF-8 编码
- 缩进 2 空格

### 校验规则

`src/validator.py` 提供 `validate(df, rules)` 方法，校验失败数据写入 `data/validate_failed/{date}.csv`，不影响原始文件。

---

## 5. 错误传播机制（errors 字段）

> ⚠️ **面向 LLM Agent 的核心机制** — 当部分数据源失败时，`result["errors"]` 会告知具体哪个任务失败及建议的 fallback 动作。
> 即使存在错误，采集器仍会返回退化数据（可能来自缓存或不完整采集），Agent 不应因此放弃整个采集结果。

### 5.1 错误来源分类

| 场景 | `status` 值 | `result["errors"]` | 说明 |
|------|------------|-------------------|------|
| fetch 函数返回**空 DataFrame/dict** | `"degraded"` | ✅ 追加错误 | 数据源返回空结果，可能是非交易日或数据延迟 |
| fetch 函数**抛出异常** | `"error"` | ✅ 追加错误 | 网络超时（30s）、连接断开、API 限流等 |
| **缓存命中** | `"cache_hit"` | ❌ 不修改 | 数据来自磁盘缓存，无错误 |
| **采集跳过**（文件已存在） | `"skipped"` | ❌ 不修改 | 使用已有文件，无错误 |
| **成功写入** | `"success"` | ❌ 不修改 | 正常采集，无错误 |

### 5.2 错误消息格式

```
{task_name}: {exception_or_error_detail}; suggestion: {LLM_fallback_action}
```

**示例：**
```
us_stock_index: RemoteDisconnected('Remote end closed connection without response'); suggestion: use LLM to search current US stock index data (Nasdaq/S&P/Dow)

nav_510300: TTFUND API rate limit exceeded; suggestion: check ttfund NAV interface or use LLM

margin_sh: eastmoney API unreachable (Connection aborted.); suggestion: check margin data source or skip
```

### 5.3 各采集模式的 errors 行为

#### `run_close_mode()` — 收盘采集
```python
result = run_close_mode(date)
# result["errors"] 示例：
[
    "us_stock_index: RemoteDisconnected('Remote end closed connection'); suggestion: use LLM to search current US stock index data (Nasdaq/S&P/Dow)",
    "nav_510300: TTFUND API timeout after 30s; suggestion: check ttfund NAV interface or use LLM"
]
```

| 任务名 | 失败原因 | suggestion 内容 |
|--------|---------|----------------|
| `etf_snapshot` | 空DataFrame / 异常 | use LLM to search current ETF snapshot data |
| `margin_sh` | 空DataFrame / 异常 | check margin data source or skip |
| `north_flow` | 空DataFrame / 异常 | check north flow data source or skip |
| `us_stock_index` | 异常 | use LLM to search current US stock index data (Nasdaq/S&P/Dow) |
| `nav_{code}` | 异常 | check ttfund NAV interface or use LLM |
| `index_valuation` | 空数据 / 异常 | check ttfund index valuation or use LLM |

#### `run_morning_mode()` — 盘前采集
```python
result = run_morning_mode(date)
# result["errors"] 示例：
[
    "gold_macro: TTFUND API returned empty data; suggestion: check ttfund gold/macro interface or use LLM",
    "index_valuation: empty index valuation data; suggestion: check ttfund index valuation or use LLM"
]
```

#### `run_weekly()` — 周度采集
```python
result = run_weekly(date)
# result["errors"] 示例：
[
    "etf_scale: empty ETF scale data; suggestion: check SSE ETF scale data source or skip",
    "industry_alloc: Connection reset by peer; suggestion: use LLM to search ETF industry allocation data"
]
```

#### `run_monthly()` — 月度采集
```python
result = run_monthly(date)
# result["errors"] 示例：
[
    "cpi: empty CPI data (data source not yet updated); suggestion: check macro data source or use LLM to search China CPI data",
    "gdp: Connection timeout after 30s; suggestion: check national statistics interface or skip"
]
```

### 5.4 Agent 正确处理 errors 的方式

**✅ 正确做法：**
```python
result = run_close_mode()
if result["errors"]:
    # 仍然可以使用 result["data"] 中的有效数据
    usable_data = result["data"]
    failed_sources = [e.split(": ")[0] for e in result["errors"]]
    # 根据 suggestion 决定是否用 LLM 补全
    for err in result["errors"]:
        task = err.split(": ")[0]
        action = err.split("suggestion: ")[1]
        print(f"[{task}] 失败 → {action}")
else:
    # 全部成功
    usable_data = result["data"]
```

**❌ 错误做法：**
```python
result = run_close_mode()
if result["errors"]:
    raise Exception("采集失败")  # 不要因为部分失败放弃整个结果
# 或者
if not result["data"]["etf_snapshot"]["success"]:  # 不要逐个检查，应该用 errors
    ...
```

### 5.5 超时行为

| 数据源 | 默认超时 |
|--------|---------|
| AkShare APIs（akshare_client） | **30 秒**（socket level） |
| 天天基金 API（ttfund_client） | 通过 `requests` 的 timeout 参数控制 |

超时后抛出 `socket.timeout` → 被捕获 → `_record_error` → `result["errors"]`。

### 5.6 验证 errors 是否正确记录

```bash
# 查看 CLI 输出中的 [ERRORS] 块
python src/collector_daily.py --mode=close
# 输出：
# [ERRORS] 2 issue(s) detected:
#   - us_stock_index: RemoteDisconnected('...'); suggestion: use LLM...
#   - nav_510300: timeout after 30s; suggestion: check ttfund...

# 查看日志
cat data/logs/collect_20260520.csv | grep error
```

---

## 6. 缓存与重跑机制

### 核心逻辑：`collect_if_missing()`

所有采集通过 `storage.collect_if_missing()` 实现 partial rerun：

```python
from src.storage import collect_if_missing, save_csv

def my_collector(filepath, fetch_fn, *args):
    collect_if_missing(
        filepath=filepath,
        fetch_fn=fetch_fn,
        *args,
        validator=None,          # 可选：校验函数
        max_age_hours=24,        # 可选：缓存有效期
    )
    return load_csv(filepath)
```

**规则：**
- 文件已存在且未过期 → 直接读取，不调用 API
- 文件不存在或已过期 → 调用 fetch_fn，结果写入文件

### 缓存 TTL

| 数据类型 | TTL |
|---------|-----|
| ETF 实时快照 | 8 小时 |
| ETF 历史行情 | 24 小时 |
| ETF 规模 | 7 天 |
| 北向资金 | 7 天 |
| 融资融券 | 24 小时 |
| 宏观数据 | 30 天 |
| 行业配置 | 90 天 |
| 基金净值 | 24 小时 |
| 指数估值 | 24 小时 |

### 强制重跑

删除目标文件后再次运行，采集器会重新请求 API：

```bash
rm data/daily/nav/nav_510300.csv
python src/collector_daily.py --mode=close
```

---

## 7. 如何扩展新数据源

### 6.1 添加 AkShare 数据源

在 `src/akshare_client.py` 中添加方法：

```python
def get_new_indicator(symbol: str) -> pd.DataFrame:
    """Fetch new indicator data.

    Uses _with_cache() for automatic TTL caching.
    """
    def _fetch():
        return ak.new_indicator(symbol=symbol)  # 替换为实际 akshare 函数

    return _with_cache(
        cache_key=f"new_indicator_{symbol}",
        fetch_fn=_fetch,
        ttl_hours=24,
    )
```

### 6.2 添加天天基金数据源

在 `src/ttfund_client.py` 中添加方法：

```python
def get_new_data(param: str) -> dict:
    """Fetch new data from TTFUND API.

    All params use snake_case (not camelCase).
    API call interval: ≥1 second (enforced by _check_interval).
    """
    _check_interval()  # 防限流
    return call("NEW_SKILL_ID", {"new_param": param})  # 替换为实际 skill_id 和参数
```

**参数命名规范（必须遵守）：**
- `fund_id`（不是 `fundId`）
- `index_id`（不是 `indexId`）
- `holding_type`（不是 `holdingType`）
- `manager_name`（不是 `name`）
- `strategy_name`（不是 `name`）
- `scope`（直接用）

### 6.3 添加新的采集脚本

参考 `src/collector_daily.py` 的结构：

```python
import argparse
from src.logger import log_collect
from src.storage import save_csv, collect_if_missing, load_csv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()

    if args.health:
        return  # 健康检查通过

    log_collect(task="new_task", source="new_source",
                status="start", rows=0, elapsed_sec=0.0, message="开始")

    # 采集逻辑...
    results = {}
    for item in items:
        results[item] = do_collect(item)

    # 汇总日志
    success = sum(1 for v in results.values() if v.get("status") == "ok")
    log_collect(task="new_task", source="new_source",
                status="done", rows=success,
                elapsed_sec=elapsed, message=f"成功 {success}/{len(results)}")

if __name__ == "__main__":
    main()
```

---

## 8. 常见问题

### Q: API 调用报 `400 Bad Request`

检查参数名是否使用 **snake_case**：
- ✅ `fund_id`, `index_id`, `holding_type`, `manager_name`, `strategy_name`
- ❌ `fundId`, `indexId`, `holdingType`, `name`

### Q: `get_etf_history` 返回空行

ETF 代码需要加交易所前缀：
- 沪市（5开头）：`sh510300`
- 深市（1开头）：`sz159919`

框架已自动处理（`akshare_client.py` 中 `_etf_prefix()`），但如果直接调用 `akshare.fund_etf_hist_sina(symbol='510300')` 会返回空。

### Q: `get_nav_history` 超时

天天基金 API 有速率限制（≥1秒/次），如果并发调用会被限流。
框架中 `call()` 函数已实现间隔检查，等待后重试即可。

### Q: 采集数据为空

可能原因：
1. **非交易日** — 北向、融资融券等在非交易日无数据
2. **数据源更新延迟** — CPI/PPI 等宏观数据通常有 2-4 周延迟
3. **缓存未过期** — 删除文件后重新运行

### Q: 如何确认数据已采集成功？

检查日志：
```bash
cat /root/secureshare/files/ETF轮动分析框架/data/logs/collect_20260521.csv
```

---

## 9. 文件清单

### 源代码（`src/`）

| 文件 | 用途 |
|------|------|
| `config.py` | 配置（ETF列表、API Key、缓存TTL、存储路径） |
| `logger.py` | 结构化日志（`log_collect()`、`alert()`、`get_run_id()`） |
| `storage.py` | 文件读写（`save_csv()`、`load_csv()`、`collect_if_missing()`） |
| `validator.py` | 数据质量校验（`validate()`、`check_stale()`） |
| `akshare_client.py` | AkShare 统一封装（9个数据源） |
| `ttfund_client.py` | 天天基金 API 封装（8个方法） |
| `collector_daily.py` | 日度采集（close/morning 双模式） |
| `collector_weekly.py` | 周度采集 |
| `collector_monthly.py` | 月度采集 |
| `collector_quarterly.py` | 季度采集 |
| `generate_quarterly_report.py` | 季度报告生成 |

### 测试（`tests/`）

| 文件 | 用途 |
|------|------|
| `test_config.py` | 配置单元测试 |
| `test_logger.py` | 日志单元测试 |
| `test_storage.py` | 存储单元测试 |
| `test_validator.py` | 校验单元测试 |
| `test_akshare_client.py` | AkShare mock 测试 |
| `test_ttfund_client.py` | 天天基金 mock 测试 |
| `test_akshare_market.py` | AkShare 市场数据测试 |
| `test_ttfund_api.py` | TTFUND 参数验证测试 |
| `test_collector_daily.py` | 日度采集集成测试 |
| `test_collector_weekly.py` | 周度采集测试 |
| `test_collector_monthly.py` | 月度采集测试 |
| `test_collector_quarterly.py` | 季度采集测试 |
| `test_collector_errors.py` | 错误传播机制测试（22个用例） |

---

_手册版本：1.1 | 更新日期：2026-05-23_