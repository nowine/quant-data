"""Weekly data collector — runs every Monday at 08:30.

Collects:
  1. ETF scale (SSE)       -> weekly/etf_scale_{week}.csv
  2. North-bound flow      -> weekly/north_flow_week_{date}.csv
  3. Industry allocation  -> weekly/industry_alloc_{year}_{week}.csv

Usage:
    python collector_weekly.py
"""

import datetime
import sys
import time
from pathlib import Path

from src import config, logger as logger_module
from src.akshare_client import (
    get_etf_scale,
    get_north_flow,
    get_industry_alloc,
)
from src.storage import save_csv, exists_today


# ── Clock stub ─────────────────────────────────────────────────────────────────

def today() -> datetime.date:
    """Return today's date. Stubbed in tests."""
    return datetime.date.today()


# ── File paths ─────────────────────────────────────────────────────────────────

def _weekly_dir() -> Path:
    """Return the weekly data directory."""
    d = Path(config.DATA_DIR) / "weekly"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _etf_scale_path() -> Path:
    week = today().isocalendar()[1]
    return _weekly_dir() / f"etf_scale_{week}.csv"


def _north_flow_week_path() -> Path:
    return _weekly_dir() / f"north_flow_week_{today()}.csv"


def _industry_alloc_path() -> Path:
    year, week = today().isocalendar()[0], today().isocalendar()[1]
    return _weekly_dir() / f"industry_alloc_{year}_{week}.csv"


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _collect_csv(
    name: str,
    fetch_fn: callable,
    filepath: Path,
) -> dict:
    """Fetch data, save to CSV, return a result dict.

    Uses exists_today so partial reruns skip already-captured files.
    """
    start = time.time()

    if exists_today(str(filepath)):
        elapsed = time.time() - start
        logger_module.log_collect(
            task=name,
            source=filepath.name,
            status="cache_hit",
            rows=0,
            elapsed_sec=elapsed,
            message=f"Already exists: {filepath}",
        )
        return {"status": "skipped", "elapsed_sec": elapsed}

    try:
        df = fetch_fn()
        save_csv(df, str(filepath))
        elapsed = time.time() - start
        logger_module.log_collect(
            task=name,
            source=filepath.name,
            status="success",
            rows=len(df),
            elapsed_sec=elapsed,
            message=f"Saved: {filepath}",
        )
        return {"status": "success", "rows": len(df), "elapsed_sec": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        logger_module.log_collect(
            task=name,
            source=filepath.name,
            status="error",
            rows=0,
            elapsed_sec=elapsed,
            message=str(e),
        )
        return {"status": "error", "error": str(e), "elapsed_sec": elapsed}


# ── Core collector ──────────────────────────────────────────────────────────────

def run_weekly() -> dict[str, dict]:
    """Collect weekly data: ETF scale, north flow, industry allocation.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
    """
    results = {}

    # 1. ETF 规模
    results["etf_scale"] = _collect_csv(
        "etf_scale",
        get_etf_scale,
        _etf_scale_path(),
    )

    # 2. 北向资金周度
    results["north_flow_week"] = _collect_csv(
        "north_flow_week",
        lambda: get_north_flow("沪深股通", 1),
        _north_flow_week_path(),
    )

    # 3. 行业配置
    year = today().year
    results["industry_alloc"] = _collect_csv(
        "industry_alloc",
        lambda: get_industry_alloc(year),
        _industry_alloc_path(),
    )

    # Summary
    total = len(results)
    success = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    skipped = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "skipped")
    errors = sum(1 for v in results.values()
                 if isinstance(v, dict) and v.get("status") == "error")

    logger_module.log_collect(
        task="weekly_summary",
        source="weekly",
        status="summary",
        rows=total,
        elapsed_sec=0,
        message=f"weekly: {success} success, {skipped} skipped, {errors} errors",
    )

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if today().weekday() != 0:
        print(f"Today ({today()}) is not Monday — weekly collector should run on Mondays only.")
        sys.exit(0)

    print("Running weekly collector...")
    result = run_weekly()
    success = sum(1 for v in result.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    total = len(result)
    print(f"Done: {success}/{total} tasks succeeded.")


if __name__ == "__main__":
    main()