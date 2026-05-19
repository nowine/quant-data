# Plan.md — ETF 数据采集系统

> SDD Development Plan | 基于 PRD + Constitution v0.2
> 版本：1.0-draft | 2026-05-20

---

## MVP-001: 公共基础模块

**Stories:** Story-001, Story-002, Story-003, Story-004, Story-005, Story-006
**Goal:** 构建所有采集脚本依赖的公共基础模块（配置、日志、存储、校验、数据客户端）
**Out of Scope:** 具体采集脚本实现、容器化

### Story-001: 配置中心 config.py

**Role:** 所有采集脚本
**Need:** 统一的配置管理（ETF列表、API配置、缓存策略、校验规则）
**Benefit:** 消除硬编码，所有模块共享同一份配置

**Acceptance Criteria (ACs):**
- [ ] AC-1: `config.py` 包含 `ETF_WATCH_LIST`（≥20只ETF，含 code/name/index）
- [ ] AC-2: `config.py` 包含 `INDEX_WATCH_LIST`（≥16只指数）
- [ ] AC-3: `config.py` 包含 `TTFUND_API_URL` 和 `TTFUND_APIKEY`（从环境变量读取）
- [ ] AC-4: `config.py` 包含 `CACHE_TTL` 字典（所有数据类型的 TTL 值）
- [ ] AC-5: `config.py` 包含 `VALIDATION_RULES`（所有数据的校验阈值）
- [ ] AC-6: `config.DATA_DIR` 指向 `/root/secureshare/files/ETF轮动分析框架/data`

**Technical Notes:**
- [ ] Backend: `src/config.py`
- [ ] Test: `tests/test_config.py`
- [ ] No hardcoded values anywhere in other modules

---

### Story-002: 日志与告警 logger.py

**Role:** 所有采集脚本
**Need:** 统一调用 `log_collect()` 和 `alert()`，输出结构化日志
**Benefit:** 每次采集可追溯，异常可告警

**Acceptance Criteria (ACs):**
- [ ] AC-1: `log_collect(task, source, status, rows, elapsed_sec, message)` 写入 `data/logs/collect_{YYYYMMDD}.csv`
- [ ] AC-2: `alert(level, message)` 写入 `data/logs/alert_{YYYYMMDD}.csv`，level 支持 `warn`/`error`
- [ ] AC-3: 日志每条记录包含 `run_id`（时间戳+随机字符串），同一次运行的所有日志共享同一 `run_id`
- [ ] AC-4: 日志编码为 UTF-8，无 BOM
- [ ] AC-5: 日志文件追加模式，不覆盖历史

**Technical Notes:**
- [ ] Backend: `src/logger.py`
- [ ] Test: `tests/test_logger.py`
- [ ] Regression: 现有的 Constitution 1.4 日志规范

---

### Story-003: 文件存储 storage.py

**Role:** 所有采集脚本
**Need:** 统一的文件读写接口，支持 partial rerun
**Benefit:** 数据文件格式一致，部分重跑不浪费 API 调用

**Acceptance Criteria (ACs):**
- [ ] AC-1: `save_csv(df, filepath)` — UTF-8 无 BOM，首行列名，无额外元数据行
- [ ] AC-2: `load_csv(filepath)` — 返回 DataFrame
- [ ] AC-3: `save_json(data, filepath)` — 写入 JSON
- [ ] AC-4: `load_json(filepath)` — 读取 JSON
- [ ] AC-5: `exists_today(filepath)` — 检查今日数据文件是否已存在且有效
- [ ] AC-6: `collect_if_missing(filepath, fetch_fn, *args)` — 核心 partial rerun 逻辑，已存在则读缓存，否则请求并存盘

**Technical Notes:**
- [ ] Backend: `src/storage.py`
- [ ] Test: `tests/test_storage.py`
- [ ] Regression: 现有的 Constitution 3.1-3.4 数据格式规范

---

### Story-004: 数据质量校验 validator.py

**Role:** 所有采集脚本
**Need:** 数据入库前校验，发现异常数据单独标记不污染原始文件
**Benefit:** 数据质量可追溯，异常数据不影响后续分析

**Acceptance Criteria (ACs):**
- [ ] AC-1: `validate(df, rules)` — 执行空值/范围/时效/完整性/一致性五类校验
- [ ] AC-2: `check_stale(filepath, max_age_hours)` — 检查缓存文件是否过期
- [ ] AC-3: 校验失败数据写入 `data/validate_failed/{date}.csv`，不影响原始数据
- [ ] AC-4: `ValidationResult(passed, warnings, errors)` 返回结构化结果
- [ ] AC-5: pydantic model 用于校验规则定义和输入校验

