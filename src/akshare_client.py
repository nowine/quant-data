"""akshare data fetcher with CSV caching.

Provides a single public function `get_akshare_data` and one internal
helper `_with_cache` that wraps any fetch function with a TTL-based CSV cache.

Public market data functions:
- get_etf_snapshot()    : ETF real-time snapshot (THS, 1576 ETFs, 24h TTL)
- get_north_flow()       : North-bound capital flow (hsgt, 168h TTL)
- get_etf_history()      : ETF historical k-line with sina→em fallback (24h TTL)
- get_us_stock_index()  : US major indices (Nasdaq/S&P/Dow), dual-source eastmoney→sina (24h TTL)
- get_etf_scale()        : ETF scale on SSE (sse, 168h TTL)
- get_margin_sh()        : Shanghai margin trading (sh, 24h TTL)
- get_pmi()             : China manufacturing PMI (72h TTL)
- get_cpi()             : China CPI yearly (720h TTL)
- get_ppi()             : China PPI yearly (720h TTL)
- get_m2()              : China M2 money supply (720h TTL)
- get_lpr()             : China LPR (168h TTL)
- get_shrzgm()          : China social financing (720h TTL)
- get_gdp()             : China GDP (2160h TTL)
- get_industrial()       : China industrial production YoY (720h TTL)
- get_industry_alloc()   : Fund industry allocation (2160h TTL)
- get_fx_rate()         : USD/CNY FX rate, degrade→LLM fallback (24h TTL)
- get_futures_basis()  : CSI futures basis, degrade→LLM fallback (24h TTL)
- get_commodity_price(): Commodity prices, degrade→LLM fallback (24h TTL)
- get_stock_board_industry(): Industry board ranking (24h TTL)
"""

import datetime
import os
import socket
import time

import akshare as ak
import pandas as pd

from src.logger import log_collect
from src.storage import save_csv

_MIN_INTERVAL = 5.0  # seconds between consecutive calls (avoids getting blocked)
_last_call_time: float = 0.0

# Set default socket timeout for all HTTP calls (akshare / urllib3 / requests).
# Prevents indefinitely hanging connections on slow/unreachable hosts.
socket.setdefaulttimeout(30.0)


def _rate_limit():
    """Sleep to meet the minimum interval between API calls."""
    global _last_call_time
    now = time.time()
    if _last_call_time > 0:
        elapsed = now - _last_call_time
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_time = time.time()


def _with_cache(cache_key: str, ttl_hours: int, fetch_fn: callable) -> pd.DataFrame:
    """Fetch data with a TTL-based CSV cache.

    Cache path  : data/cache/{cache_key}.csv
    TTL         : measured from file mtime; if file is younger than ttl_hours,
                  treat it as a cache hit.

    On cache hit   → load and return the CSV, log as ``cache_hit``.
    On cache miss  → call ``fetch_fn()``, save result to cache, log as ``success``.
    On fetch error → let the exception bubble up; callers decide how to degrade.

    Args:
        cache_key:  Logical name for this data item (no .csv extension).
        ttl_hours:  How many hours the cached file remains valid.
        fetch_fn:   Zero-argument callable that returns a DataFrame.

    Returns:
        DataFrame with the requested data.
    """
    # Read DATA_DIR via attribute access (not `from ... import DATA_DIR`) so
    # any future re-resolution (env override, init_config, reload) takes effect.
    # Same pattern used by collector_daily/weekly/monthly/quarterly.
    import src.config as _config

    cache_dir = os.path.join(_config.DATA_DIR, "cache")
    cache_file = os.path.join(cache_dir, f"{cache_key}.csv")

    # ── Cache hit? ───────────────────────────────────────────────────────────
    if os.path.isfile(cache_file):
        age_seconds = time.time() - os.path.getmtime(cache_file)
        if age_seconds < ttl_hours * 3600:
            # Valid cache entry found
            df = pd.read_csv(cache_file, encoding="utf-8")
            log_collect(
                task="partial_rerun",
                source=f"{cache_key}.csv",
                status="cache_hit",
                rows=0,
                elapsed_sec=0.0,
                message=f"Cache hit: {cache_file}",
            )
            return df

    # ── Cache miss – fetch, save, log ─────────────────────────────────────────
    start = time.time()
    df = fetch_fn()
    save_csv(df, cache_file)
    elapsed = time.time() - start
    log_collect(
        task="partial_rerun",
        source=f"{cache_key}.csv",
        status="success",
        rows=len(df),
        elapsed_sec=elapsed,
        message=f"Fetched and cached: {cache_file}",
    )
    return df


