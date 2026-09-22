"""Tests for collector_quarterly.py — quarterly data collection."""

import datetime
import pandas as pd


def _reload_quarterly(monkeypatch, tmp_path):
    """Reload collector_quarterly with patched config and logger."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)
    from src import collector_quarterly
    importlib.reload(collector_quarterly)
    return collector_quarterly


def test_run_quarterly_returns_dict(monkeypatch, tmp_path):
    """run_quarterly() should execute without error and return a result dict."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame({"code": ["510300"], "scale": [1e9]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]}))

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_holdings", lambda fund_id, holding_type: {"datas": []})
    monkeypatch.setattr(af_module, "get_index_info", lambda idx, scope: {})

    from src import collector_quarterly
    importlib.reload(collector_quarterly)
    # Stub: day 15, quarterly month (3,6,9,12)
    monkeypatch.setattr(collector_quarterly, "today", lambda: datetime.date(2026, 3, 15))
    # Skip the 1.1s rate-limit sleep between index fetches — we're mocked anyway
    monkeypatch.setattr(collector_quarterly.time, "sleep", lambda s: None)

    result = collector_quarterly.run_quarterly()

    assert isinstance(result, dict), "run_quarterly() should return a dict"
    assert "holdings" in result, "Result should contain holdings"
    assert "index_valuation" in result, "Result should contain index_valuation"


def test_run_quarterly_calls_get_holdings(monkeypatch, tmp_path):
    """run_quarterly should call get_holdings for each fund in ETF_WATCH_LIST (first 5)."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    holdings_calls = []

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    def track_holdings(fund_id, holding_type):
        holdings_calls.append((fund_id, holding_type))
        return {"datas": []}
    monkeypatch.setattr(af_module, "get_holdings", track_holdings)

    from src import collector_quarterly
    importlib.reload(collector_quarterly)
    monkeypatch.setattr(collector_quarterly, "today", lambda: datetime.date(2026, 3, 15))
    # Skip the 1.1s rate-limit sleep — we just want to verify the call pattern
    monkeypatch.setattr(collector_quarterly.time, "sleep", lambda s: None)

    collector_quarterly.run_quarterly()

    assert len(holdings_calls) == 5, f"Expected 5 get_holdings calls (first 5 funds), got {len(holdings_calls)}"
    for call in holdings_calls:
        assert call[1] == "all", f"holding_type should be 'all', got {call[1]}"