"""Quarterly report generator — runs on the last trading day of each quarter.

Generates a Markdown-formatted quarterly report combining:
  - 公募基金持仓数据 (quarterly/holdings_*.csv)
  - 北向资金数据 (daily/north_flow_*.csv)
  - 指数估值数据 (quarterly/index_valuation_*.json)

Output: reports/quarterly_report_{year}_Q{q}.md

Execution: python generate_quarterly_report.py [--year YYYY] [--quarter 1|2|3|4]
"""

import datetime
import json
import sys
from pathlib import Path

import pandas as pd

from src import config, logger as logger_module


# ── Clock stub ─────────────────────────────────────────────────────────────────

def today() -> datetime.date:
    """Return today's date. Stubbed in tests."""
    return datetime.date.today()


# ── File paths ─────────────────────────────────────────────────────────────────

def _quarterly_dir() -> Path:
    d = Path(config.DATA_DIR) / "quarterly"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _daily_dir() -> Path:
    d = Path(config.DATA_DIR) / "daily"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reports_dir() -> Path:
    d = Path(config.DATA_DIR) / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _latest_holdings_file(date_str: str) -> Path | None:
    """Find the most recent holdings CSV for any fund on or before date_str."""
    quarterly = _quarterly_dir()
    candidates = sorted(quarterly.glob("holdings_*_*.csv"), reverse=True)
    for p in candidates:
        # extract date from filename: holdings_{code}_{date}.csv
        fname = p.stem  # e.g. holdings_510300_20260315
        parts = fname.split("_")
        if len(parts) >= 3:
            file_date = parts[-1]
            if file_date <= date_str:
                return p
    return None


def _latest_north_flow_file(quarter_end: datetime.date) -> Path | None:
    """Find the most recent north_flow CSV on or before quarter_end date."""
    daily = _daily_dir()
    quarter_str = quarter_end.strftime("%Y%m%d")
    candidates = sorted(
        [p for p in daily.glob("north_flow_*.csv") if p.stem.split("_")[-1] <= quarter_str],
        reverse=True,
    )
    return candidates[0] if candidates else None


# ── Data loading helpers ───────────────────────────────────────────────────────

def _load_holdings_summary() -> dict:
    """Load all holdings CSVs and return a dict keyed by fund code."""
    quarterly = _quarterly_dir()
    holdings = {}
    for path in quarterly.glob("holdings_*_*.csv"):
        fname = path.stem
        parts = fname.split("_")
        if len(parts) >= 3:
            fund_code = parts[2]
        else:
            fund_code = "unknown"
        try:
            df = pd.read_csv(path)
            holdings[fund_code] = df
        except Exception:
            holdings[fund_code] = pd.DataFrame()
    return holdings


def _load_north_flow(quarter_end: datetime.date) -> pd.DataFrame:
    """Load the most recent north flow CSV for the quarter."""
    path = _latest_north_flow_file(quarter_end)
    if path is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        return pd.DataFrame()


def _load_index_valuation() -> dict:
    """Load the most recent index valuation JSON."""
    quarterly = _quarterly_dir()
    candidates = sorted(quarterly.glob("index_valuation_*.json"), reverse=True)
    if not candidates:
        return {}
    try:
        with open(candidates[0]) as f:
            return json.load(f)
    except Exception:
        return {}


# ── Metrics computation ─────────────────────────────────────────────────────────

def _compute_etf_performance() -> list[dict]:
    """Compute quarterly performance for each ETF in the watch list."""
    results = []
    daily = _daily_dir()
    quarter_end = today()
    quarter_start = quarter_end - datetime.timedelta(days=90)

    for etf in config.ETF_WATCH_LIST:
        code = etf["code"]
        nav_files = list(daily.glob(f"nav_{code}_*.csv"))
        if not nav_files:
            continue
        # Get first and last NAV around quarter
        try:
            df = pd.read_csv(sorted(nav_files)[0])
            # Try multiple column names
            nav_col = None
            date_col = None
            for c in ["单位净值", "NAV", "净值", "nav"]:
                if c in df.columns:
                    nav_col = c
                    break
            for c in ["日期", "date", "交易日期"]:
                if c in df.columns:
                    date_col = c
                    break
            if nav_col is None or date_col is None:
                continue
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)
            df_start = df[df[date_col] >= pd.Timestamp(quarter_start)]
            df_end = df[df[date_col] <= pd.Timestamp(quarter_end)]
            if df_start.empty or df_end.empty:
                continue
            nav_start = df_start.iloc[0][nav_col]
            nav_end = df_end.iloc[-1][nav_col]
            change_pct = ((nav_end - nav_start) / nav_start) * 100
            # Load current holdings for change
            holdings_dict = _load_holdings_summary()
            fund_holdings = holdings_dict.get(code, pd.DataFrame())
            change_str = ""
            if not fund_holdings.empty and "季度变化" in fund_holdings.columns:
                change_str = ", ".join(fund_holdings["季度变化"].dropna().astype(str).head(3))
            results.append({
                "code": code,
                "name": etf["name"],
                "quarter_change": f"{change_pct:+.2f}%",
                "holdings_change": change_str,
            })
        except Exception:
            continue

    return results


