"""Monthly data collector — runs on the first trading day of each month at 08:30.

Collects:
  1. 融资融券月报  -> monthly/margin_sh_{year}_{month}.csv
  2. CPI           -> monthly/cpi_{year}.csv
  3. PPI           -> monthly/ppi_{year}.csv
  4. PMI           -> monthly/pmi_{year}.csv
  5. GDP           -> monthly/gdp_{year}.csv
  6. M2            -> monthly/m2_{year}.csv
  7. LPR           -> monthly/lpr_{year}.csv

Usage:
    python collector_monthly.py
"""

import datetime
import time
from pathlib import Path

from src import config, logger as logger_module
from src.akshare_client import (
    get_margin_sh,
    get_cpi,
    get_ppi,
    get_pmi,
    get_gdp,
    get_m2,
    get_lpr,
)
from src.storage import save_csv, exists_today


# ── Clock stub ─────────────────────────────────────────────────────────────────

def today() -> datetime.date:
    """Return today's date. Stubbed in tests."""
    return datetime.date.today()


# ── File paths ─────────────────────────────────────────────────────────────────

def _monthly_dir() -> Path:
    """Return the monthly data directory."""
    d = Path(config.DATA_DIR) / "monthly"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _margin_sh_path() -> Path:
    t = today()
    return _monthly_dir() / f"margin_sh_{t.year}_{t.month:02d}.csv"


def _cpi_path() -> Path:
    return _monthly_dir() / f"cpi_{today().year}.csv"


def _ppi_path() -> Path:
    return _monthly_dir() / f"ppi_{today().year}.csv"


def _pmi_path() -> Path:
    return _monthly_dir() / f"pmi_{today().year}.csv"


def _gdp_path() -> Path:
    return _monthly_dir() / f"gdp_{today().year}.csv"


def _m2_path() -> Path:
    return _monthly_dir() / f"m2_{today().year}.csv"


def _lpr_path() -> Path:
    return _monthly_dir() / f"lpr_{today().year}.csv"


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _collect_csv(
    name: str,
    fetch_fn: callable,
    filepath: Path,
) -> dict:
    """Fetch data, save to CSV, return a result dict."""
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


# ── Macro data collector (for get_macro_data) ──────────────────────────────────

def get_macro_data() -> dict:
    """Fetch all macro data series and return a dict of DataFrames.

    Returns:
        Dict mapping series name -> DataFrame (or None on error).
    """
    results = {}

    fetchers = {
        "cpi": (get_cpi, _cpi_path()),
        "ppi": (get_ppi, _ppi_path()),
        "pmi": (get_pmi, _pmi_path()),
        "gdp": (get_gdp, _gdp_path()),
        "m2": (get_m2, _m2_path()),
        "lpr": (get_lpr, _lpr_path()),
        "margin_sh": (get_margin_sh, _margin_sh_path()),
    }

    for name, (fn, _path) in fetchers.items():
        try:
            results[name] = fn()
        except Exception:
            results[name] = None

    return results


# ── Core collector ──────────────────────────────────────────────────────────────

def run_monthly() -> dict[str, dict]:
    """Collect monthly macro data.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
    """
    results = {}

    results["margin_sh"] = _collect_csv(
        "margin_sh",
        get_margin_sh,
        _margin_sh_path(),
    )

    results["cpi"] = _collect_csv(
        "cpi",
        get_cpi,
        _cpi_path(),
    )

    results["ppi"] = _collect_csv(
        "ppi",
        get_ppi,
        _ppi_path(),
    )

    results["pmi"] = _collect_csv(
        "pmi",
        get_pmi,
        _pmi_path(),
    )

    results["gdp"] = _collect_csv(
        "gdp",
        get_gdp,
        _gdp_path(),
    )

    results["m2"] = _collect_csv(
        "m2",
        get_m2,
        _m2_path(),
    )

    results["lpr"] = _collect_csv(
        "lpr",
        get_lpr,
        _lpr_path(),
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
        task="monthly_summary",
        source="monthly",
        status="summary",
        rows=total,
        elapsed_sec=0,
        message=f"monthly: {success} success, {skipped} skipped, {errors} errors",
    )

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Running monthly collector...")
    result = run_monthly()
    success = sum(1 for v in result.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    total = len(result)
    print(f"Done: {success}/{total} tasks succeeded.")


if __name__ == "__main__":
    main()