**Technical Notes:**
- [ ] Backend: `src/validator.py`
- [ ] Test: `tests/test_validator.py`
- [ ] Regression: 现有 Constitution 3.2 Schema 校验规范

---

### Story-005: AkShare 封装 akshare_client.py

**Role:** 采集脚本
**Need:** 统一封装 AkShare 调用，支持缓存/降级/partial rerun
**Benefit:** 慢接口不重复请求，降级链路清晰，partial rerun 生效

**Acceptance Criteria (ACs):**
- [ ] AC-1: 封装 `get_etf_snapshot()` → `fund_etf_category_sina()`，缓存当日
- [ ] AC-2: 封装 `get_north_flow(symbol, months)` → `stock_hsgt_hist_em()`，缓存7天
- [ ] AC-3: 封装 `get_etf_history(code)` → 首选 `fund_etf_hist_sina`，失败降级 `fund_etf_hist_em`
- [ ] AC-4: 封装 `get_etf_scale()` → `fund_etf_scale_sse()`，缓存7天
- [ ] AC-5: 封装 `get_margin_sh()` → `macro_china_market_margin_sh()`，缓存1天
- [ ] AC-6: 封装宏观接口：`get_pmi()`、`get_cpi()`、`get_ppi()`、`get_m2()`、`get_lpr()`、`get_shrzgm()`、`get_gdp()`、`get_industrial()`
- [ ] AC-7: 封装 `get_industry_alloc(year)` → `fund_portfolio_industry_allocation_em()`
- [ ] AC-8: 所有接口 `_with_cache()` 统一处理缓存（检查 TTL → 命中读缓存/否则请求并存）
- [ ] AC-9: 所有接口统一返回 pandas DataFrame 或 dict（符合接口冻结约定）

**Technical Notes:**
- [ ] Backend: `src/akshare_client.py`
- [ ] Test: `tests/test_akshare_client.py`（mock 测试，不依赖真实 API）
- [ ] Regression: Constitution 2.3 接口冻结约定

---

### Story-006: 天天基金 API 封装 ttfund_client.py

**Role:** 采集脚本
**Need:** 统一封装天天基金 8 个 skill API，支持 partial rerun
**Benefit:** API 调用频率可控，partial rerun 生效

**Acceptance Criteria (ACs):**
- [ ] AC-1: `get_fund_info(fcode)` → Skill `FUND_BASE_INFOS`
- [ ] AC-2: `get_nav_history(fund_id, range)` → Skill `FUND_NAV_INFO`
- [ ] AC-3: `get_index_info(index_id, scope)` → Skill `FUND_INDEX_INFO`
- [ ] AC-4: `get_holdings(fund_id, holding_type)` → Skill `FUND_HOLDING_INFO`
- [ ] AC-5: `search_funds(page, page_num, order)` → Skill `FUND_CONDITION_SELECT`
- [ ] AC-6: `get_manager_info(name)` → Skill `FUND_MANAGER_INFO`
- [ ] AC-7: `get_gold_info(scope)` → Skill `FUND_HUAAN_GOLD_INFO`
- [ ] AC-8: `get_strategy(name, scope)` → Skill `FUND_TG_STRATEGY_INFO`
- [ ] AC-9: 所有接口调用间隔 ≥1 秒（避免限流）
- [ ] AC-10: 所有接口统一返回 DataFrame 或 dict
- [ ] AC-11: `collect_if_missing()` 集成 partial rerun

**Technical Notes:**
- [ ] Backend: `src/ttfund_client.py`
- [ ] Test: `tests/test_ttfund_client.py`（mock 测试）
- [ ] Regression: Constitution 2.3 接口冻结约定

---

## MVP-002: 日度采集脚本

**Stories:** Story-007
**Goal:** 实现日度数据采集（交易日收盘后 + 每日早间），覆盖核心行情和宏观数据
**Out of Scope:** 周/月/季度采集，容器化

### Story-007: 日度采集 collector_daily.py

**Role:** Cron 调度 / 手动触发
**Need:** 每日自动采集 ETF 行情、融资融券、北向资金、黄金宏观、ETF净值、指数估值
**Benefit:** 为 LLM 分析和报告整理提供数据支撑