def _compute_north_flow_summary(df: pd.DataFrame) -> dict:
    """Compute north flow stats: total net inflow and trend."""
    if df.empty or "net" not in df.columns:
        return {"total": 0, "trend": "数据不足"}
    total = df["net"].sum()
    positive_days = (df["net"] > 0).sum()
    total_days = len(df)
    if total > 0:
        trend = "净流入"
    elif total < 0:
        trend = "净流出"
    else:
        trend = "持平"
    return {
        "total": f"{total:.1f}",
        "trend": trend,
        "positive_ratio": f"{positive_days}/{total_days}",
    }


# ── Report generation ──────────────────────────────────────────────────────────

def generate_report() -> str:
    """Generate the quarterly report as a markdown string."""
    date = today()
    # Determine quarter from month
    quarter = (date.month - 1) // 3 + 1
    year = date.year

    # Load data
    holdings_dict = _load_holdings_summary()
    quarter_end = date
    north_df = _load_north_flow(quarter_end)
    index_val = _load_index_valuation()

    # Compute metrics
    etf_perf = _compute_etf_performance()
    north_summary = _compute_north_flow_summary(north_df)

    # Count holdings
    holdings_count = sum(len(df) for df in holdings_dict.values())
    etf_count = len(etf_perf)
    north_days = len(north_df)

    # Build report
    lines = []
    lines.append(f"# {year} Q{quarter} 季度报告")
    lines.append("")
    lines.append("## 数据采集情况")
    lines.append(f"- ETF 净值采集：{etf_count} 只")
    lines.append(f"- 北向资金：{north_days} 天")
    lines.append(f"- 行业配置：{holdings_count} 条持仓记录")
    lines.append("")

    lines.append("## 核心 ETF 表现")
    if etf_perf:
        lines.append("| 代码 | 名称 | 季度涨跌幅 | 持仓变化 |")
        lines.append("|------|------|-----------|---------|")
        for row in etf_perf[:10]:
            lines.append(f"| {row['code']} | {row['name']} | {row['quarter_change']} | {row['holdings_change']} |")
    else:
        lines.append("_暂无数据_")
    lines.append("")

    lines.append("## 北向资金")
    lines.append(f"- 季度净流入：{north_summary['total']} 亿元")
    lines.append(f"- 趋势：{north_summary['trend']}")
    if "positive_ratio" in north_summary:
        lines.append(f"- 净流入天数：{north_summary['positive_ratio']}")
    lines.append("")

    lines.append("## 指数估值分位")
    if index_val:
        lines.append("| 指数 | PE-TTM | 历史分位 | ROE |")
        lines.append("|------|--------|---------|-----|")
        for idx_name, data in list(index_val.items())[:10]:
            pe = data.get("pe_ttm", "N/A")
            pct = data.get("percentile", "N/A")
            roe = data.get("roe", "N/A")
            lines.append(f"| {idx_name} | {pe} | {pct}% | {roe}% |")
    else:
        lines.append("_暂无数据_")
    lines.append("")

    lines.append("## 下季度展望")
    lines.append("（空，由用户填写）")
    lines.append("")

    return "\n".join(lines)


def save_report(content: str, year: int, quarter: int) -> bool:
    """Write the report markdown to reports/quarterly_report_{year}_Q{quarter}.md.

    Returns True on success, False on error.
    """
    reports_dir = _reports_dir()
    filename = f"quarterly_report_{year}_Q{quarter}.md"
    filepath = reports_dir / filename
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        logger_module.log_collect(
            task="quarterly_report",
            source=filename,
            status="success",
            rows=1,
            elapsed_sec=0,
            message=f"Saved quarterly report to {filepath}",
        )
        return True
    except Exception as e:
        logger_module.log_collect(
            task="quarterly_report",
            source=filename,
            status="error",
            rows=0,
            elapsed_sec=0,
            message=str(e),
        )
        return False


def main() -> None:
    """CLI entry point."""
    year = today().year
    quarter = (today().month - 1) // 3 + 1

    # Allow override via args
    if len(sys.argv) >= 3:
        year = int(sys.argv[1])
        quarter = int(sys.argv[2])

    report = generate_report()
    save_report(report, year, quarter)
    print(f"Generated quarterly report for {year} Q{quarter}")
    print(f"Output: {config.DATA_DIR}/reports/quarterly_report_{year}_Q{quarter}.md")


if __name__ == "__main__":
    main()