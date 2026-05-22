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


import pandas as pd

from src import config, logger as logger_module
from src.akshare_client import (
    get_etf_snapshot,
    get_margin_sh,
    get_north_flow,
    get_us_stock_index,
)
from src.storage import save_csv, save_json, exists_today, load_csv
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


def _index_valuation_path(idx: str) -> Path:
    return _daily_dir() / f"index_valuation_{idx}_{today()}.json"


def _us_index_path() -> Path:
    """Return path for US stock index data (close mode output)."""
    return _daily_dir() / f"us_stock_index_{today()}.csv"


def _sector_rank_path() -> Path:
    """Return path for sector rank aggregation output."""
    return _daily_dir() / f"sector_rank_{today()}.csv"


def _premium_path(code: str) -> Path:
    """Return path for ETF premium rate output."""
    return _daily_dir() / f"premium_{code}_{today()}.csv"


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


def _run_sector_aggregation() -> pd.DataFrame:
    """Load today's ETF snapshot and produce sector rank DataFrame.

    This is called after etf_snapshot has been collected (cache confirmed hit).
    Returns a DataFrame with sector-level aggregated statistics.
    """
    snapshot_path = str(_etf_snapshot_path())
    snapshot = load_csv(snapshot_path)
    agg = aggregate_by_sector(snapshot, config.SECTOR_MAPPING, code_col="代码", change_col="涨跌幅", volume_col="成交额")
    return rank_sectors(agg)


def _run_premium_rate_for_user_holdings() -> pd.DataFrame:
    """Compute ETF premium/discount rates for user holdings.

    Requires:
    - Yesterday's close-mode etf_snapshot (for snapshot price)
    - Today's NAV from ttfund get_nav_history

    If yesterday's snapshot is missing (e.g. morning mode run without prior close),
    logs a warning and returns an empty DataFrame.
    """
    from src.tech_indicator import calc_premium_rate
    from src.storage import load_csv

    rows = []
    yesterday = today() - datetime.timedelta(days=1)
    snapshot_path = str(_daily_dir() / f"etf_snapshot_{yesterday}.csv")

    snapshot_df = None
    try:
        snapshot_df = load_csv(snapshot_path)
    except FileNotFoundError:
        logger_module.log_collect(
            task="premium_rate",
            source="sector_rank",
            status="error",
            rows=0,
            elapsed_sec=0,
            message=f"Yesterday's snapshot not found ({snapshot_path}). Run close mode first to collect ETF snapshot before morning mode.",
        )
        return pd.DataFrame()

    for holding in config.USER_HOLDINGS:
        code = holding["code"]
        name = holding["name"]
        sector = holding["sector"]
        # snapshot price: find row by code
        snapshot_row = snapshot_df[snapshot_df["代码"] == code]
        if snapshot_row.empty:
            continue
        snapshot_price = float(snapshot_row.iloc[0]["最新价"])

        # nav: get from ttfund
        try:
            raw = get_nav_history(code, "y")
            items = raw.get("data", {}).get("nav_history", {}).get("items", [])
            if not items:
                continue
            latest_nav = float(items[0]["DWJZ"])
            premium = calc_premium_rate(snapshot_price, latest_nav)
            rows.append({
                "code": code,
                "name": name,
                "sector": sector,
                "snapshot_price": snapshot_price,
                "nav": latest_nav,
                "premium_rate": round(premium, 6),
                "premium_pct": round(premium * 100, 4),
            })
        except Exception as e:
            logger_module.log_collect(
                task=f"premium_{code}",
                source="nav_history",
                status="error",
                rows=0,
                elapsed_sec=0,
                message=f"nav fetch failed for {code}: {e}",
            )
            continue

    return pd.DataFrame(rows)


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

    from src.sector_aggregator import aggregate_by_sector, rank_sectors
    from src.config import SECTOR_MAPPING

    # 4. 核心 ETF 净值 — 遍历 ETF_WATCH_LIST
    nav_results = {}
    for etf in config.ETF_WATCH_LIST:
        code = etf["code"]
        path = _nav_path(code)

        def fetch_nav(c=code):
            raw = get_nav_history(c, "y")
            items = raw.get("data", {}).get("nav_history", {}).get("items", [])
            return pd.DataFrame(items)

        nav_results[code] = _collect_csv(f"nav_{code}", fetch_nav, path)

    results["nav"] = nav_results

    # 5. 行业板块聚合 — 基于 ETF 快照生成板块涨跌排名
    # 注意：必须在 etf_snapshot 采集完后执行，使用 snapshot 的最新价/涨跌幅/成交额
    if results.get("etf_snapshot", {}).get("status") == "success":
        results["sector_rank"] = _collect_csv(
            "sector_rank",
            lambda: _run_sector_aggregation(),
            _sector_rank_path(),
        )

    # 6. 美股收盘指数 — eastmoney 接口可能不可用，降级时返回空 DataFrame
    results["us_stock_index"] = _collect_csv(
        "us_stock_index",
        lambda: get_us_stock_index(),
        _us_index_path(),
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
        path = _index_valuation_path(idx)

        def fetch_val(i=idx):
            return get_index_info(i, "all")

        val_results[idx] = _collect_json(f"index_valuation_{idx}", fetch_val, path)

    results["index_valuation"] = val_results

    # 3. 用户持仓 ETF 溢价折价率
    # 注意：依赖昨日 close 模式采集的 ETF 快照数据
    # 如果快照缺失会正常报错并跳过（log_collect 已处理）
    for holding in config.USER_HOLDINGS:
        code = holding["code"]
        path = _premium_path(code)

        def fetch_premium(c=code):
            return _run_premium_rate_for_user_holdings()

        results[f"premium_{code}"] = _collect_csv(
            f"premium_{code}",
            fetch_premium,
            path,
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
