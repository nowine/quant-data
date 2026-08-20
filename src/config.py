"""Configuration for ETF Data Collection System.

Two kinds of configuration live here:

1. **Hard-coded infrastructure constants** — paths, timeouts, validation
   thresholds. These never change at runtime and live in this file for IDE
   autocomplete / type safety. Includes: DATA_DIR, SLOW_API_TIMEOUT, CACHE_TTL,
   VALIDATION_RULES.

2. **Externalized ETF watch-list constants** — 皮皮 (data-collector agent) is
   the only operator who edits these in production. They default to the
   values below at import time (back-compat for tests / single-file scripts),
   but are REPLACED at runtime by `init_config(path)` when the collector
   loads etf_config.json. Includes: ETF_WATCH_LIST, INDEX_WATCH_LIST,
   USER_HOLDINGS, SECTOR_MAPPING.

See ADR-004 (docs/adr-004-externalize-config.md) for the full rationale.

────────────────────────────────────────────────────────────────────────────────
JSON SCHEMA (etf_config.json) — single source of truth lives in src/config_schema.py
────────────────────────────────────────────────────────────────────────────────

Top level: a JSON object. All four keys are OPTIONAL; missing keys default to
empty containers. Extra top-level keys are silently ignored.

  {
    "etf_watch_list": [
      { "code": "510300", "name": "沪深300ETF华泰柏瑞", "index": "沪深300" }
      // required: code (6-digit str), name (non-empty str), index (non-empty str)
      // extra fields allowed (e.g. notes, added_at) and ignored
    ],
    "user_holdings": [
      { "code": "159530", "name": "机器人ETF易方达", "sector": "机器人" }
      // required: code, name, sector; extra fields ignored
    ],
    "index_watch_list": ["沪深300", "中证500", ...],  // non-empty strings
    "sector_mapping": {
      "机器人": ["159530"],
      "宽基": ["510300", "510500", ...]
      // keys: sector names; values: arrays of 6-digit codes
    }
  }

Schema is enforced by src/config_schema.validate_config (Draft 2020-12).
Validation errors include the JSON-pointer path so 皮皮 can fix the file
without reading code.
"""

import os

# Load .env for cron/isolated environments where system env vars may be absent
try:
    from dotenv import load_dotenv
    from pathlib import Path as _Path
    _env_file = _Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=True)
except ImportError:
    pass

# =============================================================================
# ETF Watch List — 22 core ETFs for rotation analysis
# =============================================================================
ETF_WATCH_LIST = [
    # 宽基
    {"code": "510300", "name": "沪深300ETF华泰柏瑞", "index": "沪深300"},
    {"code": "510500", "name": "中证500ETF华夏", "index": "中证500"},
    {"code": "159915", "name": "创业板ETF易方达", "index": "创业板指"},
    {"code": "588000", "name": "科创50ETF华夏", "index": "科创50"},
    {"code": "510050", "name": "上证50ETF华夏", "index": "上证50"},
    # 半导体/芯片
    {"code": "512480", "name": "半导体ETF国联安", "index": "中证半导体"},
    {"code": "588750", "name": "芯片全产业链ETF", "index": "中证芯片产业"},
    # 新能源/电力
    {"code": "516160", "name": "新能源ETF华夏", "index": "中证新能源"},
    {"code": "159611", "name": "电力ETF嘉实", "index": "中证电力"},
    # 医药
    {"code": "512010", "name": "医药ETF国泰", "index": "中证医药"},
    {"code": "159992", "name": "创新药ETF银华", "index": "中证创新药"},
    # 金融
    {"code": "512800", "name": "银行ETF鹏华", "index": "中证银行"},
    {"code": "512000", "name": "券商ETF华宝", "index": "中证证券"},
    # 军工
    {"code": "512660", "name": "军工ETF国泰", "index": "中证军工"},
    # 消费/白酒
    {"code": "512690", "name": "白酒ETF鹏华", "index": "中证白酒"},
    # 基建
    {"code": "159619", "name": "基建ETF广发", "index": "中证基建"},
    # 科技
    {"code": "515050", "name": "5GETF华夏", "index": "中证5G通信"},
    {"code": "515070", "name": "人工智能ETF", "index": "中证人工智能"},
    # 红利
    {"code": "510880", "name": "红利ETF易方达", "index": "上证红利"},
    # 黄金
    {"code": "518880", "name": "黄金ETF华安", "index": "黄金"},
    # 用户持仓（不在以上分类中的持仓单独列出）
    {"code": "159530", "name": "机器人ETF易方达", "index": "中证机器人"},
    {"code": "159934", "name": "黄金ETF易方达", "index": "黄金"},
]

