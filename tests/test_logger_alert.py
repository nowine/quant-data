"""Tests for logger.alert()."""

import importlib
from datetime import date

import pytest


def test_alert_writes_csv(tmp_path, monkeypatch):
    """alert() creates alert_YYYYMMDD.csv with correct fields."""
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    logger_module.run_id = "test_run_456"
    logger_module.alert("error", "API timeout")

    today = date.today().strftime("%Y%m%d")
    alert_file = tmp_path / "logs" / f"alert_{today}.csv"
    assert alert_file.exists(), f"Alert file not created: {alert_file}"
    content = alert_file.read_text()
    assert "error" in content
    assert "API timeout" in content
    assert "test_run_456" in content


def test_alert_warn_level(tmp_path, monkeypatch):
    """alert() correctly records warn level."""
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    logger_module.alert("warn", "Slow response 45s")

    today = date.today().strftime("%Y%m%d")
    alert_file = tmp_path / "logs" / f"alert_{today}.csv"
    content = alert_file.read_text()
    assert "warn" in content
    assert "Slow response 45s" in content


def test_alert_csv_header(tmp_path, monkeypatch):
    """alert() writes CSV header on first row."""
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    logger_module.alert("warn", "first alert")

    today = date.today().strftime("%Y%m%d")
    alert_file = tmp_path / "logs" / f"alert_{today}.csv"
    content = alert_file.read_text()
    lines = content.strip().split("\n")
    assert len(lines) >= 2  # header + at least one data row
    # Header should contain timestamp,level,message,run_id
    header = lines[0]
    assert "timestamp" in header
    assert "level" in header
    assert "message" in header
    assert "run_id" in header


def test_alert_append_mode(tmp_path, monkeypatch):
    """Multiple alert() calls append to the same file."""
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    logger_module.alert("warn", "first")
    logger_module.alert("error", "second")
    logger_module.alert("warn", "third")

    today = date.today().strftime("%Y%m%d")
    alert_file = tmp_path / "logs" / f"alert_{today}.csv"
    content = alert_file.read_text()
    lines = content.strip().split("\n")
    assert len(lines) == 4  # header + 3 data rows
    assert "first" in content
    assert "second" in content
    assert "third" in content