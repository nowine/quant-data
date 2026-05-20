"""Tests for collector_monthly.py — monthly macro data collection."""

import datetime
import pandas as pd


def test_get_macro_data_returns_dict(monkeypatch, tmp_path):
    """get_macro_data() should return a dict with macro data keys."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)

    mock_df = pd.DataFrame({"date": ["2026-01"], "value": [2.3]})
    monkeypatch.setattr(ak_module, "get_cpi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_ppi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_pmi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_gdp", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_m2", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_lpr", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: mock_df)

    from src import collector_monthly
    importlib.reload(collector_monthly)

    result = collector_monthly.get_macro_data()

    assert isinstance(result, dict), "get_macro_data() should return a dict"
    for key in ["cpi", "ppi", "pmi", "gdp", "m2", "lpr", "margin_sh"]:
        assert key in result, f"Result should contain '{key}'"


def test_run_monthly_creates_monthly_files(monkeypatch, tmp_path):
    """run_monthly() should create files in monthly/ directory."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)

    mock_df = pd.DataFrame({"date": ["2026-01"], "value": [2.3]})
    monkeypatch.setattr(ak_module, "get_cpi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_ppi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_pmi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_gdp", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_m2", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_lpr", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: mock_df)

    from src import collector_monthly
    importlib.reload(collector_monthly)
    monkeypatch.setattr(collector_monthly, "today", lambda: datetime.date(2026, 5, 1))

    collector_monthly.run_monthly()

    monthly_dir = tmp_path / "monthly"
    assert monthly_dir.exists(), "monthly/ directory should exist"
    files = list(monthly_dir.iterdir())
    assert len(files) >= 7, f"Expected at least 7 monthly files, got {len(files)}: {[f.name for f in files]}"


def test_run_monthly_returns_result_dict(monkeypatch, tmp_path):
    """run_monthly() should return a dict with status for each task."""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ak_module
    importlib.reload(ak_module)

    mock_df = pd.DataFrame({"date": ["2026-01"], "value": [2.3]})
    monkeypatch.setattr(ak_module, "get_cpi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_ppi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_pmi", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_gdp", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_m2", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_lpr", lambda: mock_df)
    monkeypatch.setattr(ak_module, "get_margin_sh", lambda: mock_df)

    from src import collector_monthly
    importlib.reload(collector_monthly)
    monkeypatch.setattr(collector_monthly, "today", lambda: datetime.date(2026, 5, 1))

    result = collector_monthly.run_monthly()

    assert isinstance(result, dict), "run_monthly() should return a dict"
    for task in ["cpi", "ppi", "pmi", "gdp", "m2", "lpr", "margin_sh"]:
        assert task in result, f"Missing task: {task}"
        assert "status" in result[task], f"Task {task} should have a status field"
