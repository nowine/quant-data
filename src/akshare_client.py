"""akshare data fetcher with CSV caching.

Provides a single public function `get_akshare_data` and one internal
helper `_with_cache` that wraps any fetch function with a TTL-based CSV cache.

Public market data functions:
- get_etf_snapshot()    : ETF real-time snapshot (sina, 24h TTL)
- get_north_flow()       : North-bound capital flow (hsgt, 168h TTL)
- get_etf_history()      : ETF historical k-line with sina→em fallback (24h TTL)
- get_etf_scale()        : ETF scale on SSE (sse, 168h TTL)
- get_margin_sh()        : Shanghai margin trading (sh, 24h TTL)
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
        lambda: ak.stock_hsgt_hist_em(symbol=symbol, adjust=""),
    )


def get_etf_history(code: str) -> pd.DataFrame:
    """ETF historical k-line with primary→fallback retrieval.

    Primary:   ``akshare.fund_etf_hist_sina(symbol=code)``
    Fallback:  ``akshare.fund_etf_hist_em(symbol=code)``  (if sina fails)
    Cache TTL: 24 hours.

    Args:
        code:  ETF code, e.g. "510300".

    Returns:
        DataFrame with historical OHLCV data.
    """

    def _fetch():
        try:
            return ak.fund_etf_hist_sina(symbol=code)
        except Exception:
            # Fallback to eastmoney when sina fails
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
