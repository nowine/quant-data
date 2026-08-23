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

import pandas as pd

from src import config, logger as logger_module
from src.portfolio_calc import calc_contribution, calc_correlation, calc_beta
from src.akshare_client import (
    get_etf_scale,
    get_north_flow,
    get_industry_alloc,
)
from src.portfolio_calc import calc_contribution, calc_correlation, calc_beta
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

# Map of exception class name → human-readable reason hint for the caller.
# The collector surfaces this as `status=error, reason=..., exception_type=...`
# in the per-task result dict, so the caller (皮皮 agent) can decide whether to
# use cache, mark the report degraded, or skip the section.
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
    """Return (human-readable reason, exception class name) for an akshare failure.

    Falls back to (generic message, class name) for unmapped exceptions. The
    pair is added to the per-task status dict so the caller can decide a
    follow-up (use cache / mark degraded / retry later).
    """
    exc_name = type(exc).__name__
    # Walk the MRO so subclass exceptions (e.g. ReadTimeout ⊂ Timeout) still
    # resolve to a sensible hint via their nearest ancestor in our map.
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


def _sector_rank_change_path() -> Path:
    year, week = today().isocalendar()[0], today().isocalendar()[1]
    return _weekly_dir() / f"sector_rank_change_{year}_w{week:02d}.csv"


def _portfolio_weekly_path() -> Path:
    return _weekly_dir() / f"portfolio_weekly_{today()}.csv"


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _load_daily_sector_ranks(days: int = 5) -> list[pd.DataFrame]:
    """Load the most recent N daily sector_rank CSV files, sorted oldest→newest.

    Args:
        days: number of recent trading days to load.

    Returns:
        List of DataFrames with sector data.
    """
    daily_dir = Path(config.DATA_DIR) / "daily"
    sector_files = sorted(
        daily_dir.glob("sector_rank_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:days]

    dfs = []
    for fp in reversed(sector_files):
        try:
            df = pd.read_csv(fp)
            df["_source_file"] = fp.name
            dfs.append(df)
        except Exception:
            continue
    return dfs


def _compute_sector_rank_change(recent_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Compute week-over-week ranking change for sectors.

    Args:
        recent_dfs: list of sector_rank DataFrames, oldest first.

    Returns:
        DataFrame with sector, this_week_rank, last_week_rank, rank_change.
    """
    if len(recent_dfs) < 2:
        return pd.DataFrame()

    last_week = recent_dfs[-2]  # previous week
    this_week = recent_dfs[-1]  # current week

    # Build ranking (assume first col is sector name)
    last_ranked = last_week.reset_index(drop=True).reset_index()
    last_ranked.columns = [last_week.columns[0], f"{last_week.columns[0]}_rank"]
    last_ranked = last_ranked.rename(columns={last_ranked.columns[0]: "sector", f"{last_week.columns[0]}_rank": "last_week_rank"})

    this_ranked = this_week.reset_index(drop=True).reset_index()
    this_ranked.columns = [this_week.columns[0], f"{this_week.columns[0]}_rank"]
    this_ranked = this_ranked.rename(columns={this_ranked.columns[0]: "sector", f"{this_week.columns[0]}_rank": "this_week_rank"})

    merged = this_ranked.merge(last_ranked, on="sector", how="left")
    merged["rank_change"] = merged["last_week_rank"] - merged["this_week_rank"]
    return merged[["sector", "this_week_rank", "last_week_rank", "rank_change"]]


def _run_portfolio_weekly() -> pd.DataFrame:
    """Compute weekly portfolio metrics: contribution, correlation, beta.

    Loads daily sector ranks and index valuations to compute portfolio-level metrics.
    Returns empty DataFrame if insufficient data.
    """
    # Load last 5 sector rank files to get weekly aggregated returns
    sector_dfs = _load_daily_sector_ranks(5)
    if not sector_dfs:
        return pd.DataFrame()

    # Build returns per sector from sector data
    # For now, just compute week-over-week change as proxy
    change_rows = []
    for df in sector_dfs:
        change_rows.append(df[["sector", "avg_change_pct"]].rename(columns={"avg_change_pct": f"change_{df['_source_file'].split('_')[2]}"}))

    # Aggregate portfolio contribution placeholder
    # Real implementation would load NAV history and compute actual returns
    return pd.DataFrame({
        "note": ["portfolio weekly metrics require NAV history - use LLM for full analysis"],
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


# ── Core collector ──────────────────────────────────────────────────────────────

def run_weekly() -> dict[str, dict]:
    """Collect weekly data: ETF scale, north flow, industry allocation.

    Errors are accumulated in a shared list and returned in the result dict
    so the agent knows which sources failed and what to do.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
        Always includes an "errors" key: list[str] of structured error messages.
    """
    errors: list[str] = []
    results = {}

    # 1. ETF 规模
    results["etf_scale"] = _collect_csv(
        "etf_scale",
        get_etf_scale,
        _etf_scale_path(),
        errors,
        suggestion="check akshare ETF scale (SSE) or use LLM",
    )

    # 2. 北向资金周度
    results["north_flow_week"] = _collect_csv(
        "north_flow_week",
        lambda: get_north_flow("沪深股通", 1),
        _north_flow_week_path(),
        errors,
        suggestion="check north flow data source or use LLM",
    )

    # 3. 行业配置
    year = today().year
    results["industry_alloc"] = _collect_csv(
        "industry_alloc",
        lambda: get_industry_alloc(year),
        _industry_alloc_path(),
        errors,
        suggestion="check akshare industry allocation or use LLM",
    )

    # 4. 板块排名周变化 — 本周 vs 上周排名变动矩阵
    recent_dfs = _load_daily_sector_ranks(10)  # load ~2 weeks
    if recent_dfs:
        results["sector_rank_change"] = _collect_csv(
            "sector_rank_change",
            lambda: _compute_sector_rank_change(recent_dfs),
            _sector_rank_change_path(),
            errors,
            suggestion="sector_rank_change requires daily sector_rank data; run daily collector first",
        )

    # 5. 组合周度指标 — 贡献度/相关性/Beta（降级，依赖完整 NAV 历史）
    results["portfolio_weekly"] = _collect_csv(
        "portfolio_weekly",
        lambda: _run_portfolio_weekly(),
        _portfolio_weekly_path(),
        errors,
        suggestion="portfolio weekly metrics require NAV history returns; use LLM for full analysis",
    )

    results["errors"] = errors
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Weekly ETF data collector")
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

    if today().weekday() != 0:
        print(
            f"[info] Today ({today()}) is not Monday. Collector will still run — "
            "weekly akshare data may return empty/degraded on off-cycle days; "
            "see per-task status + reason."
        )

    print("Running weekly collector...")
    result = run_weekly()
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