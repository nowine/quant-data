# Tasks.md — quant-data 升级 Task 拆分

> SDD Task Breakdown | Quick Mode
> 版本：0.2-upgrade | 2026-05-22

---

## Story-101: config.py 升级

**Functionality:** `USER_HOLDINGS`（用户持仓列表）+ `SECTOR_MAPPING`（ETF→行业板块）+ ETF_WATCH_LIST 补充 159530/159934
**Verification:** `python -c "from src.config import USER_HOLDINGS, SECTOR_MAPPING; assert len(USER_HOLDINGS) >= 3"`

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1011 | 添加 `USER_HOLDINGS` 列表（159530 机器人ETF、159934 黄金ETF、588750 芯片ETF）| 验证长度+字段 | pending |
| TASK-1012 | 添加 `SECTOR_MAPPING` 字典（板块→ETF代码列表，含机器人/黄金/半导体等）| 验证 keys+映射正确 | pending |
| TASK-1013 | ETF_WATCH_LIST 补充 159530、159934 | 验证列表长度增加 | pending |

---

## Story-102: sector_aggregator.py

**Functionality:** 板块聚合 + 排名
**Verification:** `python -c "from src.sector_aggregator import aggregate_by_sector, rank_sectors; print('OK')"`

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1021 | `aggregate_by_sector(snapshot_df, sector_mapping)` — 按板块聚合平均涨跌幅/成交额/涨跌家数 | mock 数据测试 | pending |
| TASK-1022 | `rank_sectors(sector_df)` — 输出排名矩阵 | mock 数据测试 | pending |
| TASK-1023 | 真实 ETF snapshot 数据验证 | 真实运行验证 | pending |

---

## Story-103: tech_indicator.py

**Functionality:** 技术指标计算（MA/ATR/RSI/量比/Bollinger/MACD）
**Verification:** `python -c "from src.tech_indicator import calc_ma, calc_rsi, calc_atr, calc_volume_ratio, calc_bollinger, calc_macd"`

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1031 | `calc_ma(data, periods=[20,60])` + `calc_ma_deviation()` — MA 及其偏离度 | mock OHLCV DataFrame | pending |
| TASK-1032 | `calc_atr(data, period=14)` — ATR 波动性指标 | mock OHLCV DataFrame | pending |
| TASK-1033 | `calc_rsi(data, period=14)` — RSI 超买超卖 | mock OHLCV DataFrame | pending |
| TASK-1034 | `calc_volume_ratio(data, period=20)` — 量比 | mock OHLCV DataFrame | pending |
| TASK-1035 | `calc_bollinger(data, period=20)` — 布林带上/中/下轨 | mock OHLCV DataFrame | pending |
| TASK-1036 | `calc_macd(data)` — DIF/DEA/MACD 柱状图 | mock OHLCV DataFrame | pending |
| TASK-1037 | 真实 ETF 历史行情验证（159530）| `ak.fund_etf_hist_em` → tech_indicator | pending |

---

## Story-104: akshare_client 美股 + 历史行情

**Functionality:** `get_us_stock_index()` + `get_etf_history()`
**Verification:** 真实 API 调用成功返回数据

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1041 | `get_us_stock_index()` — 纳斯达克/标普/道指 | mock 测试 + 真实 API | pending |
| TASK-1042 | `get_etf_history(code, period, start_date, end_date, adjust)` — 封装 `ak.fund_etf_hist_em` | mock 测试 + 真实 API | pending |
| TASK-1043 | 单元测试（mock）| pytest 通过 | pending |
| TASK-1044 | 真实 API 验证 | 手动验证 | pending |

---

## Story-105: collector_daily P0 改进

**Functionality:** close 模式板块聚合 + morning 模式溢价率计算
**Verification:** `python src/collector_daily.py --mode=close` 生成 `sector_rank_*.csv`；morning 模式正常执行

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1051 | close 模式调用 `aggregate_by_sector` → 保存 `sector_rank_{date}.csv` | 集成测试 | pending |
| TASK-1052 | morning 模式计算持仓 ETF 溢价率（snapshot 收盘价 / nav 净值 - 1），缺失时 warn 并跳过 | 集成测试 | pending |
| TASK-1053 | 单元测试更新 | pytest 通过 | pending |

---

## Story-106: portfolio_calc.py

**Functionality:** 组合贡献度/相关性/Beta/回撤/夏普/波动率
**Verification:** `python -c "from src.portfolio_calc import calc_contribution, calc_correlation, calc_beta, calc_max_drawdown, calc_sharpe, calc_volatility"`

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1061 | `calc_contribution(holdings_df, weights)` + `calc_correlation(returns_df)` | mock 收益率数据 | pending |
| TASK-1062 | `calc_beta(portfolio_return, benchmark_return)` | mock 数据 | pending |
| TASK-1063 | `calc_max_drawdown(equity_curve)` — 最大回撤及起止日 | mock 净值序列 | pending |
| TASK-1064 | `calc_sharpe(returns, risk_free_rate)` + `calc_volatility(returns)` | mock 数据 | pending |

---

## Story-107: akshare_client P1 扩展

**Functionality:** 汇率/期货基差/大宗商品/行业板块
**Verification:** 各接口真实调用（不稳定则记录降级方案）

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1071 | `get_fx_rate()` — 人民币/美元 | 真实 API | pending |
| TASK-1072 | `get_futures_basis()` — 股指期货基差 | 真实 API | pending |
| TASK-1073 | `get_commodity_price()` — 原油/铜/黄金 | 真实 API | pending |
| TASK-1074 | `get_stock_board_industry()` — 行业板块涨跌 | 真实 API | pending |

---

## Story-108: collector_daily P1 改进

**Functionality:** morning 技术指标 + close 美股数据
**Verification:** morning 输出技术指标，close 输出美股数据

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1081 | morning 模式调用 `calc_ma/rsi/atr` 计算持仓 ETF 技术指标（实时计算，不持久化）| 集成测试 | pending |
| TASK-1082 | close 模式调用 `get_us_stock_index` 采集前一交易日美股（仅交易日）| 集成测试 | pending |

---

## Story-109: collector_weekly/monthly P1 改进

**Functionality:** 周报/月报所需的排名变化和组合指标
**Verification:** weekly/monthly 运行后检查对应文件

### Tasks

| Task | Description | Test | Status |
|------|-------------|------|--------|
| TASK-1091 | weekly 新增 `sector_rank_change_{date}.csv`（本周 vs 上周排名变化矩阵）| 集成测试 | pending |
| TASK-1092 | weekly 调用 `portfolio_calc` 计算持仓贡献度/相关性 → `portfolio_weekly_{date}.csv` | 集成测试 | pending |
| TASK-1093 | monthly 调用 `portfolio_calc` 计算归因/回撤/波动率 → `portfolio_monthly_{date}.csv` | 集成测试 | pending |

---

## Task 状态总览

| Task | Story | Status |
|------|-------|--------|
| TASK-1011~1013 | Story-101 | pending |
| TASK-1021~1023 | Story-102 | pending |
| TASK-1031~1037 | Story-103 | pending |
| TASK-1041~1044 | Story-104 | pending |
| TASK-1051~1053 | Story-105 | pending |
| TASK-1061~1064 | Story-106 | pending |
| TASK-1071~1074 | Story-107 | pending |
| TASK-1081~1082 | Story-108 | pending |
| TASK-1091~1093 | Story-109 | pending |