# =============================================================================
# Index Watch List — 20 major indices for valuation tracking
# =============================================================================
INDEX_WATCH_LIST = [
    "沪深300",
    "中证500",
    "创业板指",
    "科创50",
    "上证50",
    "中证半导体",
    "中证芯片产业",
    "中证新能源",
    "中证电力",
    "中证医药",
    "中证创新药",
    "中证银行",
    "中证证券",
    "中证军工",
    "中证白酒",
    "中证基建",
    "中证5G通信",
    "中证人工智能",
    "上证红利",
    "深证100",
]

# =============================================================================
# User Holdings — 用户当前持仓（与分析框架独立，用于早报溢价率和组合计算）
# =============================================================================
USER_HOLDINGS = [
    {"code": "159530", "name": "机器人ETF易方达", "sector": "机器人"},
    {"code": "588750", "name": "芯片全产业链ETF", "sector": "半导体/芯片"},
    {"code": "159934", "name": "黄金ETF易方达", "sector": "黄金"},
]

# =============================================================================
# Sector Mapping — ETF代码 → 行业板块映射（用于板块聚合）
# =============================================================================
SECTOR_MAPPING = {
    "宽基": ["510300", "510500", "159915", "588000", "510050"],
    "半导体/芯片": ["512480", "588750"],
    "新能源": ["516160"],
    "医药": ["512010", "159992"],
    "金融": ["512800", "512000"],
    "军工": ["512660"],
    "消费/白酒": ["512690"],
    "基建": ["159619"],
    "科技/通信": ["515050", "515070"],
    "红利": ["510880"],
    "黄金": ["518880", "159934"],
    "机器人": ["159530"],
    "电力": ["159611"],
}

# =============================================================================
# API Configuration
# =============================================================================
# (TTFUND_API_URL / TTFUND_APIKEY removed 2026-08-20: ttfund_client replaced by
#  akshare_fund_client. See docs/phase-2-followup.md for remaining data gaps.)

# =============================================================================
# Data Storage
# =============================================================================
DATA_DIR = "/root/secureshare/files/ETF轮动分析框架/data"

# =============================================================================
# API Timeout
# =============================================================================
SLOW_API_TIMEOUT = 45  # seconds
# =============================================================================
# Cache TTL — 数据类型对应的缓存有效期（小时）
# =============================================================================
CACHE_TTL = {
    "etf_snapshot": 24,         # 当日
    "macro_north_flow": 168,      # 7天
    "etf_scale": 168,             # 7天
    "margin": 24,                # 1天
    "macro_pmi": 720,             # 30天
    "macro_cpi": 720,             # 30天
    "macro_ppi": 720,             # 30天
    "macro_m2": 720,              # 30天
    "macro_lpr": 168,             # 7天
    "macro_shrzgm": 720,          # 30天
    "macro_gdp": 2160,            # 90天
    "macro_industrial": 720,      # 30天
    "nav_history": 24,            # 当日
    "index_valuation": 168,       # 7天
    "holdings": 720,             # 30天
    "manager_info": 720,          # 30天
    "gold_info": 168,             # 7天
    "strategy": 2160,             # 90天
    "industry_alloc": 2160,       # 90天
}

