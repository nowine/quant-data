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
    """Return True if today is the 15th of a quarter-end month (Mar/Jun/Sep/Dec).

    Kept as a helper for the CLI's "[info] not a quarterly run day" log line
    and for any future caller that wants to filter on cadence. No longer used
    to early-exit the collector (Q26, 2026-08-23 — collectors never gate on date).
    """
    d = today()
    return d.day == 15 and d.month in (3, 6, 9, 12)


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
        reason, exc_type = _classify_exception(e)
        return {
            "status": "error",
            "error": str(e),
            "exception_type": exc_type,
            "reason": reason,
            "elapsed_sec": elapsed,
        }


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
        reason, exc_type = _classify_exception(e)
        return {
            "status": "error",
            "error": str(e),
            "exception_type": exc_type,
            "reason": reason,
            "elapsed_sec": elapsed,
        }


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
    import argparse
    parser = argparse.ArgumentParser(description="Quarterly ETF data collector")
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

    if not is_quarterly_run_day():
        print(
            f"[info] Today ({today()}) is not a quarterly run day "
            "(15th of Mar/Jun/Sep/Dec). Collector will still run — "
            "akshare calls may return empty/degraded on off-cycle days; "
            "see per-task status + reason."
        )

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