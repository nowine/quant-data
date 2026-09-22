# Phase 2 Follow-up — akshare 数据缺口回填

> 来源: 2026-08-19 ~ 08-20 ttfund_client → akshare_client 迁移讨论
> 触发: ttfund_client 被 akshare_client 完全替代,但三块高频数据在 akshare 中**没有直接对应接口**,目前以 stub 形式保留函数签名与返回结构(返回空 dict / 空列表)。

---

## 背景

`src/akshare_fund_client.py` 完全替代 `src/ttfund_client.py`。8 个公开函数签名 100% 保持,调用方零改动。其中:

- **3 个真实实现** — `get_nav_history` / `get_fund_info` / `get_index_info`(基础点位部分)
- **3 个 stub** — `get_gold_info` / `get_holdings` / `get_strategy`(完整 stub,无 akshare 替代)
- **2 个未调用但 stub 保留** — `search_funds` / `get_manager_info`

下文是 Phase 2 要解决的实际数据缺口。

---

## P2-1: 黄金行情数据 (Phase 2 优先级 🔴 高)

**函数:** `get_gold_info(scope="all")` — 现为 stub,返回空 dict。

**数据缺口:**
| scope | 原 ttfund 提供 | 用途 | 当前状态 |
|-------|--------------|------|----------|
| `gold` | 国内黄金 ETF 价格、上海金、伦敦金、美元指数 | 用户持仓 `518880/159934` 板块行情 | stub 空数据 |
| `macro` | 黄金 ETF 总规模、央行储备 | 宏观背景 | stub 空数据 |
| `risk` | 黄金波动率/与股债相关性 | 资产配置参考 | stub 空数据 |

**用户持仓影响:**
- `collector_daily.py:503` 调 `get_gold_info("all")`,失败时只影响"黄金板块行情聚合",核心 ETF 报价和溢价率**不受影响**。
- `USER_HOLDINGS` 里有 `159934`(黄金 ETF 易方达),缺数据会让"早报板块结构"看起来不完整。

**Phase 2 候选方案(待评估):**
1. **新浪财经黄金行情** — `hq.sinajs.cn` 接口,公开,无 key,字段齐全
2. **akshare 拼凑** — `ak.spot_golden_benchmark_sge()`(上海金)+ `ak.foreign_bond_yield()` 旁路
3. **爬雪球黄金 ETF 行情** — 已有 `ak.fund_etf_fund_info_em` 拿 518880/159934 净值
4. **直接放弃** — 早报里写"黄金板块数据暂不可用"

**建议:** 方案 3 + 1 组合。先用 `fund_etf_fund_info_em` 覆盖用户持仓的两个黄金 ETF,宏观部分走新浪。

---

## P2-2: 单只基金持仓查询 (Phase 2 优先级 🟡 中)

**函数:** `get_holdings(fund_id, holding_type="all")` — 现为 stub,返回 `{"datas": []}`。

**数据缺口:**
akshare 提供的 `fund_report_stock_cninfo(date="XXXX0331")` 是**全市场所有基金的重仓股**,不是按单只基金查持仓。

**用途:**
- `collector_quarterly.py:62` 调 `get_holdings(code, "all")`,季度收集
- 用于"持仓透明度"分析(基金前十大重仓股、债券持仓、行业分布)

**影响:**
- 季度报告里"持仓结构"维度会缺失
- 核心数据(基金净值/规模/收益率)**不受影响**

**Phase 2 候选方案:**
1. **东财基金持仓季报** — 拼 `fundf10.eastmoney.com/ccmx_{fundcode}.html` HTML,字段规范
2. **akfund/zhifu 第三方** — 找付费或限速接口
3. **爬天天基金原页面** — `fundf10.eastmoney.com/ccmx_{fundcode}.html`,已确认字段一致
4. **降级为指数成分股** — 只跟踪 INDEX_WATCH_LIST 成分股变化代替基金持仓

**建议:** 方案 3,直接爬天天基金原页面(数据源本身就是去财,合法合规)。接口契约不变。

---

## P2-3: 指数估值分位 (Phase 2 优先级 🟡 中)

**函数:** `get_index_info(index_id, scope="all")` — 现 stub,只返回基础点位,估值字段缺失。

**数据缺口:**
| 字段 | 原 ttfund 提供 | akshare 等价 | Phase 2 解决方案 |
|------|--------------|-------------|------------------|
| 指数点位 | ✅ 有 | `ak.stock_zh_index_daily()` 可算 | (已在 stub 提供基础版本) |
| PE_TTM | ✅ 有 | ❌ 无 | 需爬 index?q=市盈率(中证指数官网) |
| PB | ✅ 有 | ❌ 无 | 同上 |
| PE 百分位(近 5/10 年) | ✅ 有 | ❌ 无 | 历史 PE 序列 → 百分位 |
| 成分股权重 | ✅ 有 | 部分(中证指数官网) | `ak.index_stock_cons_weight_csindex()` 仅限中证系列 |

**用途:**
- `collector_quarterly.py:100` 调 `get_index_info(idx, "all")`,季度收集
- 用于"指数估值轮动"分析: PE 百分位 < 30% 视为低估区间

**影响:**
- 季度报告"指数估值表"维度会缺失(只剩点位)
- 但**不影响 ETF 净值/价格/溢价率数据流**

**Phase 2 候选方案:**
1. **中证指数官网爬虫** — `csindex.com.cn` 公开数据,PE/PB 历史可下
2. **国证指数(深市)** — 类似公开 API
3. **第三方 Wind/聚宽付费** — 工作量重
4. **定期爬历史快照 → 本地算分位** — 数据源全自管,无需每次计算时联网

**建议:** 方案 4。一次性爬近 10 年 PE/PB 快照存本地,后续只算 percentile。接口契约保留 `pe_percentile` 字段。

---

## 整体原则

1. **接口契约不变** — 三个 stub 函数的签名/返回结构都已冻结,Phase 2 实现必须 100% 兼容
2. **调用方零改动** — collector / report generator 一行不动
3. **缓存策略沿用** — CACHE_TTL 中 `gold_info: 168h` / `holdings: 720h` / `index_valuation: 168h` 已就位
4. **数据源优先级** — 公开免费 > 付费 > 爬虫,避免重蹈 ttfund 失效覆辙

---

## 验收标准

Phase 2 完成 = 三块 stub 函数都返回真实数据,且 `pytest` 全绿(包含 `test_akshare_fund_client.py` 中 stub 标记为 `@pytest.mark.phase2` 的用例,Phase 2 完成后取消标记)。

---

_创建: 2026-08-20 — 配合 src/akshare_fund_client.py 替换 src/ttfund_client.py_