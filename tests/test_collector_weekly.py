"""Tests for collector_weekly.py — weekly data collection on Mondays."""

import datetime
import os
import pandas as pd


def _reload_weekly(monkeypatch, tmp_path):
    """Reload collector_weekly with patched config and logger."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)
    from src import collector_weekly
    importlib.reload(collector_weekly)
    return collector_weekly


def test_collector_weekly_runs(monkeypatch, tmp_path):
    """collector_weekly should execute without error and return a result dict."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame({"code": ["510300"], "scale": [1e9]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]}))
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame({"industry": ["半导体"], "pct": [20.0]}))

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))  # Monday

    result = collector_weekly.run_weekly()

    assert isinstance(result, dict), "run_weekly() should return a dict"
    assert "etf_scale" in result, "Result should contain etf_scale"
    assert "status" in result["etf_scale"], "Each task should have a status field"


def test_run_weekly_calls_get_etf_scale(monkeypatch, tmp_path):
    """run_weekly should call get_etf_scale."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    scale_calls = []
    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    def track_scale():
        scale_calls.append(1)
        return pd.DataFrame({"code": ["510300"], "scale": [1e9]})
    monkeypatch.setattr(ak_module, "get_etf_scale", track_scale)
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame())

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    collector_weekly.run_weekly()

    assert len(scale_calls) == 1, f"Expected 1 get_etf_scale call, got {len(scale_calls)}"


def test_run_weekly_calls_north_flow_weekly(monkeypatch, tmp_path):
    """run_weekly should call get_north_flow with ('沪深股通', 1) for weekly data."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    north_args = []
    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame())
    def track_north(sym, months):
        north_args.append((sym, months))
        return pd.DataFrame()
    monkeypatch.setattr(ak_module, "get_north_flow", track_north)
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame())

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    collector_weekly.run_weekly()

    assert len(north_args) == 1, f"Expected 1 north_flow call, got {len(north_args)}"
    assert north_args[0] == ("沪深股通", 1), f"Expected ('沪深股通', 1), got {north_args[0]}"


def test_run_weekly_calls_get_industry_alloc(monkeypatch, tmp_path):
    """run_weekly should call get_industry_alloc for the current year."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    alloc_calls = []
    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())
    def track_alloc(year):
        alloc_calls.append(year)
        return pd.DataFrame()
    monkeypatch.setattr(ak_module, "get_industry_alloc", track_alloc)

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    collector_weekly.run_weekly()

    assert len(alloc_calls) == 1, f"Expected 1 industry_alloc call, got {len(alloc_calls)}"
    assert alloc_calls[0] == 2026, f"Expected year 2026, got {alloc_calls[0]}"


def test_run_weekly_saves_weekly_files(monkeypatch, tmp_path):
    """run_weekly should create files in weekly/ directory."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame({"code": ["510300"], "scale": [1e9]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]}))
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame({"industry": ["半导体"], "pct": [20.0]}))

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    collector_weekly.run_weekly()

    weekly_dir = tmp_path / "weekly"
    assert weekly_dir.exists(), f"Expected weekly/ directory to exist"
    files = list(weekly_dir.iterdir())
    assert len(files) >= 3, f"Expected at least 3 weekly files, got {len(files)}: {[f.name for f in files]}"


def test_cli_runs_weekly(monkeypatch, tmp_path):
    """CLI should invoke run_weekly."""
    import importlib
    import json
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame())

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    weekly_called = False
    def mock_weekly():
        nonlocal weekly_called
        weekly_called = True
        return {}
    monkeypatch.setattr(collector_weekly, "run_weekly", mock_weekly)

    # ADR-004: --config is required. Write a minimal valid config.
    cfg = tmp_path / "etf_config.json"
    cfg.write_text(json.dumps({
        "etf_watch_list": [{"code": "510300", "name": "x", "index": "y"}],
    }))
    import sys
    monkeypatch.setattr(sys, "argv", ["collector_weekly.py", "--config", str(cfg)])
    config._initialized = False
    collector_weekly.main()

    assert weekly_called, "main() should call run_weekly()"


def test_output_structure(monkeypatch, tmp_path):
    """run_weekly should return a dict with etf_scale, north_flow_week, industry_alloc keys."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)
    monkeypatch.setattr(ak_module, "get_etf_scale", lambda: pd.DataFrame({"code": ["510300"]}))
    monkeypatch.setattr(ak_module, "get_north_flow", lambda sym, months: pd.DataFrame())
    monkeypatch.setattr(ak_module, "get_industry_alloc", lambda year: pd.DataFrame())

    from src import collector_weekly
    importlib.reload(collector_weekly)
    monkeypatch.setattr(collector_weekly, "today", lambda: datetime.date(2026, 5, 18))

    result = collector_weekly.run_weekly()

    for task in ["etf_scale", "north_flow_week", "industry_alloc"]:
        assert task in result, f"Missing task: {task}"
        assert "status" in result[task], f"Task {task} should have a status field"