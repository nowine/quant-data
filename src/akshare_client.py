"""akshare data fetcher with CSV caching.

Provides a single public function `get_akshare_data` and one internal
helper `_with_cache` that wraps any fetch function with a TTL-based CSV cache.
"""

import os
import time

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
