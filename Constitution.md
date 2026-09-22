# Constitution.md — quant-data ETF 数据采集系统（升级版）

> SDD Constitution | 基于 PRD v1.1 升级需求清单
> 版本：0.2-upgrade | 2026-05-22

---

## 0. Meta

| Field | Value |
|-------|-------|
| Project | quant-data ETF 数据采集系统 |
| Base PRD | PRD_数据采集系统.md (v1.0, 已交付) |
| Upgrade PRD | /root/secureshare/files/ETF轮动分析框架/quant-data升级需求清单.md (v1.1) |
| Created | 2026-05-22 |
| Version | 0.2-upgrade |
| Mode | Quick Mode（主Agent直接执行） |

---

## 1. 开发方法论

### 1.1 TDD（强制）

| 规则 | 证据 |
|------|------|
| 每个公开函数先写失败测试再实现 | `git log` 显示 test commit 先于 feat commit |
| 所有公开接口有单元测试 | `pytest` 通过，业务逻辑覆盖率 ≥ 80% |
| 错误/降级路径有显式测试 | `test_*_error`、`test_*_fallback` 存在 |

### 1.2 版本控制

| 规则 | 证据 |
|------|------|
| 所有制品在 Git | 每个文件都有 commit |
| 每个 Task 独立分支 | `git branch -a` 显示 `feature/TASK-XXX-*` 模式 |
| Commit message 遵循 Conventional Commits | `feat:`、`fix:`、`test:`、`refactor:`、`docs:`、`chore:` |
| 不使用容器化 | 用户确认：直接运行脚本，无需 Docker/Podman |

### 1.3 定义完成

| 层级 | 完成意味着 |
|------|-----------|
| Task | 所有单元测试通过（`pytest`）|
| Story | 所有 AC 通过 + 代码已 commit |
| MVP | P0 所有 Story 完成 + 用户验收通过 |

---

## 2. 架构约束

### 2.1 模块职责

| 模块 | 职责 | 边界 |
|------|------|------|
| `src/config.py` | 配置中心（ETF列表、用户持仓、板块映射）| 不做数据采集 |
| `src/akshare_client.py` | AkShare API 封装（行情、宏观、美股等）| 只做 HTTP 调用，不做业务逻辑 |
| `src/ttfund_client.py` | 天天基金 Skill API 封装 | 只做 HTTP 调用，不做业务逻辑 |
| `src/collector_daily.py` | 日度采集编排器 | 调用各 client，按 mode 路由 |
| `src/collector_weekly.py` | 周度采集编排器 | 同上 |
| `src/collector_monthly.py` | 月度采集编排器 | 同上 |
| `src/tech_indicator.py` | 技术指标计算 | 纯计算，无 API 依赖 |
| `src/portfolio_calc.py` | 组合层面计算 | 纯计算，无 API 依赖 |
| `src/sector_aggregator.py` | 板块聚合 | 从 snapshot 聚合，不直接调 API |

### 2.2 数据格式

| 类型 | 格式 | 规范 |
|------|------|------|
| CSV 数据文件 | UTF-8 无 BOM，首行列名 | Constitution v0.2 3.4 |
| JSON 数据文件 | 缩进 2，UTF-8 | Constitution v0.2 3.5 |
| 日志文件 | CSV，追加模式，不覆盖 | Constitution v0.2 1.3 |

### 2.3 接口冻结约定

| 规则 | 说明 |
|------|------|
| 客户端接口签名不可随意变更 | 函数名、参数名、返回类型保持稳定 |
| 新增接口允许，删除/重命名需经用户确认 | 变更通过 Constitution change process |

---

## 3. P0 升级需求（本次实施范围）

### 3.1 config.py 更新

- [ ] `USER_HOLDINGS` 配置（用户持仓，与 ETF_WATCH_LIST 分开）
- [ ] `SECTOR_MAPPING` 配置（ETF代码→行业板块映射）
- [ ] `ETF_WATCH_LIST` 添加 159530、159934

### 3.2 新模块

| 模块 | 优先级 | 说明 |
|------|--------|------|
| `src/tech_indicator.py` | P0 | MA/ATR/RSI/量比，不持久化 |
| `src/sector_aggregator.py` | P0 | 板块聚合 + 排名 |
| `src/portfolio_calc.py` | P1 | 组合指标计算 |

### 3.3 akshare_client.py 扩展

| 接口 | 优先级 |
|------|--------|
| `get_us_stock_index()` | P0 |
| `get_fx_rate()` | P1 |
| `get_stock_board_industry()` | P1 |
| `get_futures_basis()` | P1 |
| `get_commodity_price()` | P1 |

### 3.4 collector 改进

| 改进项 | 优先级 |
|--------|--------|
| close 模式增加板块聚合 | P0 |
| morning 模式增加溢价折价率 | P0 |
| morning 模式增加技术指标 | P1 |
| close 模式增加美股数据 | P1 |

---

## 4. 变更管理

任何对本文档的变更需要：
1. 书面变更请求 + 理由
2. 用户审批
3. 版本号更新（如 0.2-upgrade → 0.3-upgrade）

---

## 5. 已知 TBD（已澄清）

| ID | 问题 | 结论 |
|----|------|------|
| TBD-001 | tech_indicator 依赖的历史行情接口 | 使用 `ak.fund_etf_hist_em(symbol, period, start_date, end_date, adjust)` |
| TBD-002 | morning 模式溢价率数据缺失时行为 | 正常报错并跳过，注释提醒用户应先跑 close 模式 |