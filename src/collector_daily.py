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
    get_etf_history,
    get_margin_sh,
    get_north_flow,
    get_us_stock_index,
)
from src.akshare_fund_client import get_nav_history, get_gold_info, get_index_info
from src.storage import save_csv, save_json, exists_today, load_csv
from src.tech_indicator import (
    calc_ma,
    calc_rsi,
    calc_atr,
    calc_volume_ratio,
    calc_bollinger,
    calc_macd,
    calc_premium_rate,
)
from src.portfolio_calc import (
    calc_sharpe,
    calc_volatility,
    calc_max_drawdown,
    calc_beta,
    calc_correlation,
    calc_contribution,
)


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


def _tech_indicator_path(code: str) -> Path:
    """Return path for ETF technical indicators output."""
    return _daily_dir() / f"tech_indicator_{code}_{today()}.csv"


# ── Error registry ─────────────────────────────────────────────────────────────
#
# Structured error list passed through the call stack so the agent always
# knows which data sources failed and what to do about it.
# Each entry format: "{task_name}: {detail}; suggestion: {action}"


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_csv(
    name: str,
    fetch_fn: callable,
    filepath: Path,
    errors: list[str],
    suggestion: str = "check data source or use LLM",
) -> dict:
    """Fetch data, save to CSV, return a result dict.

    On error or empty result the ``errors`` list is appended with a structured
    message including the caller's ``suggestion`` (e.g. "use LLM search").
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
        _record_error(errors, name, str(e), suggestion)
        return {"status": "error", "error": str(e), "elapsed_sec": elapsed}


def _collect_json(
    name: str,
    fetch_fn: callable,
    filepath: Path,
    errors: list[str],
    suggestion: str = "check data source or use LLM",
) -> dict:
    """Fetch data (dict/list), save to JSON, return a result dict.

    On error or empty result the ``errors`` list is appended with a structured
    message including the caller's ``suggestion`` (e.g. "use LLM search").
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
        data = fetch_fn()
        if not data:
            elapsed = time.time() - start
            _record_error(errors, name, "returned empty data", suggestion)
            return {"status": "degraded", "elapsed_sec": elapsed}

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
        _record_error(errors, name, str(e), suggestion)
        return {"status": "error", "error": str(e), "elapsed_sec": elapsed}


def _run_sector_aggregation() -> pd.DataFrame:
    """Load today's ETF snapshot and produce sector rank DataFrame.

    This is called after etf_snapshot has been collected (cache confirmed hit).
    Returns a DataFrame with sector-level aggregated statistics.
    """
    from src.sector_aggregator import aggregate_by_sector, rank_sectors

    snapshot_path = str(_etf_snapshot_path())
    snapshot = load_csv(snapshot_path)
    agg = aggregate_by_sector(snapshot, config.SECTOR_MAPPING, code_col="代码", change_col="涨跌幅")
    return rank_sectors(agg)


