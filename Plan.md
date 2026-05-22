# Plan.md — quant-data 升级开发计划

> SDD Development Plan | 基于升级需求清单 v1.1
> 版本：0.2-upgrade | 2026-05-22 | Quick Mode

---

## MVP-P0: 升级版早晚报核心功能

**Stories:** Story-101, Story-102, Story-103, Story-104, Story-105
**Goal:** 完成 P0 升级，使早晚报能正常使用
**Out of Scope:** P1 功能（周报/月报增强、美股以外接口）

---

### Story-101: config.py 升级

**Need:** 添加用户持仓列表和板块映射配置
**Verification:** `python -c "from src.config import USER_HOLDINGS, SECTOR_MAPPING; assert len(USER_HOLDINGS) >= 3; assert '机器人' in SECTOR_MAPPING"`

**Tasks:**
- [ ] TASK-1011: `USER_HOLDINGS` 配置（159530, 159934 等）
- [ ] TASK-1012: `SECTOR_MAPPING` 板块映射配置
- [ ] TASK-1013: `ETF_WATCH_LIST` 添加 159530、159934

---

### Story-102: sector_aggregator.py 板块聚合模块

**Need:** 从 ETF 快照按行业聚合，生成板块涨跌排名
**Verification:** `python -c "from src.sector_aggregator import aggregate_by_sector, rank_sectors"` 无报错

**Tasks:**
- [ ] TASK-1021: `aggregate_by_sector(snapshot_df, sector_mapping)` 实现
- [ ] TASK-1022: `rank_sectors(sector_df)` 实现
- [ ] TASK-1023: 单元测试（mock snapshot_df 验证聚合逻辑）
- [ ] TASK-1024: 真实数据验证

---

### Story-103: tech_indicator.py 技术指标模块

**Need:** 计算 MA/ATR/RSI/量比，为早报提供定量分析
**Verification:** `python -c "from src.tech_indicator import calc_ma, calc_rsi, calc_atr, calc_volume_ratio"` 无报错

**Tasks:**
- [ ] TASK-1031: `calc_ma(data, periods)` + 测试
- [ ] TASK-1032: `calc_atr(data, period)` + 测试
- [ ] TASK-1033: `calc_rsi(data, period)` + 测试
- [ ] TASK-1034: `calc_volume_ratio(data, period)` + 测试
- [ ] TASK-1035: `calc_bollinger(data, period)` + 测试
- [ ] TASK-1036: `calc_macd(data)` + 测试
- [ ] TASK-1037: 真实 ETF 数据验证（159530）

---

### Story-104: akshare_client 美股 + 历史行情接口

**Need:** 早报需要美股隔夜数据 + tech_indicator 需要历史行情
**Verification:** `python -c "from src.akshare_client import get_us_stock_index, get_etf_history"` 无报错；真实调用验证

**Tasks:**
- [ ] TASK-1041: `get_us_stock_index()` 实现（纳斯达克/标普/道指）
- [ ] TASK-1042: `get_etf_history(code, period, start_date, end_date)` 实现（封装 `ak.fund_etf_hist_em`）
- [ ] TASK-1043: 单元测试
- [ ] TASK-1044: 真实 API 验证

---

### Story-105: collector_daily P0 改进

**Need:** close 增加板块聚合，morning 增加溢价率计算
**Verification:** `python src/collector_daily.py --mode=close` 生成 `sector_rank_*.csv`；morning 模式计算持仓溢价率

**Tasks:**
- [ ] TASK-1051: close 模式集成 sector_aggregator，输出 `sector_rank_{date}.csv`
- [ ] TASK-1052: morning 模式集成溢价率计算（依赖前一天 snapshot + 当日 nav）
- [ ] TASK-1053: 单元测试更新

---

## MVP-P1: 周报/月报增强功能

**Stories:** Story-106, Story-107, Story-108, Story-109
**Goal:** 周报/月报所需的组合计算和扩展接口
**Out of Scope:** —

---

### Story-106: portfolio_calc.py 组合计算模块

**Need:** 计算持仓贡献度/相关性/Beta/回撤/夏普，为周报/月报提供组合视角
**Verification:** `python -c "from src.portfolio_calc import calc_contribution, calc_max_drawdown, calc_sharpe"` 无报错

**Tasks:**
- [ ] TASK-1061: `calc_contribution(holdings, weights)` + 测试
- [ ] TASK-1062: `calc_correlation(returns_df)` + 测试
- [ ] TASK-1063: `calc_beta(portfolio_return, benchmark_return)` + 测试
- [ ] TASK-1064: `calc_max_drawdown(equity_curve)` + 测试
- [ ] TASK-1065: `calc_sharpe(returns)` + `calc_volatility(returns)` + 测试

---

### Story-107: akshare_client 扩展接口

**Need:** 汇率/期货基差/大宗商品/行业板块接口
**Verification:** 各接口真实 API 调用验证（不稳定则降级为 LLM 搜索）

**Tasks:**
- [ ] TASK-1071: `get_fx_rate()` 人民币/美元汇率
- [ ] TASK-1072: `get_futures_basis()` 股指期货基差
- [ ] TASK-1073: `get_commodity_price()` 原油/铜/金
- [ ] TASK-1074: `get_stock_board_industry()` 行业板块涨跌排名

---

### Story-108: collector_daily P1 改进

**Need:** morning 增加技术指标计算，close 增加美股数据
**Verification:** morning 输出 tech_indicators，close 输出美股数据

**Tasks:**
- [ ] TASK-1081: morning 模式调用 tech_indicator 计算持仓 ETF 技术指标
- [ ] TASK-1082: close 模式采集前一交易日美股收盘数据（仅交易日）
- [ ] TASK-1083: 单元测试更新

---

### Story-109: collector_weekly / collector_monthly 增强

**Need:** 周报/月报所需的组合指标和排名变化
**Verification:** 各自运行输出对应文件

**Tasks:**
- [ ] TASK-1091: weekly 新增板块周排名变化矩阵
- [ ] TASK-1092: weekly 新增组合周度指标（contribution/相关性）
- [ ] TASK-1093: monthly 新增月度组合归因 + 最大回撤分析 + 波动率曲面

---

## Story 总览

| Story | MVP | Title | Status |
|-------|-----|-------|--------|
| Story-101 | P0 | config.py 升级（持仓+板块映射）| pending |
| Story-102 | P0 | sector_aggregator.py 板块聚合 | pending |
| Story-103 | P0 | tech_indicator.py 技术指标 | pending |
| Story-104 | P0 | akshare_client 美股+历史行情 | pending |
| Story-105 | P0 | collector_daily P0 改进 | pending |
| Story-106 | P1 | portfolio_calc.py 组合计算 | pending |
| Story-107 | P1 | akshare_client 扩展接口 | pending |
| Story-108 | P1 | collector_daily P1 改进 | pending |
| Story-109 | P1 | collector_weekly/monthly 增强 | pending |

---

## 实施顺序（P0 先完成）

```
Story-101 (config) → Story-102 (sector) → Story-103 (tech_indicator) → Story-104 (akshare扩展) → Story-105 (collector_daily改进)
→ Story-106 (portfolio_calc) → Story-107 (akshare扩展P1) → Story-108 (collector_daily P1) → Story-109 (weekly/monthly增强)
```

**P0 完成后向用户汇报，用户验证早报/晚报功能后再继续 P1。**