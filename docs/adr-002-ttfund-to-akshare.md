# ADR-002: ttfund_client → akshare_fund_client 迁移

> **状态**: Accepted (2026-08-20)
> **决策者**: 九节
> **背景**: 天天基金 Skills API 失效风险 + 无备用 key 通道

## 背景

原 `src/ttfund_client.py` 依赖 `skills.tiantianfunds.com` 网关 + `TTFUND_APIKEY` 环境变量:

| 风险 | 影响 |
|------|------|
| 网关失效 / 限速 / 鉴权失败 | ETF 净值、持仓、估值分位三大数据全部断流 |
| 鉴权 key 单一来源 | 唯一密钥在 `.env`,一旦泄露/失效,在新平台申请流程繁琐 |
| 字段规范强耦合 | 拼音首字母 (`DWJZ/LJJZ/JZZZL`) 写死在 collector 里 |

`akshare` 是开源、公开的金融数据聚合库,东方财富网底层数据,字段虽不同但覆盖率足够。

## 决策

**方案 A**: 用 `akshare_fund_client.py` 替代 `ttfund_client.py`,**保留 ttfund 公开 API 签名**,通过 shim 内部将 akshare DataFrame 翻译成 ttfund 字段命名。让所有 collector / report generator **零代码改动**。

### 函数实现矩阵

| ttfund 函数 | akshare 替代 | 实现状态 |
|------|------|------|
| `get_nav_history(fund_id, range)` | `ak.fund_open_fund_info_em(indicator="单位净值走势")` | ✅ 真实实现 |
| `get_fund_info(fcode)` | `ak.fund_individual_basic_info_xq()` | ✅ 真实实现 |
| `get_index_info(index_id, scope)` | 部分(`stock_zh_index_daily`) | 🟡 partial stub (PE/PB 待 P2) |
| `get_gold_info(scope)` | ❌ akshare 无对应 | ⚪ stub (P2-1) |
| `get_holdings(fund_id, type)` | ❌ akshare 只有全市场口径 | ⚪ stub (P2-2) |
| `get_strategy(name, scope)` | ❌ akshare 无对应 | ⚪ stub |
| `search_funds(...)` | ❌ 暂无 | ⚪ stub (compat) |
| `get_manager_info(name)` | ❌ 暂无 | ⚪ stub (compat) |

### 关键设计点

1. **字段桥接**: `get_nav_history` 返回嵌套 `{"data": {"nav_history": {"items": [{"FSRQ", "DWJZ", "JZZZL", "LJJZ", "NAVTYPE", "RATE"}]}}}` 形态,内部分两步翻译:
   - akshare df 列 → 拼音首字母键
   - **akshare 是 oldest-first,shim 内 `df.iloc[::-1]` 反转为 newest-first**,确保 `items[0]` 是最新值(原 ttfund 契约)

2. **真接口验证 (关键)**: 实测 `fund_open_fund_info_em("510300", "1年")` 返回 3475 条历史,`items[0].DWJZ` = 4.6502(2026-08-19),与 collector 解构路径完全兼容。

3. **Stub 契约**: `get_gold_info/get_holdings/get_strategy` 返回 `{}` / `{"datas": []}`,调用方原本就处理空数据,不报错。stub 触发 WARNING 级日志,指向 `docs/phase-2-followup.md` 哪一阶段。

4. **删除内容**:
   - `src/ttfund_client.py` (298 行)
   - `tests/test_ttfund_client.py` / `test_ttfund_api.py` / `test_ttfund_field_mapping.py` (1033 行)
   - `config.TTFUND_API_URL` / `config.TTFUND_APIKEY`
   - `.env` 中的 `TTFUND_APIKEY`(运维清理,不属于此 PR)

## 替代方案

- **方案 B**: 重写所有调用方,直接用 `ak.fund_*` 系列,清爽但需要更新 4 个 collector 文件 + 多个测试 + 报告生成器,工作量为本方案的 3-4 倍。
- **方案 C**: 寻找其他付费 API (Wind/聚宽),引入新的供应商风险与成本,得不偿失。

## 后果

- **正向**: `TTFUND_APIKEY` 从秘密中移除,.env 简化;akshare 公开 API,失效风险低;数据源单点故障消除
- **代价**: 三大功能 stub 化(get_gold_info / get_holdings / get_index_info 部分),报告里"黄金板块"/"基金持仓"/"估值分位"维度暂时缺失,需 Phase 2 回填
- **运维**: 调用方零变更,部署包无新增依赖(akshare 已在 requirements.txt)

## 验证

- 迁移后 61 passed / 3 skipped (Phase 2 标记)
- `get_nav_history("510300")` 真实 akshare 调用验证
- `test_collector_quarterly.run_quarterly` 完整跑通,验证 stub 数据流不破坏下游
- `test_morning_mode` 等 4 个早先慢测试,通过补 `get_etf_history` mock 从 31s → 0.62s

## 后续

`docs/phase-2-followup.md` 列出三个 stub 的具体回填方案,作为下一期开发主线。