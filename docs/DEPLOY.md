# ETF Quant Data — 部署指南

> **状态**: 2026-08-20 — Phase 1 迁移后更新
> **场景**: 本项目**不使用 Docker / podman 部署**,而是通过 OpenClaw cron
> 在 host 上直接运行 `collector_daily.py`。

## 当前部署架构

```
┌────────────────────────────────────────────────────┐
│  OpenClaw cron (data-collector agent)              │
│  ├── 早报  07:00 Asia/Shanghai  cron 0 7 * * 1-5  │
│  ├── 晚报  21:30 Asia/Shanghai  cron 30 21 * * 1-5 │
│  ├── 周报  11:00 周日          cron 0 11 * * 0    │
│  └── 月报  00:01 每月1日       cron 1 0 1 * *    │
└────────────────────────────────────────────────────┘
                       │
                       │  Step 1: python3 collector_daily.py --mode=morning
                       ▼
┌────────────────────────────────────────────────────┐
│  /root/.openclaw/workspace-agents/                 │
│    fullstack-engineer/projects/quant-data/         │
│  ├── src/collector_daily.py      # morning/close   │
│  ├── src/collector_weekly.py                       │
│  ├── src/collector_monthly.py                      │
│  ├── src/collector_quarterly.py                    │
│  └── src/akshare_fund_client.py  # NAV 数据源      │
└────────────────────────────────────────────────────┘
                       │
                       │  CSV/JSON 落盘
                       ▼
┌────────────────────────────────────────────────────┐
│  /root/secureshare/files/                          │
│    ETF轮动分析框架/data/{daily,weekly,monthly}/    │
│  数据被皮皮 (deepseek-v4-pro) 在 Step 2-6 读取,    │
│  生成报告写入 {YYYY-MM}/{YYYY-MM-DD}-早报.md 等。  │
└────────────────────────────────────────────────────┘
```

## 关键 cron 配置

| Job ID | 名称 | Schedule | 备注 |
|--------|------|----------|------|
| `6ac0c6fc-...` | ETF早报生成 | `0 7 * * 1-5` Asia/Shanghai | `--mode=morning` |
| `07f8bc86-...` | ETF晚报生成 | `30 21 * * 1-5` Asia/Shanghai | `--mode=close` |
| `aa7da85c-...` | ETF周报生成 | `0 11 * * 0` | |
| `b87d876a-...` | ETF月报生成 | `1 0 1 * *` | |

**查看**:`openclaw cron list`
**单次手动跑**:`openclaw cron run <job-id>`
**历史 runs**:`ls /root/.openclaw/cron/runs/<job-id>.jsonl | tail`

## 代码变更后的发布流程 (重要)

> ⚠️ **不要假设 OpenClaw 会自动看到代码变更**。
> host 上的 `python3 src/collector_daily.py` 直接读工作区代码,
> 不存在镜像构建/容器重启步骤 — 但**数据文件输出目录**是固定的。

按 **MEMORY.md #7** 的纪律:

1. **git commit & push** — 改动要落库,即便 host 上立即生效
2. **手动验证端到端** — 不要等 cron 自动触发:

   ```bash
   cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
   export PYTHONPATH=.
   # 清理今日缓存,确保走真实代码路径
   rm -f /root/secureshare/files/ETF轮动分析框架/data/daily/*_{YYYY-MM-DD}.{csv,json}
   python3 src/collector_daily.py --mode=morning
   # 检查输出
   ls -la /root/secureshare/files/ETF轮动分析框架/data/daily/*_{YYYY-MM-DD}.*
   ```

3. **失败兜底** — 如果手动跑挂,**禁用 cron job**:
   ```bash
   openclaw cron update <job-id> --enabled=false
   ```
   修复后重新开启。

## 容器 vs 直接运行的注意事项

项目里有 `Dockerfile` / `docker-compose.yml`,但**当前未使用**。
它们是历史遗留,**不要重新启用**,原因:
- akshare 在容器内访问东方财富/新浪等源可能受 DNS 限制
- 直接跑 python 调试方便
- 容器化会引入额外的镜像构建/缓存/僵尸状态问题 (见 MEMORY #16)

如果未来要启用 docker:
- 必须删掉 `docker-compose.yml` 中的 `TTFUND_APIKEY` 环境变量 (已 2026-08-20 清理)
- 必须把 akshare 容器 DNS 配好 (docker network dns 8.8.8.8)
- 验证 `python3 -c "import akshare; akshare.fund_open_fund_info_em('510300', indicator='单位净值走势')"`

## 数据目录约定

| 路径 | 内容 | 写入者 |
|------|------|--------|
| `/root/secureshare/files/ETF轮动分析框架/data/daily/` | 每日 CSV/JSON | collector_daily |
| `/root/secureshare/files/ETF轮动分析框架/data/weekly/` | 每周快照 | collector_weekly |
| `/root/secureshare/files/ETF轮动分析框架/data/monthly/` | 月度快照 | collector_monthly |
| `/root/secureshare/files/ETF轮动分析框架/data/logs/` | 采集日志 | logger.py |
| `/root/secureshare/files/ETF轮动分析框架/{YYYY-MM}/` | 报告输出 | 皮皮 agent |

## 关键故障排查

| 现象 | 检查项 |
|------|--------|
| 早报/晚报缺失 | `openclaw cron list` 看 job status, `ls -la /root/.openclaw/cron/runs/<job-id>.jsonl \| tail` |
| NAV 数据缺失 | 跑 `python3 -c "from src.akshare_fund_client import get_nav_history; print(get_nav_history('510300')['data']['nav_history']['items'][:3])"` |
| 数据目录空了 | 检查 `/root/secureshare/files/ETF轮动分析框架/data/` 是否还挂载, SecureShare 容器是否在跑 |
| TTFUND 引用 | **不应再有**; 如 grep 命中 → 检查 `docs/adr-002-ttfund-to-akshare.md` 是否完整 |

## 版本历史

- **2026-08-20** — Phase 1: ttfund_client → akshare_fund_client 迁移 (`8e11d86`)
- **2026-08-20** — Phase 1.1: load_csv 代码列 str/int 修复 (`80e5c47`)
- **更早** — TTFUND_APIKEY 配置模式 (已废弃,见 ADR-002)