def get_akshare_data(cache_key: str, ttl_hours: int, fetch_fn: callable) -> pd.DataFrame:
    """Public entry point: fetch data with TTL cache.

    This is a thin wrapper around ``_with_cache`` for callers that don't need
    to know the internal cache key construction.

    Args:
        cache_key:  Logical name for this data item.
        ttl_hours:  Cache TTL in hours.
        fetch_fn:   Zero-argument callable that returns a DataFrame.

    Returns:
        DataFrame with the requested data.
    """
    return _with_cache(cache_key, ttl_hours, fetch_fn)


# ── Market Data Functions ────────────────────────────────────────────────────


def get_etf_snapshot() -> pd.DataFrame:
    """ETF real-time snapshot from THS (Tonghuashun).

    Wraps ``akshare.fund_etf_category_ths()`` which covers 1576 ETFs with
    pure numeric codes (vs Sina's 382 with sz/sh prefixes).

    Output columns are standardised to match config expectations:
        代码 (pure numeric, e.g. "510300"), 名称, 涨跌幅, 最新价 (净值≈市价).

    Cache TTL: 24 hours.
    """
    _rename = {
        "基金代码": "代码",
        "基金名称": "名称",
        "当前-单位净值": "最新价",
        "增长率": "涨跌幅",
        "增长值": "涨跌额",
        "前一日-单位净值": "昨收",
    }

    def _fetch():
        _rate_limit()
        raw = ak.fund_etf_category_ths()
        return raw.rename(columns=_rename).astype({"代码": str})

    return _with_cache("etf_snapshot_ths", 24, _fetch).astype({"代码": str})


def get_north_flow(symbol: str = "北向资金", months: int = 3) -> pd.DataFrame:
    """North-bound (HSGT) capital flow history.

    Wraps ``akshare.stock_hsgt_hist_em()``.
    Cache TTL: 168 hours (7 days).

    Args:
        symbol:  Fund or stock symbol, default "北向资金".
        months:  Historical window in months, default 3.

    Returns:
        DataFrame with flow data (date, close, change, volume, amount, …).
    """
    return _with_cache(
        f"north_flow_{symbol}_{months}",
        168,
        lambda: (_rate_limit(), ak.stock_hsgt_hist_em(symbol=symbol))[-1],
    )


def _etf_prefix(code: str) -> str:
    """Return sina exchange prefix for ETF code.

    Shanghai ETF (5xxxxx) -> 'sh'
    Shenzhen ETF (1xxxxx) -> 'sz'
    """
    return "sh" if code.startswith("5") else "sz"


def get_etf_history(code: str) -> pd.DataFrame:
    """ETF historical k-line with primary→fallback retrieval.

    Primary:   ``akshare.fund_etf_hist_sina(symbol=code)`` with correct
               exchange prefix (sh/sz) inferred from code prefix.
    Fallback:  ``akshare.fund_etf_hist_em(symbol=code)``  (if sina fails)
    Cache TTL: 24 hours.

    Args:
        code:  ETF code, e.g. "510300" (sh) or "159919" (sz).

    Returns:
        DataFrame with historical OHLCV data.
    """

    def _fetch():
        _rate_limit()
        prefix = _etf_prefix(code)
        symbol = f"{prefix}{code}"
        try:
            return ak.fund_etf_hist_sina(symbol=symbol)
        except Exception:
            # Fallback to eastmoney (no prefix needed)
            _rate_limit()
            return ak.fund_etf_hist_em(symbol=code)

    return _with_cache(f"etf_history_{code}", 24, _fetch)


_US_INDEX_EM_NAME_TO_CODE = {
    "标普500指数": ".INX",
    "纳斯达克综合指数": ".IXIC",
    "道琼斯工业指数": ".DJI",
}
_US_INDEX_SINA = {
    ".INX": "标普500",
    ".IXIC": "纳斯达克综合",
    ".DJI": "道琼斯工业",
}
_US_INDEX_COLUMNS = ["指数代码", "指数名称", "日期", "收盘价", "涨跌幅"]


def _fetch_us_index_primary() -> pd.DataFrame:
    """Fetch US major indices via eastmoney spot table, normalized.

    Returns columns [指数代码, 指数名称, 日期, 收盘价, 涨跌幅], one row per index
    in fixed order. Raises if the endpoint fails OR no major-index row matches
    (the old silent "return all rows" fallback leaked junk stock rows).
    """
    _rate_limit()
    df = ak.stock_us_spot_em()
    has_pct = "涨跌幅" in df.columns
    rows = []
    for em_name, code in _US_INDEX_EM_NAME_TO_CODE.items():
        hit = df[df["名称"] == em_name]
        if hit.empty:
            continue
        r = hit.iloc[0]
        close = pd.to_numeric(r["最新价"], errors="coerce")
        if pd.isna(close):
            continue
        pct = pd.to_numeric(r["涨跌幅"], errors="coerce") if has_pct else None
        rows.append(
            {
                "指数代码": code,
                "指数名称": em_name,
                "日期": datetime.date.today().isoformat(),
                "收盘价": float(close),
                "涨跌幅": None if pct is None or pd.isna(pct) else float(pct),
            }
        )
    if not rows:
        raise ValueError(
            f"stock_us_spot_em returned no major-index rows (got {len(df)} rows, "
            f"needed {_US_INDEX_EM_NAME_TO_CODE})"
        )
    return pd.DataFrame(rows, columns=_US_INDEX_COLUMNS)