def _run_premium_rate_for_holdings(holders: list[dict]) -> pd.DataFrame:
    """Compute ETF premium/discount rates for an arbitrary holder list.

    Requires:
    - Yesterday's close-mode etf_snapshot (for snapshot price)
    - Today's NAV from akshare_fund_client get_nav_history

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

    for holding in holders:
        code = holding["code"]
        name = holding.get("name", "")
        sector = holding.get("sector")
        # snapshot price: find row by code
        snapshot_row = snapshot_df[snapshot_df["代码"] == code]
        if snapshot_row.empty:
            continue
        snapshot_price = float(snapshot_row.iloc[0]["最新价"])

        # nav: get from akshare_fund_client
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


def _run_premium_rate_for_user_holdings() -> pd.DataFrame:
    """Back-compat thin wrapper for USER_HOLDINGS — see _run_premium_rate_for_holdings."""
    return _run_premium_rate_for_holdings(config.USER_HOLDINGS)


# ── Mode: close ────────────────────────────────────────────────────────────────

def run_close_mode() -> dict[str, dict]:
    """Collect end-of-day data: ETF snapshot, margin, north flow, NAV.

    Runs collect_if_missing for each item so already-captured files are skipped.
    Errors are accumulated in a shared list and returned in the result dict
    so the agent knows which sources failed and what to do.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
        Always includes an "errors" key: list[str] of structured error messages.
    """
    errors: list[str] = []
    results = {}

    # 1. ETF 全市场行情快照
    results["etf_snapshot"] = _collect_csv(
        "etf_snapshot",
        get_etf_snapshot,
        _etf_snapshot_path(),
        errors,
        suggestion="use LLM to search current ETF market data",
    )

    # 2. 融资融券余额 (SH)
    results["margin_sh"] = _collect_csv(
        "margin_sh",
        get_margin_sh,
        _margin_sh_path(),
        errors,
        suggestion="check akshare margin data or use LLM",
    )

    # 3. 北向资金近 3 月
    def fetch_north():
        return get_north_flow("沪股通", 3)

    results["north_flow"] = _collect_csv(
        "north_flow",
        fetch_north,
        _north_flow_path(),
        errors,
        suggestion="check north flow data source or use LLM",
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

        nav_results[code] = _collect_csv(
            f"nav_{code}",
            fetch_nav,
            path,
            errors,
            suggestion="check akshare etf_history interface or use LLM",
        )

    results["nav"] = nav_results

    # 5. 行业板块聚合 — 基于 ETF 快照生成板块涨跌排名
    if results.get("etf_snapshot", {}).get("status") == "success":
        results["sector_rank"] = _collect_csv(
            "sector_rank",
            lambda: _run_sector_aggregation(),
            _sector_rank_path(),
            errors,
            suggestion="sector_rank requires etf_snapshot - check data pipeline",
        )

    # 6. 美股收盘指数 — eastmoney 接口不可用，降级返回空 DataFrame
    results["us_stock_index"] = _collect_csv(
        "us_stock_index",
        lambda: get_us_stock_index(),
        _us_index_path(),
        errors,
        suggestion="use LLM to search current US stock index data (Nasdaq/S&P/Dow)",
    )

    results["errors"] = errors
    return results


def _run_tech_indicators_for_holdings(holders: list[dict]) -> pd.DataFrame:
    """Compute technical indicators for an arbitrary holder list.

    Fetches OHLCV history from akshare get_etf_history, computes MA20/60,
    RSI, ATR, Bollinger, MACD, volume_ratio.
    Returns empty DataFrame if no data available.
    """
    rows = []
    for holding in holders:
        code = holding["code"]
        name = holding.get("name", "")
        sector = holding.get("sector")

        # Get OHLCV history from akshare (open/high/low/close/volume)
        try:
            ohlcv_df = get_etf_history(code)
            if ohlcv_df.empty:
                continue
            required_cols = {"close", "volume"}
            if not required_cols.issubset(set(ohlcv_df.columns)):
                continue

            # Sort by date ascending for indicator calculation
            ohlcv_df = ohlcv_df.sort_values("date")

            # Calculate indicators using OHLCV data
            ma_result = calc_ma(ohlcv_df, (20, 60))
            indicators = {
                "ma20": ma_result["MA20"],
                "ma60": ma_result["MA60"],
                "rsi14": calc_rsi(ohlcv_df, 14),
                "atr14": calc_atr(ohlcv_df, 14),
            }
            boll = calc_bollinger(ohlcv_df, 20)
            macd_val = calc_macd(ohlcv_df)
            vol_ratio = calc_volume_ratio(ohlcv_df, 20)

            # Use latest values
            latest_price = float(ohlcv_df["close"].iloc[-1])
            rows.append({
                "code": code,
                "name": name,
                "sector": sector,
                "price": latest_price,
                "ma20": round(float(indicators["ma20"].iloc[-1]) if len(indicators["ma20"]) else float("nan"), 4),
                "ma60": round(float(indicators["ma60"].iloc[-1]) if len(indicators["ma60"]) else float("nan"), 4),
                "rsi14": round(float(indicators["rsi14"].iloc[-1]) if len(indicators["rsi14"]) else float("nan"), 4),
                "atr14": round(float(indicators["atr14"].iloc[-1]) if len(indicators["atr14"]) else float("nan"), 4),
                "boll_upper": round(float(boll["BB_UPPER"].iloc[-1]) if len(boll["BB_UPPER"]) else float("nan"), 4),
                "boll_mid": round(float(boll["BB_MIDDLE"].iloc[-1]) if len(boll["BB_MIDDLE"]) else float("nan"), 4),
                "boll_lower": round(float(boll["BB_LOWER"].iloc[-1]) if len(boll["BB_LOWER"]) else float("nan"), 4),
                "macd_dif": round(float(macd_val["DIF"].iloc[-1]) if len(macd_val["DIF"]) else float("nan"), 4),
                "macd_dea": round(float(macd_val["DEA"].iloc[-1]) if len(macd_val["DEA"]) else float("nan"), 4),
                "macd_hist": round(float(macd_val["MACD"].iloc[-1]) if len(macd_val["MACD"]) else float("nan"), 4),
                "volume_ratio": round(float(vol_ratio.iloc[-1]) if len(vol_ratio) else float("nan"), 4),
            })
        except Exception as e:
            logger_module.log_collect(
                task=f"tech_indicator_{code}",
                source="etf_history",
                status="error",
                rows=0,
                elapsed_sec=0,
                message=f"tech indicators failed for {code}: {e}",
            )
            continue

    return pd.DataFrame(rows)


def _run_tech_indicators_for_user_holdings() -> pd.DataFrame:
    """Back-compat thin wrapper for USER_HOLDINGS — see _run_tech_indicators_for_holdings."""
    return _run_tech_indicators_for_holdings(config.USER_HOLDINGS)


# ── Mode: morning ──────────────────────────────────────────────────────────────

def run_morning_mode() -> dict[str, dict]:
    """Collect pre-market data: gold + macro, index valuations, premium rates.

    Errors are accumulated in a shared list and returned in the result dict
    so the agent knows which sources failed and what to do.

    Returns:
        Dict mapping task name -> result dict with status/rows/elapsed_sec.
        Always includes an "errors" key: list[str] of structured error messages.
    """
    errors: list[str] = []
    results = {}

    # 1. 黄金 + 宏观指标
    results["gold_macro"] = _collect_json(
        "gold_macro",
        lambda: get_gold_info("all"),
        _gold_macro_path(),
        errors,
        suggestion="check akshare gold/macro interface or use LLM (Phase 2 P2-1)",
    )

    # 2. 核心指数估值分位 — 遍历 INDEX_WATCH_LIST
    val_results = {}
    for idx in config.INDEX_WATCH_LIST:
        path = _index_valuation_path(idx)

        def fetch_val(i=idx):
            return get_index_info(i, "all")

        val_results[idx] = _collect_json(
            f"index_valuation_{idx}",
            fetch_val,
            path,
            errors,
            suggestion=f"check akshare index valuation for {idx} or use LLM (Phase 2 P2-3)",
        )

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
            errors,
            suggestion=f"premium for {code} requires yesterday's snapshot; run close mode first",
        )

    # 4. 技术指标 — 基于 akshare get_etf_history OHLCV 计算 MA/RSI/ATR/Bollinger/MACD/量比
    for holding in config.USER_HOLDINGS:
        code = holding["code"]
        path = _tech_indicator_path(code)

        def fetch_tech(c=code):
            return _run_tech_indicators_for_user_holdings()

        results[f"tech_indicator_{code}"] = _collect_csv(
            f"tech_indicator_{code}",
            fetch_tech,
            path,
            errors,
            suggestion=f"check akshare etf_history for {code} or use LLM",
        )

    results["errors"] = errors
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

    # Always print errors so agent can see them
    if result.get("errors"):
        print(f"\n[ERRORS] {len(result['errors'])} issue(s) detected:")
        for err in result["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
