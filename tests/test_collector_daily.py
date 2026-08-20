"""Tests for collector_daily.py — two run modes: close and morning."""

import datetime
import os
import pandas as pd


def _reload_collector(monkeypatch, tmp_path):
    """Reload collector_daily with patched config and logger."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)
    from src import collector_daily
    importlib.reload(collector_daily)
    return collector_daily


def test_is_trading_day_rejects_saturday(monkeypatch, tmp_path):
    """Saturday should be rejected as a non-trading day."""
    cd = _reload_collector(monkeypatch, tmp_path)
    monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 23))  # Saturday
    assert cd.is_trading_day() is False


def test_is_trading_day_rejects_sunday(monkeypatch, tmp_path):
    """Sunday should be rejected as a non-trading day."""
    cd = _reload_collector(monkeypatch, tmp_path)
    monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 24))  # Sunday
    assert cd.is_trading_day() is False


def test_is_trading_day_accepts_weekday(monkeypatch, tmp_path):
    """Monday–Friday should be accepted as trading days."""
    cd = _reload_collector(monkeypatch, tmp_path)
    monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 18))  # Monday
    assert cd.is_trading_day() is True


def test_close_mode_calls_etf_snapshot(monkeypatch, tmp_path):
    """close mode should produce an etf_snapshot result entry."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    mock_df = pd.DataFrame({"code": ["510300"], "name": ["test"]})

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    result = collector_daily.run_close_mode()
    assert "etf_snapshot" in result


def test_close_mode_calls_margin_sh(monkeypatch, tmp_path):
    """close mode should produce a margin_sh result entry."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    mock_margin_df = pd.DataFrame({"date": ["2026-05-20"], "balance": [1e9]})

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: mock_margin_df)
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    result = collector_daily.run_close_mode()
    assert "margin_sh" in result


def test_close_mode_calls_get_north_flow_with_correct_args(monkeypatch, tmp_path):
    """close mode should call get_north_flow('沪股通', 3)."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    mock_north_df = pd.DataFrame({"date": ["2026-05-20"], "flow": [100]})
    north_call_args = []

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    def track_north(sym, months):
        north_call_args.append((sym, months))
        return mock_north_df
    monkeypatch.setattr(ak_module, "get_north_flow", track_north)

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_close_mode()

    assert len(north_call_args) == 1
    assert north_call_args[0] == ("沪股通", 3), \
        f"Expected ('沪股通', 3), got {north_call_args[0]}"


