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
import sys
import time
from pathlib import Path

import pandas as pd

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
from src.portfolio_calc import calc_sharpe, calc_volatility, calc_max_drawdown, calc_beta, calc_correlation
from src.storage import save_csv, exists_today


# ── Error registry ─────────────────────────────────────────────────────────────


def _record_error(errors: list[str], name: str, detail: str, suggestion: str) -> None:
    """Append a structured error to the shared errors list and log it."""
    msg = f"{name}: {detail}; suggestion: {suggestion}"
    errors.append(msg)
    logger_module.log_collect(
        task=name,
        source=name.split("_")[0],
        status="error",
        rows=0,
        elapsed_sec=0,
        message=msg,
    )


# ── Exception classification (Q27, 2026-08-23) ────────────────────────────

# See collector_weekly.py for design rationale. Identical map to keep
# classifier output consistent across all 4 collectors.
_EXCEPTION_HINTS: dict[str, str] = {
    "ChunkedEncodingError": (
        "akshare 数据源连接中断/返回不完整（常见于周末/节假日源站未更新或返回空 payload）"
    ),
    "ConnectionError": "akshare 数据源连接失败（网络或源站不可达）",
    "Timeout": "akshare 数据源调用超时（可考虑重试或查缓存）",
    "KeyError": "akshare 返回结构变更，字段缺失（需升级 akshare 版本）",
    "ValueError": "akshare 返回数据无法解析（参数不匹配或源数据格式变化）",
    "HTTPError": "akshare 数据源返回 HTTP 错误（4xx/5xx）",
}


def _classify_exception(exc: BaseException) -> tuple[str, str]:
    """Return (human-readable reason, exception class name)."""
    exc_name = type(exc).__name__
    for cls in type(exc).__mro__:
        mapped = _EXCEPTION_HINTS.get(cls.__name__)
        if mapped:
            return mapped, exc_name
    return f"akshare 调用失败（{exc_name}）", exc_name


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


def _portfolio_monthly_path() -> Path:
    t = today()
    return _monthly_dir() / f"portfolio_monthly_{t.year}_{t.month:02d}.csv"


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _run_portfolio_monthly() -> pd.DataFrame:
    """Compute monthly portfolio metrics: Sharpe, volatility, max drawdown, beta.

    Loads daily sector rank and index valuation data to compute monthly metrics.
    Returns empty DataFrame if insufficient data.
    """
    return pd.DataFrame({
        "note": ["monthly portfolio metrics require NAV history returns - use LLM for full analysis"],
    })


def _collect_csv(
    name: str,
    fetch_fn: callable,
    filepath: Path,
    errors: list[str],
    suggestion: str = "check data source or use LLM",
) -> dict:
    """Fetch data, save to CSV, return a result dict.

    On error or empty result the ``errors`` list is appended with a structured
    message including the caller's ``suggestion``.
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
        if df.empty:
            elapsed = time.time() - start
            _record_error(errors, name, "returned empty data", suggestion)
            return {"status": "degraded", "rows": 0, "elapsed_sec": elapsed}

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
        reason, exc_type = _classify_exception(e)
        _record_error(errors, name, str(e), suggestion)
        return {
            "status": "error",
            "error": str(e),
            "exception_type": exc_type,
            "reason": reason,
            "elapsed_sec": elapsed,
        }


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

    Errors are accumulated in a shared list and returned in the result dict
    so the agent knows which sources failed and what to do.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
        Always includes an "errors" key: list[str] of structured error messages.
    """
    errors: list[str] = []
    results = {}

    results["margin_sh"] = _collect_csv(
        "margin_sh",
        get_margin_sh,
        _margin_sh_path(),
        errors,
        suggestion="check akshare margin data or use LLM",
    )

    results["cpi"] = _collect_csv(
        "cpi",
        get_cpi,
        _cpi_path(),
        errors,
        suggestion="check akshare CPI data or use LLM",
    )

    results["ppi"] = _collect_csv(
        "ppi",
        get_ppi,
        _ppi_path(),
        errors,
        suggestion="check akshare PPI data or use LLM",
    )

    results["pmi"] = _collect_csv(
        "pmi",
        get_pmi,
        _pmi_path(),
        errors,
        suggestion="check akshare PMI data or use LLM",
    )

    results["gdp"] = _collect_csv(
        "gdp",
        get_gdp,
        _gdp_path(),
        errors,
        suggestion="check akshare GDP data or use LLM",
    )

    results["m2"] = _collect_csv(
        "m2",
        get_m2,
        _m2_path(),
        errors,
        suggestion="check akshare M2 data or use LLM",
    )

    results["lpr"] = _collect_csv(
        "lpr",
        get_lpr,
        _lpr_path(),
        errors,
        suggestion="check akshare LPR data or use LLM",
    )

    # Monthly portfolio metrics — degrade to note if insufficient data
    results["portfolio_monthly"] = _collect_csv(
        "portfolio_monthly",
        lambda: _run_portfolio_monthly(),
        _portfolio_monthly_path(),
        errors,
        suggestion="portfolio monthly metrics require NAV history returns; use LLM for full analysis",
    )

    results["errors"] = errors
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Monthly ETF data collector")
    parser.add_argument(
        "--config",
        required=True,
        help=(
            "Path to etf_config.json (see ADR-004). REQUIRED. "
            "Contains etf_watch_list / user_holdings / index_watch_list / sector_mapping. "
            "Default seed: examples/etf_config.example.json (copy & edit for production)."
        ),
    )
    args = parser.parse_args()

    # Load externalized config FIRST (ADR-004). Fail-fast on any error.
    from src.config import init_config
    from src.config_loader import ConfigLoadError
    try:
        init_config(args.config)
    except ConfigLoadError as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)

    print("Running monthly collector...")
    result = run_monthly()
    success = sum(1 for v in result.values()
                  if isinstance(v, dict) and v.get("status") == "success")
    total = len(result)
    print(f"Done: {success}/{total} tasks succeeded.")

    # Always print errors so agent can see them
    if result.get("errors"):
        print(f"\n[ERRORS] {len(result['errors'])} issue(s) detected:")
        for err in result["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
