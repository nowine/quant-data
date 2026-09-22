"""Tests for generate_quarterly_report.py — quarterly report generation."""

import datetime
import json
import pandas as pd


def test_generate_report_returns_markdown_string(monkeypatch, tmp_path):
    """generate_report() should return a non-empty markdown string."""
    # Set up mock data dirs
    quarterly_dir = tmp_path / "quarterly"
    quarterly_dir.mkdir()
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    # Mock holdings CSV — one fund
    holdings_path = quarterly_dir / "holdings_510300_20260315.csv"
    holdings_df = pd.DataFrame({
        "代码": ["600519", "000858"],
        "名称": ["贵州茅台", "五粮液"],
        "持仓占比": [8.5, 6.2],
        "季度变化": ["+0.5%", "-0.3%"],
    })
    holdings_df.to_csv(holdings_path, index=False)

    # Mock index valuation JSON
    val_path = quarterly_dir / "index_valuation_20260315.json"
    val_data = {
        "沪深300": {"pe_ttm": 12.5, "percentile": 25.0, "roe": 11.2},
        "中证500": {"pe_ttm": 18.3, "percentile": 40.0, "roe": 9.5},
    }
    with open(val_path, "w") as f:
        json.dump(val_data, f)

    # Mock north flow CSV
    north_path = daily_dir / "north_flow_20260331.csv"
    north_df = pd.DataFrame({
        "date": ["2026-03-28", "2026-03-29", "2026-03-30", "2026-03-31"],
        "flow": [45.2, -12.3, 38.7, 22.1],
        "net": [45.2, -12.3, 38.7, 22.1],
    })
    north_df.to_csv(north_path, index=False)

    # Stub today() and config
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import generate_quarterly_report as gqr
    importlib.reload(gqr)
    monkeypatch.setattr(gqr, "today", lambda: datetime.date(2026, 3, 31))

    report = gqr.generate_report()
    assert isinstance(report, str), "generate_report() should return a string"
    assert len(report) > 100, "Report should not be empty"
    assert "# 2026 Q1" in report, "Report should contain the year and quarter header"


def test_report_contains_required_sections(monkeypatch, tmp_path):
    """Report should contain all required sections."""
    quarterly_dir = tmp_path / "quarterly"
    quarterly_dir.mkdir()
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    holdings_path = quarterly_dir / "holdings_510300_20260315.csv"
    pd.DataFrame({
        "代码": ["600519"],
        "名称": ["贵州茅台"],
        "持仓占比": [8.5],
        "季度变化": ["+0.5%"],
    }).to_csv(holdings_path, index=False)

    val_path = quarterly_dir / "index_valuation_20260315.json"
    with open(val_path, "w") as f:
        json.dump({}, f)

    north_path = daily_dir / "north_flow_20260331.csv"
    pd.DataFrame({"date": ["2026-03-31"], "flow": [10], "net": [10]}).to_csv(north_path, index=False)

    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import generate_quarterly_report as gqr
    importlib.reload(gqr)
    monkeypatch.setattr(gqr, "today", lambda: datetime.date(2026, 3, 31))

    report = gqr.generate_report()
    for section in ["数据采集情况", "核心 ETF 表现", "北向资金", "下季度展望"]:
        assert section in report, f"Report should contain section: {section}"


def test_save_report_writes_file(monkeypatch, tmp_path):
    """save_report() should write a .md file to the reports directory."""
    quarterly_dir = tmp_path / "quarterly"
    quarterly_dir.mkdir()
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import generate_quarterly_report as gqr
    importlib.reload(gqr)
    monkeypatch.setattr(gqr, "today", lambda: datetime.date(2026, 3, 31))

    report_content = "# 2026 Q1 季度报告\n\n测试内容"
    result = gqr.save_report(report_content, year=2026, quarter=1)

    assert result is True, "save_report() should return True on success"
    expected_file = reports_dir / "quarterly_report_2026_Q1.md"
    assert expected_file.exists(), f"Report file should exist at {expected_file}"
    assert expected_file.read_text() == report_content