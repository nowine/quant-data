# `etf_config.json` 操作手册

> **给**: 皮皮（data-collector agent）和任何想调整 ETF 监控清单的人
> **不是给**: 想了解 ADR 决策背景的人 → 看 [`adr-004-externalize-config.md`](adr-004-externalize-config.md)
> **目标**: 10 分钟搞清楚怎么改、怎么验证、哪里会错

---

## 0. 一句话总结

`etf_config.json` 是一份 **4 个字段的 JSON 文件**，告诉 4 个 collector（daily/weekly/monthly/quarterly）监控哪些标的。改 JSON，**不动代码、不走 git**，下次 cron 自动加载（每个 cron 是 isolated session，进程重启自然 reload）。

---

## 1. 文件在哪？

**约定俗成位置**：
```
/root/secureshare/files/ETF轮动分析框架/config/etf_config.json
```

为什么放这：跟 `data/` 并列，都属于 ETF 轮动分析框架的数据根目录。如果你想放别处也行 —— 路径是 collector 的 `--config` 参数，**调用方定**。

---

## 2. 复制模板

第一次部署：
```bash
cp projects/quant-data/examples/etf_config.example.json \
   /root/secureshare/files/ETF轮动分析框架/config/etf_config.json
```

`examples/etf_config.example.json` 是权威种子文件（每次 ADR-004 改动都会同步更新）。

---

## 3. 4 个字段是什么？

| 字段 | 类型 | 必填？ | 用途 | 谁会改 |
|---|---|---|---|---|
| `etf_watch_list` | array of `{code, name, index}` | 否 | **22 只核心 ETF**的快照/行情采集源 | 加新观察标的 |
| `user_holdings` | array of `{code, name, sector}` | 否 | **当前持仓**，跑溢价率/技术指标/组合分析 | 调仓后改 |
| `index_watch_list` | array of string | 否 | **指数名称**，季度估值分位采集 | 增删指数 |
| `sector_mapping` | object `{sector: [code]}` | 否 | 行业→ETF 映射，给板块聚合器用 | 加新板块 |

**全部字段都可选**。缺哪一项，代码 fallback 到空列表（不是 fallback 到旧硬编码常量）。

---

## 4. 持仓 vs 观察标的：怎么放？

**关键认知**：
- **`user_holdings`** = 我现在持有 → 触发溢价率/技术指标/组合分析（每个交易日跑）
- **`etf_watch_list`** = 我想看行情 → 触发 ETF 快照/历史价格（采集全市场数据）
- **观察但还没买的标**（如 159611/510230/159168/513980）→ 放 `etf_watch_list`，**不放** `user_holdings`

**允许重叠**（如 159530 同时在两个列表）。**重叠是有意的**，不是 bug：
- `etf_watch_list` 里的 159530 → 走 ETF 快照采集
- `user_holdings` 里的 159530 → 走溢价率 + 技术指标计算
- 两个计算路径独立，互不冲突

---

## 5. 必填字段速查

每个 entry 都有最低要求。改错会报 schema 错。

### `etf_watch_list[].entry` 必填：
- `code`: 6 位数字 ETF 代码，**字符串**（不是整数！写 `"159530"`，不要写 `159530`）
- `name`: 标的名称，**非空字符串**
- `index`: 该 ETF 跟踪的指数名（如 "沪深300"），**非空字符串**
- 额外字段允许（如 `notes`, `added_at`），会被忽略

### `user_holdings[].entry` 必填：
- `code`: 6 位数字 ETF 代码，**字符串**
- `name`: 标的名称，**非空字符串**
- `sector`: 板块名（必须能在 `sector_mapping` 找到对应键），**非空字符串**
- 额外字段允许

### `index_watch_list[]`：
- 元素是非空字符串（指数名）
- 建议从 etf_watch_list 已有 `index` 字段里挑，保证能 join

### `sector_mapping`：
- key: 板块名（**非空字符串**）
- value: 6 位数字 ETF 代码的 **数组**

