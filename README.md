# ETF Data Collection System (quant-data)

## 项目概述

ETF 数据自动化采集系统，支持日/周/月/季度多种频率的基金、指数、宏观数据采集。

## 项目结构

```
quant-data/
├── src/
│   ├── config.py           # 配置（ETF列表、API URL、缓存TTL、校验规则）
│   ├── logger.py           # 日志（log_collect / alert）
│   ├── storage.py          # 存储（CSV/JSON 读写 + partial rerun）
│   ├── validator.py        # 数据校验（5类校验 + 过期检查）
│   ├── akshare_client.py   # akshare 数据源（14个行情+宏观接口 + _with_cache）
│   ├── ttfund_client.py    # 天天基金 API（8个接口 + HTTP封装）
│   ├── collector_daily.py  # 日频采集器（close 15:30 / morning 08:00）
│   ├── collector_weekly.py # 周频采集器（周一 08:30）
│   ├── collector_monthly.py# 月频采集器（每月初）
│   ├── collector_quarterly.py # 季度采集器（季度末月 15日）
│   └── generate_quarterly_report.py # 季度报告生成器
├── tests/                  # 测试文件（TDD）
├── docs/
│   ├── SDD_Workflow_Log.md
│   └── ttfund_api_fields.md  # TTFUND API 字段映射
├── Dockerfile
└── docker-compose.yml
```

## 环境依赖

- Python 3.11+
- `requirements.txt` 中的依赖（akshare, requests, pandas, pydantic 等）

## 快速开始

### 本地开发

```bash
cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
pip install -r requirements.txt

# 运行日频采集（收盘）
python src/collector_daily.py --mode=close

# 运行日频采集（盘前）
python src/collector_daily.py --mode=morning

# 运行周频采集
python src/collector_weekly.py

# 运行月频采集
python src/collector_monthly.py

# 运行季度采集
python src/collector_quarterly.py

# 生成季度报告
python src/generate_quarterly_report.py
```

### Docker 运行

```bash
podman build -t quant-collector:latest .
podman-compose up -d
```

## 数据目录结构

```
/root/secureshare/files/ETF轮动分析框架/data/
├── daily/                  # 日频数据
│   ├── etf_snapshot_20260520.csv
│   ├── nav_510300_20260520.csv
│   └── north_flow_20260520.csv
├── weekly/                 # 周频数据
├── monthly/                # 月频数据
├── quarterly/              # 季度数据
├── cache/                  # API 缓存（akshare）
└── logs/
    ├── collect_YYYYMMDD.csv   # 采集日志
    └── alert_YYYYMMDD.csv     # 告警日志
```

## 配置

主要配置在 `src/config.py`：
- `ETF_WATCH_LIST`：监控的 ETF 列表（20只）
- `INDEX_WATCH_LIST`：监控的指数列表（20只）
- `CACHE_TTL`：API 缓存策略（19条规则）
- `VALIDATION_RULES`：数据校验规则（10条）

## 测试

```bash
cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
PYTHONPATH=. pytest tests/ -v
```

## SDD 流程

本项目遵循 Spec-Driven Development (SDD) 工作流：
- Step 1-4：PRD → Constitution → Plan → Task Breakdown
- Step 5-6：一致性审查
- Step 7：实施（21 Tasks，13 Stories）
- Step 8：验证交付

详见 `docs/SDD_Workflow_Log.md`。