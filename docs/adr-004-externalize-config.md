# ADR-004: Externalize ETF watch-list configuration to JSON

> **状态**: Accepted (2026-08-21)
> **决策者**: 九节
> **背景**: quant-data 的 ETF 监控列表 hardcode 在 src/config.py 里,皮皮(data-collector agent)想调整监控标的必须改代码

## 背景

`src/config.py` 当前 167 行,4 个**标的列表**常量(ETF_WATCH_LIST / INDEX_WATCH_LIST / USER_HOLDINGS / SECTOR_MAPPING)是 hardcoded Python 列表/dict。

**真正痛点**:不是"格式",是**职责边界**:
- 皮皮(data-collector agent)是 quant-data 的**使用者**,她调整监控列表的需求合理且频繁
- 但当前她必须改 `src/config.py` → commit → push → cron restart → 等部署,**走完整 git 流程**
- 她其实不想碰代码,只想改数据
- 同时发现 cron prompt 里她硬编码了 5 持仓 + 4 观察标的,与 config.py 已有 drift(589020 / 561380 / 510230 / 159168 / 513980 都不在 config.py 里)

## 决策

**方案**:把 4 个标的列表常量外部化到 JSON 文件,皮皮通过 cron prompt 把文件路径传进来。

### 五步实施(垂直切片)

| Commit | 内容 | Seam |
|--------|------|------|
| 1 | `src/config_schema.py` + jsonschema 校验器 | JSON Schema + `validate_config()` |
| 2 | `src/config_loader.py` + 测试 | 文件 IO + 校验,返结构化 dict |
| 3 | `src/config.py` 加 `init_config(path)`,4 常量改为运行时加载 | `init_config()` |
| 4 | 本 ADR + DEPLOY.md 章节 | 文档 |
| 5 | `examples/etf_config.example.json` 种子 + `collector_daily --config PATH` | 入口闭环 |

### 关键决策点(Q11/Q12/Q13/Q14/Q19/Q20/Q22)

- **Q11-A**:**单文件分组**(`etf_config.json` 一个文件,4 个 top-level key)。比多文件更易管理,皮皮一次读全。
- **Q12-B**:Schema 允许**多余字段忽略**(top-level 和 entry 双层 `additionalProperties: True`)。皮皮可加 `_notes` 等不破坏 schema。
- **Q13-A**:**Fail-fast**。配置错 → 立即 raise ConfigLoadError → cron exit 非零 → 皮皮看到错误并修改 JSON。
- **Q14-A**:**启动时一次加载**,无运行时 reload。cron 用 isolated session,每次新进程自然 reload。weekly/monthly collector 同理(都是 isolated session)。
- **Q19-B**:**`--config <path>`** 长选项。和现有 `--extra-holdings`、`--mode` 风格一致。
- **Q20-B**:**不留 fallback**。配置错 = fail-fast。回滚靠 git revert,**不**在代码里留双源默认值。
- **Q21-B**:**手动创建 JSON**(不写一次性脚本)。`src/config.py` 顶部 docstring 写完整 JSON schema 文档,皮皮参考即可。
- **Q22-B**:既有的 `config.X` 引用**零改动**(属性查找语义保留);新增 `config_loader.py` / `config_init` 测试覆盖新功能。

### 范围边界(Q10)

**外部化**:`ETF_WATCH_LIST` / `INDEX_WATCH_LIST` / `USER_HOLDINGS` / `SECTOR_MAPPING`
**保持 config.py**: `DATA_DIR` / `SLOW_API_TIMEOUT` / `CACHE_TTL` / `VALIDATION_RULES`(基础设施/校验规则,非业务数据)

### 物理位置(Q5-A 推论)

**皮皮决定**,工具不挑。约定俗成参考位置:`/root/secureshare/files/ETF轮动分析框架/config/etf_config.json`,与 `data/` 并列。

## 后果

### 优点
- 皮皮调整监控标的:改 JSON → 下次 cron 自动加载(无需 git 流程)
- 单一权威源消除 cron prompt 与 config.py 的 drift
- 失败立即可见(fail-fast)
- schema 文档就写在 config.py 顶部 docstring(Q21-B)

### 缺点 / 后续待办
- config.py docstring 会随 schema 演化变长(Q21-B 的代价,可接受)
- `init_config()` 必须在 collector_daily 启动时调用一次(commit 5 落地)
- `extra-holdings` CLI 仍保留作为开发工具(Q9-A)

### 不做什么
- ❌ 不写 sidecar 同步机制(皮皮直接改 JSON 是 single source of truth)
- ❌ 不加 hot-reload(cron isolated session 已隐含 reload)
- ❌ 不留 fallback(Q20-B)
- ❌ 不把 DATA_DIR / VALIDATION_RULES 外部化(范围边界 Q10)

## 验证

- commit 1:`pytest tests/test_config_schema.py` — 21/21 绿
- commit 2:`pytest tests/test_config_loader.py` — 15/15 绿
- commit 3:`pytest tests/test_config_init.py` — 14/14 绿
- commit 5 完成后手动验证:运行 `collector_daily.py --config examples/etf_config.example.json --mode close`,确认启动时加载成功

## 引用

- Grill-me session 2026-08-20~21, Q1-Q23
- ADR-003 extra-holdings(同次决策的姊妹篇,先于 ADR-004)
- `docs/DEPLOY.md` §配置外部化(使用流程)
- `src/config.py` 顶部 docstring(schema 文档)