---

## 6. 改完怎么验证？

### 6.1 手动跑一次最轻量的 collector（推荐）

```bash
cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
export PYTHONPATH=.
python3 src/collector_weekly.py --config /root/secureshare/files/ETF轮动分析框架/config/etf_config.json
```

为什么 weekly：daily 太重（采集全市场），monthly 调多个远程 API，quarterly 只在特定日跑。**weekly 跑 1 次 = 22 + 5 + 7 ≈ 34 次远程调用，2 分钟内出结果**，且任何交易日都能跑（虽然周一才有完整数据，其他日只是 date guard）。

成功的样子：
```
Today (YYYY-MM-DD) is not Monday — weekly collector should run on Mondays only.
```
**或**（周一跑）：
```
Running weekly collector...
Done: X/Y tasks succeeded.
```

**没跑数据不代表改坏了** —— date guard 可能拦截。检查 6.2。

### 6.2 真接口加载验证（最快）

```bash
cd /root/.openclaw/workspace-agents/fullstack-engineer/projects/quant-data
export PYTHONPATH=.
python3 -c "
from src.config import init_config, ETF_WATCH_LIST, USER_HOLDINGS, INDEX_WATCH_LIST, SECTOR_MAPPING
init_config('/root/secureshare/files/ETF轮动分析框架/config/etf_config.json')
print(f'etf_watch_list: {len(ETF_WATCH_LIST)}')
print(f'user_holdings: {len(USER_HOLDINGS)}')
print(f'index_watch_list: {len(INDEX_WATCH_LIST)}')
print(f'sector_mapping: {len(SECTOR_MAPPING)}')
print(f'user_holdings codes: {[h[\"code\"] for h in USER_HOLDINGS]}')
"
```

成功：4 行数字 + 持仓代码列表，与你期望的一致。

### 6.3 错误时怎么办？

**schema 错误**（最常见）：
```
[FATAL] etf_config.json failed schema validation: /path/to/etf_config.json
etf_config.json schema validation failed:
  - user_holdings[0]: 'sector' is a required property
  - index_watch_list[3]: '' is too short
```

修法：看 `path[index]: 错误描述`，对应位置找到 entry 补字段。**重新保存后下次 cron 自动生效**。

**文件不存在**：
```
[FATAL] etf_config.json not found: /path/to/etf_config.json
  hint: pass --config <path-to-etf_config.json> to the collector.
```

修法：从 `examples/etf_config.example.json` 复制一份到目标路径。

**JSON 语法错**：
```
[FATAL] etf_config.json is not valid JSON: /path/to/etf_config.json
...
```

修法：用 `python3 -m json.tool /path/to/etf_config.json` 检查语法。

---

## 7. 跟 cron prompt 的关系

**改 JSON 不需要改 cron prompt**（只要路径不变）。如果路径变了：
- 4 个 cron job 都要改 `message` 字段里的 `--config` 参数
- 改完用 `openclaw cron list` 确认
- 失败兜底：`openclaw cron update <id> --enabled=false`

---

## 8. 跟 git 的关系

**JSON 文件本身不提交到 git**（皮皮的业务数据，不是代码）。`.gitignore` 已配。

如果你想给 schema 改默认值 → 改 `examples/etf_config.example.json`（提交到 git），那是**所有人**的种子。

---

## 9. 改完没生效？

检查 3 件事：
1. **JSON 文件保存了吗？** `cat /path/to/etf_config.json` 看时间戳
2. **路径对吗？** 重新跑 6.2，看 `init_config` 加载的是不是同一个文件
3. **cron 是新进程吗？** OpenClaw cron 都是 isolated session，每次是新进程 → 每次都重新读 JSON

如果是 `--config` 参数写错路径 → cron 会立刻 exit 1 并发飞书 alert 给你（MEMORY #13 教训）。

---

_最后更新: 2026-08-22 00:55 — ADR-004 收尾时同步写_
