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

## 配置外部化 (2026-08-21 起生效)

**背景**:quant-data 的 4 个 ETF 监控列表常量 (ETF_WATCH_LIST / INDEX_WATCH_LIST / USER_HOLDINGS / SECTOR_MAPPING) 原本 hardcode 在 `src/config.py`,皮皮 (data-collector agent) 调整监控标的必须改代码、走 git 流程。现已外部化到 JSON,详见 ADR-004。

### 皮皮怎么用

**Step 1**:创建/编辑 `etf_config.json` (路径由你定,推荐 `/root/secureshare/files/ETF轮动分析框架/config/etf_config.json`):

```json
{
  "etf_watch_list": [
    {"code": "510300", "name": "沪深300ETF华泰柏瑞", "index": "沪深300"}
  ],
  "user_holdings": [
    {"code": "159530", "name": "机器人ETF易方达", "sector": "机器人"}
  ],
  "index_watch_list": ["沪深300", "中证500"],
  "sector_mapping": {
    "机器人": ["159530"],
    "宽基": ["510300", "510500"]
  }
}
```

- 所有 4 个 top-level key 都是**可选**;空文件 `{}` 也合法 (会得到 4 个空列表)
- 每个 entry 的 `code` 必须是 6 位数字字符串,`name` 不能为空,`index` / `sector` 必填
- 多余字段 (如 `notes`、`added_at`) 会被忽略,不会报错
- 完整 schema 参考 `src/config.py` 顶部 docstring 或 `src/config_schema.py::ETF_CONFIG_SCHEMA`

**Step 2**:在 cron prompt / 命令里把路径传给 collector:

```bash
cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
export PYTHONPATH=.
python3 src/collector_daily.py --mode=morning --config /root/secureshare/files/ETF轮动分析框架/config/etf_config.json
```

**Step 3**:下次 cron 自动加载新 JSON(每次 isolated session 重新读文件)。

### cron prompt 改造示例

**改前** (皮皮在 prompt 里硬编码标的):

```
## 持仓
- 159530 机器人ETF
- 588750 芯片ETF

## 执行
python3 src/collector_daily.py --mode=morning
```

**改后** (标的走 JSON,皮皮只维护路径):

```
## 持仓
- 参考配置: /root/secureshare/files/ETF轮动分析框架/config/etf_config.json

## 执行
python3 src/collector_daily.py --mode=morning \
  --config /root/secureshare/files/ETF轮动分析框架/config/etf_config.json
```

### 故障排查

| 症状 | 原因 | 修复 |
|------|------|------|
| `ConfigLoadError: etf_config.json not found` | 路径不对或文件不存在 | 检查 `--config` 参数 + 文件存在 |
| `etf_config.json failed schema validation` | JSON 不符合 schema | 看错误信息里的路径 (如 `etf_watch_list[3].code`),改对应 entry |
| cron exit code 非零,但没有输出 | JSON 解析失败 | 用 `python3 -m json.tool <path>` 验证 JSON 语法 |
| 启动后采集到的列表是空的 | JSON 里某个 key 漏写 | 检查 4 个 top-level key 名字拼写 |

### 回滚

如果新版配置系统出问题,回滚靠 git revert (config.py 在 commit `334717b` 之前是 hardcoded):

```bash
git revert 334717b 9657c73 4da4572
# 然后删掉 collector_daily 的 --config 参数
```

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