def _fetch_us_index_sina() -> pd.DataFrame:
    """Fetch US major indices via sina daily bars (index_us_stock_sina).

    Takes the last 2 bars per index; close = latest close,
    涨跌幅 = pct change vs previous close. Same normalized schema as primary.
    Raises if any index has insufficient history (<2 bars).
    """
    frames = []
    for symbol, name in _US_INDEX_SINA.items():
        _rate_limit()
        hist = ak.index_us_stock_sina(symbol=symbol)
        if hist is None or len(hist) < 2:
            raise ValueError(f"index_us_stock_sina({symbol}) returned <2 bars")
        last = hist.iloc[-1]
        prev_close = float(hist.iloc[-2]["close"])
        close = float(last["close"])
        frames.append(
            {
                "指数代码": symbol,
                "指数名称": name,
                "日期": str(last["date"]),
                "收盘价": close,
                "涨跌幅": round((close / prev_close - 1) * 100, 4),
            }
        )
    return pd.DataFrame(frames, columns=_US_INDEX_COLUMNS)


def _fetch_us_indices() -> pd.DataFrame:
    """Dual-source US index fetch: eastmoney spot → sina daily-bar fallback.

    Fallback engagement is logged as status=degraded so the collect log shows
    which source served the data. Raises RuntimeError if both fail.
    """
    try:
        return _fetch_us_index_primary()
    except Exception as primary_err:
        primary_detail = f"{type(primary_err).__name__}: {primary_err}"
        log_collect(
            task="us_stock_index",
            source="us_stock_index",
            status="degraded",
            rows=0,
            elapsed_sec=0.0,
            message=f"primary source failed ({primary_detail}); falling back to sina",
        )
    try:
        return _fetch_us_index_sina()
    except Exception as sina_err:
        # NOTE: primary_err is del-ed when its except block exits (PEP 3110),
        # so the detail string must be captured inside that block.
        raise RuntimeError(
            f"us_stock_index: both sources failed — "
            f"eastmoney: {primary_detail}; sina: {sina_err}"
        ) from sina_err


def get_us_stock_index() -> pd.DataFrame:
    """US stock market indices (Nasdaq, S&P500, Dow Jones) close prices.

    Dual-source with automatic fallback (2026-09-28):
    1. Primary: ``akshare.stock_us_spot_em()`` (eastmoney realtime spot)
    2. Fallback: ``akshare.index_us_stock_sina()`` (sina daily bars)

    Cache TTL: 24 hours (updated once per trading day).

    Returns:
        DataFrame [指数代码, 指数名称, 日期, 收盘价, 涨跌幅], 3 rows
        (.INX / .IXIC / .DJI).
    """
    return _with_cache("us_stock_index", 24, _fetch_us_indices)


def get_etf_scale() -> pd.DataFrame:
    """ETF scale (AUM) data from Shanghai Stock Exchange.

    Wraps ``akshare.fund_etf_scale_sse()``.
    Cache TTL: 168 hours (7 days).

    Returns:
        DataFrame with ETF code, name, and scale columns.
    """
    return _with_cache("etf_scale", 168, lambda: ak.fund_etf_scale_sse())


def get_margin_sh() -> pd.DataFrame:
    """Shanghai margin trading statistics.

    Wraps ``akshare.macro_china_market_margin_sh()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with margin trading data (date, margin_balance, margin_buy, …).
    """
    return _with_cache("margin_sh", 24, lambda: ak.macro_china_market_margin_sh())


def get_pmi() -> pd.DataFrame:
    """China manufacturing PMI.

    Wraps ``akshare.macro_china_pmi()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with PMI data.
    """
    return _with_cache("macro_pmi", 720, lambda: ak.macro_china_pmi())


def get_cpi() -> pd.DataFrame:
    """China CPI yearly.

    Wraps ``akshare.macro_china_cpi_yearly()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with CPI data.
    """
    return _with_cache("macro_cpi", 720, lambda: ak.macro_china_cpi_yearly())