**Acceptance Criteria (ACs):**
- [ ] AC-1: `--mode=close` 采集 ETF 快照、融资融券、北向资金（交易日下午运行）
- [ ] AC-2: `--mode=morning` 采集黄金宏观指标（每日早间运行）
- [ ] AC-3: 遍历 `ETF_WATCH_LIST` 采集每只 ETF 净值 `get_nav_history()`
- [ ] AC-4: 遍历 `INDEX_WATCH_LIST` 采集每只指数估值 `get_index_info()`
- [ ] AC-5: 每日 08:00 运行 `--mode=morning`，15:30 运行 `--mode=close`（交易日）
- [ ] AC-6: partial rerun 生效：今日已成功的文件不重复请求 API
- [ ] AC-7: 每次采集输出汇总日志（成功率、各接口状态）
- [ ] AC-8: 单次日度采集总耗时 < 5 分钟

**Technical Notes:**
- [ ] Backend: `src/collector_daily.py`
- [ ] Test: `tests/test_collector_daily.py`（集成测试 + mock）
- [ ] Regression: 数据文件格式符合 Constitution 3.4 CSV 规范

---

## MVP-003: 周/月/季度采集脚本

**Stories:** Story-008, Story-009, Story-010
**Goal:** 完成周度、月度、季度数据采集，覆盖低频宏观和基金数据
**Out of Scope:** 容器化

### Story-008: 周度采集 collector_weekly.py

**Role:** Cron 调度 / 手动触发
**Need:** 每周日 20:00 采集 ETF 规模、基金排名、基金经理信息
**Benefit:** 周频数据支撑板块轮动分析

**Acceptance Criteria (ACs):**
- [ ] AC-1: 采集 ETF 规模/份额 `get_etf_scale()` → `weekly/etf_scale_{date}.csv`
- [ ] AC-2: 采集条件选基排名 `search_funds()` → `weekly/fund_rank_{date}.csv`
- [ ] AC-3: 采集重点基金经理信息 `get_manager_info()` → `weekly/manager_{name}_{date}.json`
- [ ] AC-4: partial rerun 生效
- [ ] AC-5: 周日 20:00 Cron 配置

**Technical Notes:**
- [ ] Backend: `src/collector_weekly.py`
- [ ] Test: `tests/test_collector_weekly.py`

---

### Story-009: 月度采集 collector_monthly.py

**Role:** Cron 调度 / 手动触发
**Need:** 每月1日 02:00 采集宏观月频数据和核心 ETF 持仓
**Benefit:** 月频宏观数据支撑长周期分析

**Acceptance Criteria (ACs):**
- [ ] AC-1: 采集 PMI/CPI/PPI/M2/LPR/SHRZGM/GDP/工业增加值/社融等宏观数据
- [ ] AC-2: 遍历 `ETF_WATCH_LIST` 采集持仓 `get_holdings()`
- [ ] AC-3: 慢接口（CPI/PPI/工业增加值约 20-40 秒）单独处理，不阻塞其他任务
- [ ] AC-4: partial rerun 生效
- [ ] AC-5: 每月1日 02:00 Cron 配置

**Technical Notes:**
- [ ] Backend: `src/collector_monthly.py`
- [ ] Test: `tests/test_collector_monthly.py`

---

### Story-010: 季度采集 collector_quarterly.py

**Role:** Cron 调度 / 手动触发
**Need:** 每季初1日 03:00 采集行业配置、投顾策略、持有人结构
**Benefit:** 季频数据支撑资产配置分析

**Acceptance Criteria (ACs):**
- [ ] AC-1: 采集行业配置 `get_industry_alloc(year)` → `quarterly/industry_alloc_{year}.csv`
- [ ] AC-2: 采集投顾策略 `get_strategy()` → `quarterly/strategy_{name}_{year}.json`
- [ ] AC-3: 采集持有人结构 `get_fund_info()` 提取持有人字段 → `quarterly/holder_structure_{code}_{year}.json`
- [ ] AC-4: partial rerun 生效
- [ ] AC-5: 每季初1日 03:00 Cron 配置

**Technical Notes:**
- [ ] Backend: `src/collector_quarterly.py`
- [ ] Test: `tests/test_collector_quarterly.py`

---

## MVP-004: 容器化与部署

**Stories:** Story-011, Story-012, Story-013
**Goal:** 项目容器化，支持一键部署和健康检查
**Out of Scope:** —

