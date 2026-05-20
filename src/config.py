"""Configuration for ETF Data Collection System.

This module contains all static configuration for the data collection system.
It has no business logic, does not read/write files, and does not call any APIs.
"""

import os

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
# API Configuration
# =============================================================================
TTFUND_API_URL = "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill/invoke"
TTFUND_APIKEY = os.environ.get("TTFUND_APIKEY", "")

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