def test_close_mode_iterates_nav_for_all_etfs(monkeypatch, tmp_path):
    """close mode should call get_nav_history for each ETF in ETF_WATCH_LIST."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    nav_calls = []
    def track_nav(code, rng):
        nav_calls.append(code)
        return {}
    monkeypatch.setattr(af_module, "get_nav_history", track_nav)

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_close_mode()

    etf_codes = [etf["code"] for etf in config.ETF_WATCH_LIST]
    assert len(nav_calls) == len(etf_codes), \
        f"Expected {len(etf_codes)} nav calls, got {len(nav_calls)}: {nav_calls}"
    assert nav_calls == etf_codes


def test_morning_mode_calls_get_gold_info(monkeypatch, tmp_path):
    """morning mode should call get_gold_info with scope='all'."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    import src.akshare_client as ak_module
    importlib.reload(ak_module)
    # Mock ALL akshare_client calls touched by morning_mode (etf_snapshot + 22×etf_history).
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_etf_history", lambda code: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    gold_calls = []
    def track_gold(scope):
        gold_calls.append(scope)
        return {}
    monkeypatch.setattr(af_module, "get_gold_info", track_gold)
    monkeypatch.setattr(af_module, "get_index_info", lambda idx, scope: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_morning_mode()

    assert "all" in gold_calls, f"Expected 'all' in gold_calls, got {gold_calls}"


def test_morning_mode_calls_get_index_info_for_all_indices(monkeypatch, tmp_path):
    """morning mode should call get_index_info for every index in INDEX_WATCH_LIST."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    import src.akshare_client as ak_module
    importlib.reload(ak_module)
    # Mock ALL akshare_client calls touched by morning_mode (etf_snapshot + 22×etf_history).
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_etf_history", lambda code: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    index_calls = []
    def track_index(idx, scope):
        index_calls.append(idx)
        return {}
    monkeypatch.setattr(af_module, "get_index_info", track_index)
    monkeypatch.setattr(af_module, "get_gold_info", lambda scope: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_morning_mode()

    assert len(index_calls) == len(config.INDEX_WATCH_LIST), \
        f"Expected {len(config.INDEX_WATCH_LIST)} index calls, got {len(index_calls)}: {index_calls}"
    assert index_calls == config.INDEX_WATCH_LIST


def test_close_mode_output_structure(monkeypatch, tmp_path):
    """run_close_mode should return a dict with task keys and status field."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame({"code": ["510300"]}))
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame({"date": ["2026-05-20"]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    result = collector_daily.run_close_mode()

    assert isinstance(result, dict)
    for task in ["etf_snapshot", "margin_sh", "north_flow"]:
        assert task in result, f"Missing task: {task}"
        assert "status" in result[task]


def test_morning_mode_output_structure(monkeypatch, tmp_path):
    """run_morning_mode should return a dict with task keys and status field."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_gold_info", lambda scope: {})
    monkeypatch.setattr(af_module, "get_index_info", lambda idx, scope: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    result = collector_daily.run_morning_mode()

    assert isinstance(result, dict)
    assert "gold_macro" in result, f"Missing task: gold_macro"
    assert "status" in result["gold_macro"], f"gold_macro result missing status: {result['gold_macro']}"
    assert "index_valuation" in result, f"Missing task: index_valuation"
    # index_valuation is a dict of index_name -> result dict with status
    iv = result["index_valuation"]
    assert isinstance(iv, dict), f"index_valuation should be dict, got {type(iv)}"
    for idx_name, idx_result in iv.items():
        assert "status" in idx_result, f"index_valuation[{idx_name}] missing status: {idx_result}"


def test_cli_close_mode(monkeypatch, tmp_path):
    """CLI --mode=close should invoke run_close_mode."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    close_called = False
    def mock_close(extra=None):
        nonlocal close_called
        close_called = True
        return {}
    monkeypatch.setattr(collector_daily, "run_close_mode", mock_close)

    import sys
    monkeypatch.setattr(sys, "argv", ["collector_daily.py", "--mode=close", "--config", "/tmp/fake.json"]); monkeypatch.setattr("src.config.init_config", lambda path: None)
    collector_daily.main()

    assert close_called, "main() should call run_close_mode for --mode=close"


def test_cli_morning_mode(monkeypatch, tmp_path):
    """CLI --mode=morning should invoke run_morning_mode."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_gold_info", lambda scope: {})
    monkeypatch.setattr(af_module, "get_index_info", lambda idx, scope: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    morning_called = False
    def mock_morning(extra=None):
        nonlocal morning_called
        morning_called = True
        return {}
    monkeypatch.setattr(collector_daily, "run_morning_mode", mock_morning)

    import sys
    monkeypatch.setattr(sys, "argv", ["collector_daily.py", "--mode=morning", "--config", "/tmp/fake.json"]); monkeypatch.setattr("src.config.init_config", lambda path: None)
    collector_daily.main()

    assert morning_called, "main() should call run_morning_mode for --mode=morning"


def test_cli_defaults_to_close(monkeypatch, tmp_path):
    """Running with no --mode arg should default to close mode."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    close_called = False
    def mock_close(extra=None):
        nonlocal close_called
        close_called = True
        return {}
    monkeypatch.setattr(collector_daily, "run_close_mode", mock_close)

    import sys
    monkeypatch.setattr(sys, "argv", ["collector_daily.py", "--config", "/tmp/fake.json"]); monkeypatch.setattr("src.config.init_config", lambda path: None)
    collector_daily.main()

    assert close_called


def test_close_mode_saves_daily_files(monkeypatch, tmp_path):
    """close mode should create files in daily/ directory."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame({"code": ["510300"], "name": ["test"]}))
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame({"date": ["2026-05-20"], "balance": [1e9]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]}))

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_close_mode()

    daily_dir = tmp_path / "daily"
    assert daily_dir.exists()
    files = list(daily_dir.iterdir())
    assert len(files) >= 3, \
        f"Expected at least 3 daily files, got {len(files)}: {[f.name for f in files]}"


def test_north_flow_saved_to_correct_path(monkeypatch, tmp_path):
    """north_flow data should be saved to daily/north_flow_{date}.csv."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_snapshot", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]}))

    from src import akshare_fund_client as af_module
    importlib.reload(af_module)
    monkeypatch.setattr(af_module, "get_nav_history", lambda code, rng: {})

    from src import collector_daily
    importlib.reload(collector_daily)
    monkeypatch.setattr(collector_daily, "today", lambda: datetime.date(2026, 5, 20))

    collector_daily.run_close_mode()

    daily_dir = tmp_path / "daily"
    north_file = daily_dir / "north_flow_2026-05-20.csv"
    assert north_file.exists(), f"Expected {north_file} to exist"