# =============================================================================
# Validation Rules — 数据校验规则
# =============================================================================
VALIDATION_RULES = {
    "PMI": {"min": 30, "max": 70, "nullable": False},
    "CPI_YOY": {"min": -10, "max": 20, "nullable": False},
    "PPI_YOY": {"min": -30, "max": 30, "nullable": False},
    "M2_YOY": {"min": 0, "max": 30, "nullable": False},
    "LPR_1Y": {"min": 2, "max": 10, "nullable": False},
    "GDP_YOY": {"min": -10, "max": 20, "nullable": False},
    "PE_PERCENTILE": {"min": 0, "max": 100, "nullable": True},
    "ETL_SCALE": {"min": 0, "max": 10000, "nullable": False},  # 亿元
    "NAV": {"min": 0, "max": 100, "nullable": False},
    "NORTH_FLOW": {"min": -500, "max": 500, "nullable": True},  # 亿元
}


# =============================================================================
# Runtime loader — replaces 4 ETF list constants from etf_config.json
# =============================================================================
# Per ADR-004 Q6: config.py is a thin wrapper that loads JSON at process start
# via init_config(path). The defaults above remain valid (back-compat per Q22-B)
# for tests and ad-hoc scripts. In production cron flow, collector_daily calls
# init_config() before any read of these 4 constants.
#
# Fail-fast per Q13-A / Q20-B: bad path / bad JSON / schema violation → raise
# ConfigLoadError, no silent fallback. The cron job will see a non-zero exit
# code and the operator (皮皮) will fix the JSON file directly.

# Module-level flag tracking whether init_config has succeeded.
_initialized: bool = False


def is_initialized() -> bool:
    """Return True iff init_config() has succeeded in this process."""
    return _initialized


def init_config(path) -> None:
    """Load etf_config.json and replace the 4 ETF list constants in-place.

    Must be called exactly once per process, before any code reads
    ``config.ETF_WATCH_LIST`` etc. via attribute lookup. After this call
    succeeds, attribute lookups for the 4 lists return the loaded values;
    existing imports done before this call (e.g. ``from src.config import
    ETF_WATCH_LIST``) keep their original (default) reference — this is the
    back-compat guarantee relied on by tests/test_config.py.

    Args:
        path: Path-like pointing to etf_config.json.

    Raises:
        ConfigLoadError: File / parse / schema failure. No fallback (Q20-B).
        RuntimeError: If called more than once (signals a configuration bug
            in the calling code; the second call is rejected rather than
            silently overwriting because the operator only sees one cron
            prompt and a second init usually means the path changed mid-run).
    """
    global _initialized

    if _initialized:
        raise RuntimeError(
            "init_config() called twice in the same process. "
            "皮皮 should not need to reconfigure mid-run; "
            "if this is a test, use importlib.reload(src.config) instead."
        )

    from src.config_loader import load_config  # lazy: keeps this module
                                              # importable without jsonschema

    loaded = load_config(path)

    # Mutate module attributes — attribute lookups (`config.ETF_WATCH_LIST`)
    # see the new values; imports done before this call stay frozen.
    ETF_WATCH_LIST = loaded["etf_watch_list"]
    USER_HOLDINGS = loaded["user_holdings"]
    INDEX_WATCH_LIST = loaded["index_watch_list"]
    SECTOR_MAPPING = loaded["sector_mapping"]

    # Direct module-dict mutation ensures `from src.config import X` calls
    # in OTHER modules that fire after this point also see the new value.
    import sys
    this_module = sys.modules[__name__]
    this_module.ETF_WATCH_LIST = ETF_WATCH_LIST
    this_module.USER_HOLDINGS = USER_HOLDINGS
    this_module.INDEX_WATCH_LIST = INDEX_WATCH_LIST
    this_module.SECTOR_MAPPING = SECTOR_MAPPING

    _initialized = True