def get_ppi() -> pd.DataFrame:
    """China PPI yearly.

    Wraps ``akshare.macro_china_ppi_yearly()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with PPI data.
    """
    return _with_cache("macro_ppi", 720, lambda: ak.macro_china_ppi_yearly())


def get_m2() -> pd.DataFrame:
    """China M2 money supply.

    Wraps ``akshare.macro_china_money_supply()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with M2 money supply data.
    """
    return _with_cache("macro_m2", 720, lambda: ak.macro_china_money_supply())


def get_lpr() -> pd.DataFrame:
    """China Loan Prime Rate (LPR).

    Wraps ``akshare.macro_china_lpr()``.
    Cache TTL: 168 hours (7 days).

    Returns:
        DataFrame with LPR data.
    """
    return _with_cache("macro_lpr", 168, lambda: ak.macro_china_lpr())


def get_shrzgm() -> pd.DataFrame:
    """China total social financing volume.

    Wraps ``akshare.macro_china_shrzgm()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with social financing data.
    """
    return _with_cache("macro_shrzgm", 720, lambda: ak.macro_china_shrzgm())


def get_gdp() -> pd.DataFrame:
    """China GDP.

    Wraps ``akshare.macro_china_gdp()``.
    Cache TTL: 2160 hours (90 days).

    Returns:
        DataFrame with GDP data.
    """
    return _with_cache("macro_gdp", 2160, lambda: ak.macro_china_gdp())


def get_industrial() -> pd.DataFrame:
    """China industrial production year-on-year.

    Wraps ``akshare.macro_china_industrial_production_yoy()``.
    Cache TTL: 720 hours (30 days).

    Returns:
        DataFrame with industrial production data.
    """
    return _with_cache("macro_industrial", 720, lambda: ak.macro_china_industrial_production_yoy())


def get_industry_alloc(year: int) -> pd.DataFrame:
    """Fund industry allocation by year.

    Wraps ``akshare.fund_portfolio_industry_allocation_em()``.
    Cache TTL: 2160 hours (90 days).

    Args:
        year:  The year to query, e.g. 2023.

    Returns:
        DataFrame with industry allocation data.
    """
    return _with_cache(
        f"macro_industry_alloc_{year}", 2160, lambda: ak.fund_portfolio_industry_allocation_em(year)
    )


def _degrade_to_empty(fetch_fn: callable, api_name: str) -> pd.DataFrame:
    """Try fetch_fn, log warning and return empty DataFrame on failure.

    Used for APIs that are blocked on Tencent Cloud (US stock, FX, etc.)
    so the caller always gets a DataFrame (possibly empty) instead of an exception.
    """
    try:
        return fetch_fn()
    except Exception as e:
        log_collect(
            task=api_name,
            source="akshare_client",
            status="degraded",
            rows=0,
            elapsed_sec=0,
            message=f"akshare {api_name} unavailable on this network, LLM search recommended: {e}",
        )
        return pd.DataFrame()


def get_fx_rate() -> pd.DataFrame:
    """FX exchange rate (USD/CNY).

    Wraps ``akshare.currency_history()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with exchange rate data, or empty DataFrame if unavailable.
        If empty, use LLM to search for current USD/CNY rate.
    """
    return _with_cache(
        "fx_usd_cny",
        24,
        lambda: _degrade_to_empty(lambda: ak.currency_history(), "fx_rate"),
    )


def get_futures_basis() -> pd.DataFrame:
    """CSI futures basis (升贴水) data.

    Wraps ``akshare.futures_roll_price()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with futures basis data, or empty DataFrame if unavailable.
        If empty, use LLM to search for current basis data.
    """
    return _with_cache(
        "futures_basis",
        24,
        lambda: _degrade_to_empty(lambda: ak.futures_roll_price(), "futures_basis"),
    )


def get_commodity_price() -> pd.DataFrame:
    """Commodity futures prices (crude oil, copper, gold).

    Wraps ``akshare.futures_child_table()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with commodity prices, or empty if unavailable.
        If empty, use LLM to search for current prices.
    """
    return _with_cache(
        "commodity_price",
        24,
        lambda: _degrade_to_empty(lambda: ak.futures_child_table(), "commodity_price"),
    )


def get_stock_board_industry() -> pd.DataFrame:
    """Industry sector board ranking (concept/industry板块涨跌).

    Wraps ``akshare.stock_board_industry_name_em()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with industry board data (板块名称, 涨跌幅, 成交额等).
    """
    return _with_cache(
        "stock_board_industry",
        24,
        lambda: _degrade_to_empty(
            lambda: ak.stock_board_industry_name_em(), "stock_board_industry"
        ),
    )
