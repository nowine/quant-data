"""Tests for weekly/monthly/quarterly --config CLI flag → config.init_config() bridge.

Mirrors test_collector_daily_config.py. Per ADR-004, all four collectors must
load etf_config.json via init_config() at process start so 皮皮 can adjust
the 4 ETF list constants (ETF_WATCH_LIST / USER_HOLDINGS / INDEX_WATCH_LIST /
SECTOR_MAPPING) without touching code.

Public seam: the --config CLI option on each collector's main().

Each test reloads its target collector so a stale _initialized flag from
prior tests doesn't trip the double-init RuntimeError (see config.py).
"""

from __future__ import annotations

import datetime
import importlib
import json
import sys
from pathlib import Path

import pytest

import src.collector_daily as cd  # for _initialized reset helper


@pytest.fixture(autouse=True)
def _restore_config_defaults():
    """Save+restore the 4 module-level constants so test order doesn't pollute
    downstream tests (e.g. test_config.py asserts ETF_WATCH_LIST >= 20 entries).

    init_config() mutates the config module in place; without this fixture,
    running test_collector_config_cli.py before test_config.py makes the
    defaults-only tests see the 1-entry stub JSON.
    """
    from src import config as config_mod
    saved = (
        list(config_mod.ETF_WATCH_LIST),
        list(config_mod.USER_HOLDINGS),
        list(config_mod.INDEX_WATCH_LIST),
        dict(config_mod.SECTOR_MAPPING),
    )
    yield
    (
        config_mod.ETF_WATCH_LIST,
        config_mod.USER_HOLDINGS,
        config_mod.INDEX_WATCH_LIST,
        config_mod.SECTOR_MAPPING,
    ) = saved
    config_mod._initialized = False


def _write_minimal(path: Path) -> Path:
    """Write a JSON config that satisfies the schema."""
    path.write_text(json.dumps({
        "etf_watch_list": [
            {"code": "510300", "name": "沪深300ETF", "index": "000300.SH"}
        ],
        "user_holdings": [
            {"code": "159530", "name": "机器人ETF", "sector": "robot"}
        ],
        "index_watch_list": ["000300.SH"],
        "sector_mapping": {
            "robot": ["159530", "562500"]
        },
    }))
    return path


def _reset_init_flag() -> None:
    """Allow init_config() to be called again after importlib.reload."""
    from src import config as config_mod
    config_mod._initialized = False


def _reload_collector(name: str):
    """Reload a collector module so its `from src import config` re-binds."""
    return importlib.reload(importlib.import_module(name))


# ── Weekly ────────────────────────────────────────────────────────────────────

class TestWeeklyConfigFlag:
    def test_missing_config_flag_prints_help(self, capsys, monkeypatch):
        cw = _reload_collector("src.collector_weekly")
        _reset_init_flag()
        monkeypatch.setattr(sys, "argv", ["collector_weekly.py"])
        with pytest.raises(SystemExit):
            cw.main()
        captured = capsys.readouterr()
        assert "required" in captured.err.lower() or "config" in captured.err.lower()

    def test_valid_config_loads_lists(self, tmp_path, monkeypatch):
        cfg = _write_minimal(tmp_path / "cfg.json")

        # Stub run_weekly so main() exits fast (we only test init side-effect).
        monkeypatch.setattr(sys, "argv", [
            "collector_weekly.py", "--config", str(cfg)
        ])
        cw = _reload_collector("src.collector_weekly")
        _reset_init_flag()
        monkeypatch.setattr(cw, "today", lambda: datetime.date(2026, 5, 18))  # Monday
        monkeypatch.setattr(cw, "run_weekly", lambda: {"errors": []})

        cw.main()

        from src import config as config_mod
        assert config_mod.is_initialized()
        assert len(config_mod.USER_HOLDINGS) == 1
        assert config_mod.USER_HOLDINGS[0]["code"] == "159530"

    def test_bad_config_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json")
        monkeypatch.setattr(sys, "argv", [
            "collector_weekly.py", "--config", str(bad)
        ])
        _reload_collector("src.collector_weekly")
        _reset_init_flag()

        with pytest.raises(SystemExit) as exc_info:
            _reload_collector("src.collector_weekly").main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "json" in captured.err.lower() or "configloaderror" in captured.err.lower()


# ── Monthly ───────────────────────────────────────────────────────────────────

class TestMonthlyConfigFlag:
    def test_missing_config_flag_prints_help(self, capsys, monkeypatch):
        cm = _reload_collector("src.collector_monthly")
        _reset_init_flag()
        monkeypatch.setattr(sys, "argv", ["collector_monthly.py"])
        with pytest.raises(SystemExit):
            cm.main()
        captured = capsys.readouterr()
        assert "required" in captured.err.lower() or "config" in captured.err.lower()

    def test_valid_config_loads_lists(self, tmp_path, monkeypatch):
        cfg = _write_minimal(tmp_path / "cfg.json")
        monkeypatch.setattr(sys, "argv", [
            "collector_monthly.py", "--config", str(cfg)
        ])
        cm = _reload_collector("src.collector_monthly")
        _reset_init_flag()
        monkeypatch.setattr(cm, "run_monthly", lambda: {"errors": []})

        cm.main()

        from src import config as config_mod
        assert config_mod.is_initialized()
        assert len(config_mod.ETF_WATCH_LIST) == 1

    def test_bad_config_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "nope.json"
        monkeypatch.setattr(sys, "argv", [
            "collector_monthly.py", "--config", str(bad)
        ])
        _reload_collector("src.collector_monthly")
        _reset_init_flag()

        with pytest.raises(SystemExit) as exc_info:
            _reload_collector("src.collector_monthly").main()
        assert exc_info.value.code != 0


# ── Quarterly ─────────────────────────────────────────────────────────────────

class TestQuarterlyConfigFlag:
    def test_missing_config_flag_prints_help(self, capsys, monkeypatch):
        cq = _reload_collector("src.collector_quarterly")
        _reset_init_flag()
        monkeypatch.setattr(sys, "argv", ["collector_quarterly.py"])
        with pytest.raises(SystemExit):
            cq.main()
        captured = capsys.readouterr()
        assert "required" in captured.err.lower() or "config" in captured.err.lower()

    def test_valid_config_loads_lists(self, tmp_path, monkeypatch):
        cfg = _write_minimal(tmp_path / "cfg.json")
        monkeypatch.setattr(sys, "argv", [
            "collector_quarterly.py", "--config", str(cfg)
        ])
        cq = _reload_collector("src.collector_quarterly")
        _reset_init_flag()
        # Force-run-day so main() proceeds past the date guard
        monkeypatch.setattr(cq, "today", lambda: datetime.date(2026, 3, 15))
        monkeypatch.setattr(cq, "run_quarterly", lambda: {"errors": []})

        cq.main()

        from src import config as config_mod
        assert config_mod.is_initialized()
        assert len(config_mod.INDEX_WATCH_LIST) == 1
        assert "robot" in config_mod.SECTOR_MAPPING

    def test_bad_config_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "nope.json"
        monkeypatch.setattr(sys, "argv", [
            "collector_quarterly.py", "--config", str(bad)
        ])
        _reload_collector("src.collector_quarterly")
        _reset_init_flag()

        with pytest.raises(SystemExit) as exc_info:
            _reload_collector("src.collector_quarterly").main()
        assert exc_info.value.code != 0