### Story-011: 容器化基础

**Role:** 部署工程师
**Need:** Dockerfile + docker-compose.yml，使服务可容器化运行
**Benefit:** 跨环境一致部署，依赖自包含

**Acceptance Criteria (ACs):**
- [ ] AC-1: `Dockerfile` 多阶段构建（builder + runner），非 root 用户，镜像 < 500MB
- [ ] AC-2: `.dockerignore` 排除 `__pycache__`、`.git`、`.env`、data 目录
- [ ] AC-3: `docker-compose.yml` 包含所有服务，日志目录挂载，环境变量注入
- [ ] AC-4: 健康检查端点 `GET /health`（所有 collector 支持 `--health` 参数）
- [ ] AC-5: 本地 `podman build` + `podman-compose up` 验证通过

**Technical Notes:**
- [ ] Config: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- [ ] Test: `tests/test_container.py`（smoke test）
- [ ] Regression: Constitution 10 容器化规范

---

### Story-012: Cron 配置

**Role:** 运维
**Need:** 四个采集脚本的 Cron 调度配置
**Benefit:** 自动定时运行，无需人工干预

**Acceptance Criteria (ACs):**
- [ ] AC-1: `collector_daily.py --mode=close` 交易日 15:30 Cron
- [ ] AC-2: `collector_daily.py --mode=morning` 每日 08:00 Cron
- [ ] AC-3: `collector_weekly.py` 每周日 20:00 Cron
- [ ] AC-4: `collector_monthly.py` 每月1日 02:00 Cron
- [ ] AC-5: `collector_quarterly.py` 每季初1日 03:00 Cron
- [ ] AC-6: Cron 配置文档化（Constitution 6 已包含此约定）

**Technical Notes:**
- [ ] Config: `crontab` 配置或 `docs/cron.md`
- [ ] Test: 手动验证 Cron 表达式正确性

---

### Story-013: 文档与验收

**Role:** 项目Owner/用户
**Need:** README + 部署说明 + 验收测试
**Benefit:** 新成员可快速上手，项目可移交

**Acceptance Criteria (ACs):**
- [ ] AC-1: `README.md` 包含项目结构、依赖安装、运行方式、Cron 配置
- [ ] AC-2: `requirements.txt` 包含所有 Python 依赖（akshare/pandas/requests/pydantic）
- [ ] AC-3: 验收标准逐项核对（PRD 第九章 8 条验收标准全部通过）
- [ ] AC-4: 所有制品（docs/、src/、tests/）commit 到 Git

**Technical Notes:**
- [ ] Docs: `README.md`, `docs/API_CONTRACT.md`（如有）
- [ ] Test: 8 条验收标准逐条验证

---

## Story 总览

| Story | MVP | Title | Status | Commits |
|-------|-----|-------|--------|---------|
| Story-001 | MVP-001 | 配置中心 config.py | `pending` | — |
| Story-002 | MVP-001 | 日志与告警 logger.py | `pending` | — |
| Story-003 | MVP-001 | 文件存储 storage.py | `pending` | — |
| Story-004 | MVP-001 | 数据质量校验 validator.py | `pending` | — |
| Story-005 | MVP-001 | AkShare 封装 akshare_client.py | `pending` | — |
| Story-006 | MVP-001 | 天天基金 API 封装 ttfund_client.py | `pending` | — |
| Story-007 | MVP-002 | 日度采集 collector_daily.py | `pending` | — |
| Story-008 | MVP-003 | 周度采集 collector_weekly.py | `pending` | — |
| Story-009 | MVP-003 | 月度采集 collector_monthly.py | `pending` | — |
| Story-010 | MVP-003 | 季度采集 collector_quarterly.py | `pending` | — |
| Story-011 | MVP-004 | 容器化基础 | `pending` | — |
| Story-012 | MVP-004 | Cron 配置 | `pending` | — |
| Story-013 | MVP-004 | 文档与验收 | `pending` | — |

---

## MVP 总览

| MVP | Title | Stories | Status |
|-----|-------|---------|--------|
| MVP-001 | 公共基础模块 | Story-001 ~ 006 | `pending` |
| MVP-002 | 日度采集脚本 | Story-007 | `pending` |
| MVP-003 | 周/月/季度采集脚本 | Story-008 ~ 010 | `pending` |
| MVP-004 | 容器化与部署 | Story-011 ~ 013 | `pending` |