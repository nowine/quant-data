"""Daily data collector — two run modes: close (15:30) and morning (08:00).

Usage:
    python collector_daily.py --mode=close   # After market close
    python collector_daily.py --mode=morning # Before market open
"""

import argparse
import datetime
import sys
import time
from pathlib import Path


from src import config, logger as logger_module
from src.akshare_client import (
    get_etf_snapshot,
    get_margin_sh,
    get_north_flow,
)
from src.storage import save_csv, save_json, exists_today
from src.ttfund_client import get_nav_history, get_gold_info, get_index_info


# ── Clock stub ─────────────────────────────────────────────────────────────────

def today() -> datetime.date:
    """Return today's date. Stubbed in tests."""
    return datetime.date.today()


# ── Trading day check ──────────────────────────────────────────────────────────

def is_trading_day() -> bool:
    """Return True if today is a weekday (Mon-Fri)."""
    return today().weekday() < 5


# ── File paths ─────────────────────────────────────────────────────────────────

def _daily_dir() -> Path:
    """Return the daily data directory."""
    d = Path(config.DATA_DIR) / "daily"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _etf_snapshot_path() -> Path:
    return _daily_dir() / f"etf_snapshot_{today()}.csv"


def _margin_sh_path() -> Path:
    return _daily_dir() / f"margin_sh_{today()}.csv"


def _nav_path(code: str) -> Path:
    return _daily_dir() / f"nav_{code}_{today()}.csv"


def _north_flow_path() -> Path:
    return _daily_dir() / f"north_flow_{today()}.csv"


def _gold_macro_path() -> Path:
    return _daily_dir() / f"gold_macro_{today()}.json"


def _index_valuation_path() -> Path:
    return _daily_dir() / f"index_valuation_{today()}.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_csv(
    name: str,
    fetch_fn: callable,
    filepath: Path,
) -> dict:
    """Fetch data, save to CSV, return a result dict.

    Uses collect_if_missing so partial reruns skip already-captured files.
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


def _collect_json(
    name: str,
    fetch_fn: callable,
    filepath: Path,
) -> dict:
    """Fetch data (dict/list), save to JSON, return a result dict."""
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
        data = fetch_fn()
        save_json(data, str(filepath))
        elapsed = time.time() - start
        logger_module.log_collect(
            task=name,
            source=filepath.name,
            status="success",
            rows=1,
            elapsed_sec=elapsed,
            message=f"Saved: {filepath}",
        )
        return {"status": "success", "elapsed_sec": elapsed}
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


# ── Mode: close ────────────────────────────────────────────────────────────────

def run_close_mode() -> dict[str, dict]:
    """Collect end-of-day data: ETF snapshot, margin, north flow, NAV.

    Runs collect_if_missing for each item so already-captured files are skipped.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
    """
    results = {}

    # 1. ETF 全市场行情快照
    results["etf_snapshot"] = _collect_csv(
        "etf_snapshot",
        get_etf_snapshot,
        _etf_snapshot_path(),
    )

    # 2. 融资融券余额 (SH)
    results["margin_sh"] = _collect_csv(
        "margin_sh",
        get_margin_sh,
        _margin_sh_path(),
    )

    # 3. 北向资金近 3 月
    def fetch_north():
        return get_north_flow("沪股通", 3)
    results["north_flow"] = _collect_csv(
        "north_flow",
        fetch_north,
        _north_flow_path(),
    )

    # 4. 核心 ETF 净值 — 遍历 ETF_WATCH_LIST
    nav_results = {}
    for etf in config.ETF_WATCH_LIST:
        code = etf["code"]
        path = _nav_path(code)

        def fetch_nav(c=code):
            return get_nav_history(c, "y")

        nav_results[code] = _collect_csv(f"nav_{code}", fetch_nav, path)

    results["nav"] = nav_results

    # Summary
    total = len(results)
    success = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    skipped = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "skipped")
    errors = sum(1 for v in results.values()
                 if isinstance(v, dict) and v.get("status") == "error")

    logger_module.log_collect(
        task="close_summary",
        source="daily",
        status="summary",
        rows=total,
        elapsed_sec=0,
        message=f"close mode: {success} success, {skipped} skipped, {errors} errors",
    )

    return results


# ── Mode: morning ──────────────────────────────────────────────────────────────

def run_morning_mode() -> dict[str, dict]:
    """Collect pre-market data: gold + macro, index valuations.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
    """
    results = {}

    # 1. 黄金 + 宏观指标
    results["gold_macro"] = _collect_json(
        "gold_macro",
        lambda: get_gold_info("all"),
        _gold_macro_path(),
    )

    # 2. 核心指数估值分位 — 遍历 INDEX_WATCH_LIST
    val_results = {}
    for idx in config.INDEX_WATCH_LIST:
        path = _index_valuation_path()

        def fetch_val(i=idx):
            return get_index_info(i, "all")

        val_results[idx] = _collect_json(f"index_valuation_{idx}", fetch_val, path)

    results["index_valuation"] = val_results

    # Summary
    total = len(results)
    success = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    skipped = sum(1 for v in results.values()
                  if isinstance(v, dict) and v.get("status") == "skipped")
    errors = sum(1 for v in results.values()
                 if isinstance(v, dict) and v.get("status") == "error")

    logger_module.log_collect(
        task="morning_summary",
        source="daily",
        status="summary",
        rows=total,
        elapsed_sec=0,
        message=f"morning mode: {success} success, {skipped} skipped, {errors} errors",
    )

    return results


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Daily ETF data collector")
    parser.add_argument(
        "--mode",
        choices=["close", "morning"],
        default="close",
        help="Run mode: 'close' (after market, 15:30) or 'morning' (before open, 08:00)",
    )
    args = parser.parse_args()

    if not is_trading_day():
        print(f"Today ({today()}) is not a trading day — nothing to do.")
        sys.exit(0)

    if args.mode == "close":
        print("Running close mode...")
        result = run_close_mode()
        success = sum(1 for v in result.values()
                      if isinstance(v, dict) and v.get("status") == "success")
        total = len(result)
        print(f"Done: {success}/{total} tasks succeeded.")
    else:
        print("Running morning mode...")
        result = run_morning_mode()
        success = sum(1 for v in result.values()
                      if isinstance(v, dict) and v.get("status") == "success")
        total = len(result)
        print(f"Done: {success}/{total} tasks succeeded.")


if __name__ == "__main__":
    main()
