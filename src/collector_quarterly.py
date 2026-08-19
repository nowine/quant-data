"""Quarterly data collector — runs on the 15th of quarter-end months (Mar/Jun/Sep/Dec).

Data collected:
  - 公募基金持仓（股票、债券）via akshare_fund_client.get_holdings(fund_id, "all")
  - 指数估值分位（季度）via akshare_fund_client.get_index_info(idx, "all")

CLI: python collector_quarterly.py
"""

import datetime
import sys
import time
from pathlib import Path

from src import config, logger as logger_module
from src.storage import save_csv, save_json
from src.akshare_fund_client import get_holdings, get_index_info


# ── Clock stub ─────────────────────────────────────────────────────────────────

def today() -> datetime.date:
    """Return today's date. Stubbed in tests."""
    return datetime.date.today()


# ── Date helpers ───────────────────────────────────────────────────────────────

def is_quarterly_run_day() -> bool:
    """Return True if today is the 15th of a quarter-end month (Mar/Jun/Sep/Dec)."""
    d = today()
    return d.day == 15 and d.month in (3, 6, 9, 12)


# ── File paths ─────────────────────────────────────────────────────────────────

def _quarterly_dir() -> Path:
    d = Path(config.DATA_DIR) / "quarterly"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _holdings_path(fund_code: str) -> Path:
    date_str = today().strftime("%Y%m%d")
    return _quarterly_dir() / f"holdings_{fund_code}_{date_str}.csv"


def _index_valuation_path() -> Path:
    date_str = today().strftime("%Y%m%d")
    return _quarterly_dir() / f"index_valuation_{date_str}.json"


# ── Collectors ─────────────────────────────────────────────────────────────────

def _collect_holdings(fund: dict) -> dict:
    """Fetch and save fund holdings (stocks + bonds) for one fund."""
    start = time.time()
    code = fund["code"]
    path = _holdings_path(code)

    try:
        data = get_holdings(code, "all")
        # get_holdings returns dict with "datas" list
        records = data.get("datas", [])
        if records:
            import pandas as pd
            df = pd.DataFrame(records)
            save_csv(df, str(path))
        elapsed = time.time() - start
        logger_module.log_collect(
            task=f"holdings_{code}",
            source=f"holdings_{code}_{today()}",
            status="success",
            rows=len(records),
            elapsed_sec=elapsed,
            message=f"Saved {len(records)} holdings for {code}",
        )
        return {"status": "success", "rows": len(records), "elapsed_sec": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        logger_module.log_collect(
            task=f"holdings_{code}",
            source=f"holdings_{code}_{today()}",
            status="error",
            rows=0,
            elapsed_sec=elapsed,
            message=str(e),
        )
        return {"status": "error", "error": str(e), "elapsed_sec": elapsed}


def _collect_index_valuation() -> dict:
    """Fetch and save index valuation for all indices in INDEX_WATCH_LIST."""
    start = time.time()
    path = _index_valuation_path()

    try:
        results = {}
        for idx in config.INDEX_WATCH_LIST:
            data = get_index_info(idx, "all")
            results[idx] = data
            time.sleep(1.1)  # rate limit
        save_json(results, str(path))
        elapsed = time.time() - start
        logger_module.log_collect(
            task="index_valuation",
            source=f"index_valuation_{today()}",
            status="success",
            rows=len(results),
            elapsed_sec=elapsed,
            message=f"Saved valuations for {len(results)} indices",
        )
        return {"status": "success", "rows": len(results), "elapsed_sec": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        logger_module.log_collect(
            task="index_valuation",
            source=f"index_valuation_{today()}",
            status="error",
            rows=0,
            elapsed_sec=elapsed,
            message=str(e),
        )
        return {"status": "error", "error": str(e), "elapsed_sec": elapsed}


# ── Main run ────────────────────────────────────────────────────────────────────

def run_quarterly() -> dict:
    """Collect all quarterly data.

    Returns:
        dict mapping task name -> result dict with status/rows/elapsed_sec.
    """
    results = {}

    # 1. Fund holdings — first 5 ETFs in watch list
    holdings_results = {}
    for fund in config.ETF_WATCH_LIST[:5]:
        holdings_results[fund["code"]] = _collect_holdings(fund)
    results["holdings"] = holdings_results

    # 2. Index valuation — all indices in watch list
    results["index_valuation"] = _collect_index_valuation()

    # Summary
    logger_module.log_collect(
        task="quarterly_summary",
        source="quarterly",
        status="summary",
        rows=len(results),
        elapsed_sec=0,
        message=f"quarterly: {len(holdings_results)} holdings, {len(config.INDEX_WATCH_LIST)} indices",
    )
    return results


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    if not is_quarterly_run_day():
        print(f"Today ({today()}) is not a quarterly run day (15th of Mar/Jun/Sep/Dec).")
        sys.exit(0)

    print(f"Running quarterly collection for {today()}...")
    result = run_quarterly()

    success = sum(
        1 for v in result.values()
        if isinstance(v, dict) and v.get("status") == "success"
    )
    total = len(result)
    print(f"Done: {success}/{total} task groups succeeded.")


if __name__ == "__main__":
    main()