# ADR-003: Ad-hoc extra holdings via CLI 参数

> **状态**: Accepted (2026-08-20)
> **决策者**: 九节
> **背景**: quant-data 工具只能基于 `config.py` 静态持仓列表查询，无法响应 prompt 中临时追加的标的

## 背景

`collector_daily.run_close_mode()` 和 `run_morning_mode()` 的循环源都是静态常量:

| 列表 | 用途 | 当前形态 |
|------|------|---------|
| `config.ETF_WATCH_LIST` (22 项) | 轮动分析框架的 ETF 净值采集 | `[{code, name, index}]` |
| `config.USER_HOLDINGS` (3 项) | 用户持仓的溢价率 / 技术指标 / 早报板块结构 | `[{code, name, sector}]` |

当主人通过 prompt 临时要求"也帮我看看 512480"，collector 不会跑这个标的 — 列表是 hardcoded，CLI 无扩展点。

### 设计目标

让 cron / 手动调用方能在不修改 `config.py` 的前提下，**一次性**追加任意 ETF 标的进入本次 run 的采集流程。

## 决策

**方案**: 引入 `--extra-holdings` CLI 参数 + 两个纯函数 seam，由 `collector_daily` 在编排层接入。

### 三个 commit 拆分（垂直切片）

| Commit | 内容 | Seam |
|--------|------|------|
| 1 | `src/extra_holdings.py::parse_extra_holdings_arg` + 11 个测试 | CLI 字符串 → `[{code, name?, sector?}]` |
| 2 | `build_extra_holdings_set(codes)` + mock 测试 | code 列表 → akshare 反查 name 的 DataFrame |
| 3 | `collector_daily` 接入 `--extra-holdings` 参数 | `run_close_mode(extra=None)` / `run_morning_mode(extra=None)` |

### 接口契约 (Q11 选择)

**CLI 参数**: `--extra-holdings '[{"code":"159530","name":"机器人ETF易方达","sector":"机器人"},{"code":"512480"}]'`

- JSON 数组字符串
- 每项必须有 6 位数字 `code`
- `name` / `sector` 可选；缺失则后续反查 / 留空
- 空串 / 纯空白 = `[]`，不报错
- JSON 解析失败 / 缺 `code` / code 非 6 位数字 = `ValueError`，CLI 层 wrap 成友好提示

### 反查决策 (Q2 + 验证后修正)

**决定**: `build_extra_holdings_set` **只**反查 `name`，**不**反查 `sector`。`sector` 缺则留 `None`。

**事实** (2026-08-20 验证):

| 数据源 | 是否可用 | 说明 |
|--------|---------|------|
| `ak.fund_name_em()` | ✅ 可用 | 全量拉一次 ~5-10s，返回 27548 行；`基金代码` 是 str；`基金简称` 是 name |
| `ak.fund_individual_basic_info_xq()` | ❌ 雪球 API 返回 `KeyError: 'data'` | 源站挂了 |
| `ak.fund_etf_fund_info_em(fund=code)` | ⚠️ 可用但慢 | 单次 ~60s/调用；冷启动拉一次都嫌慢 |
| akshare 直查 `sector` (行业板块) | ❌ 无对应 API | `fund_name_em.基金类型` 返回产品类型（"指数型-股票"），不是行业 |

**反查实现策略**:

1. 冷启动拉 `ak.fund_name_em()` 全量（一次 ~5-10s），落盘到 `~/.cache/quant-data/fund_name.csv`
2. 后续调用先查 csv，过期（>24h）再刷一次
3. 解析 `code` → 取 `基金简称` 作为 `name`；`sector` 留 `None`，由调用方（未来 collector_daily 调用层）自行补或从 `USER_HOLDINGS` 推断

**为什么不缓存到 `config.py`**: sector 没有自动数据源，且强行编 sector 字典会让 config 变成双重权威源（违反 Q6 的"一次性"原则）。

**为什么不用 parquet 用 csv**: 项目 `requirements.txt` 只锁定 `pandas>=2.0.0`，没引入 pyarrow。csv 是 pandas 原生支持，无新依赖，足够单列 [code, name] 的小表（~27548 行）。

### 临时标的触发范围 (Q4=Q7=A, Q8=A, Q10=B)

| Mode | 触发任务 | 依据 |
|------|---------|------|
| `close` | **只**净值采集（对齐 `ETF_WATCH_LIST` 语义） | 临时标的不进入轮动框架，但补当次净值 |
| `morning` | `premium_rate` + `tech_indicator`（对齐 `USER_HOLDINGS` 语义） | 一次性临时持仓的角色 |

**`morning` 模式不触发**: 估值分位 / 板块聚合（`sector_aggregator`）— 临时标的塞入会让宏观视图噪声变大。
**`close` 模式不触发**: premium / tech_indicator — premium 需要次日 open 数据；tech_indicator 跨时间窗。

### 错误处理 (Q5=A + Q10=B)

- 临时标的失败进 `errors_extra` 子列表（与主任务 `errors` 分离）
- 早报生成器优先展示 `errors_extra`（主人主动追加的，失败必须可见）
- 不发飞书 alert（避免和主任务告警混淆）

### 去重 (Q9=C)

临时标的与 `USER_HOLDINGS` / `ETF_WATCH_LIST` 重复时：
- **静默去重** + 一行 warn 日志（`logger.warning("extra-holdings: dedup 159530 (already in USER_HOLDINGS)`）
- 不报错，不覆盖

## 不做什么 (Q6)

- ❌ **不**写 sidecar JSON 文件持久化临时标的（"临时"是关键词；持久化应改 `USER_HOLDINGS`，单 commit 一 PR）
- ❌ **不**修改 `config.ETF_WATCH_LIST` / `config.USER_HOLDINGS`
- ❌ **不**自动推临时标的的估值 / 板块聚合
- ❌ **不**发飞书 alert

## 后果

### 优点
- 主框架零侵入：commit 1 / commit 2 完全独立，可在不动 collector_daily 的情况下合并
- 临时诉求走 CLI 一行，cron 可用
- 严格保留"临时"语义，避免双重权威源

### 缺点 / 后续待办
- sector 字段留空：早报板块结构对临时标的不可用 → 临时标的只能作为"独立条目"展示，不进板块聚合
- 冷启动依赖 `ak.fund_name_em()` 在线，akshare 源挂时临时标的拿不到 name（但 code 仍可用，落到 `name=""`）
- 当 sector 有更可靠数据源时，可扩展 `build_extra_holdings_set` 增加 sector 字段（**不**修改既有契约，只新增）

## 验证

- commit 1：`pytest tests/test_extra_holdings.py` — 11/11 绿
- commit 2：`pytest tests/test_extra_holdings_enrich.py` — mock akshare，验证缓存命中 / 未命中 / 过期三路径
- commit 3：手动 `python -m src.collector_daily --mode morning --extra-holdings '[{"code":"512480"}]'` 验证临时标的触发 premium + tech_indicator

## 引用

- Grill-me session 2026-08-20, Q1–Q15
- `docs/phase-2-followup.md` P2-1 黄金 / P2-2 持仓 / P2-3 估值分位（未动）