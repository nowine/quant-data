"""akshare data fetcher with CSV caching.

Provides a single public function `get_akshare_data` and one internal
helper `_with_cache` that wraps any fetch function with a TTL-based CSV cache.

Public market data functions:
- get_etf_snapshot()    : ETF real-time snapshot (sina, 24h TTL)
- get_north_flow()       : North-bound capital flow (hsgt, 168h TTL)
- get_etf_history()      : ETF historical k-line with sina→em fallback (24h TTL)
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
"""

import os
import time

import akshare as ak
import pandas as pd

from src.logger import log_collect
from src.storage import save_csv


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
    from src.config import DATA_DIR

    cache_dir = os.path.join(DATA_DIR, "cache")
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


def get_akshare_data(
    cache_key: str, ttl_hours: int, fetch_fn: callable
) -> pd.DataFrame:
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
    """ETF real-time snapshot from Sina.

    Wraps ``akshare.fund_etf_category_sina()``.
    Cache TTL: 24 hours.

    Returns:
        DataFrame with ETF listing data.
    """
    return _with_cache("etf_snapshot", 24, lambda: ak.fund_etf_category_sina())


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
        lambda: ak.stock_hsgt_hist_em(symbol=symbol),
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
        # Sina requires exchange prefix: sh510300 or sz159919
        prefix = _etf_prefix(code)
        symbol = f"{prefix}{code}"
        try:
            return ak.fund_etf_hist_sina(symbol=symbol)
        except Exception:
            # Fallback to eastmoney (no prefix needed)
            return ak.fund_etf_hist_em(symbol=code)

    return _with_cache(f"etf_history_{code}", 24, _fetch)


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
