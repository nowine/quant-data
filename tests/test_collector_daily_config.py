"""Tests for collector_daily --config CLI flag → config.init_config() bridge.

Per ADR-004 Q19-B: --config PATH is a required long option.
- Missing --config → argparse error (cron prompt must supply it).
- --config pointing at a valid file → init_config(path) succeeds, then
  collector proceeds.
- --config pointing at a bad file → ConfigLoadError surfaces as non-zero
  exit (fail-fast per Q13-A / Q20-B). argparse-level error handling here
  is just to capture and re-raise cleanly.

Public seam: the --config CLI option on collector_daily.main().
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import src.collector_daily as cd
from src.config_loader import ConfigLoadError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_minimal(path: Path) -> Path:
    path.write_text(json.dumps({
        "etf_watch_list": [{"code": "510300", "name": "x", "index": "y"}],
    }))
    return path


def _mock_all_collect(monkeypatch):
    """Stub out all collector side-effects so main() can return cleanly."""
    monkeypatch.setattr(cd, "_collect_csv", lambda *a, **kw: {"status": "success"})
    monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})
    monkeypatch.setattr(cd, "is_trading_day", lambda: True)
    # Also stub the akshare_fund_client functions reached by helpers
    from src import akshare_fund_client as af
    monkeypatch.setattr(af, "get_gold_info", lambda s: {"datas": []})
    monkeypatch.setattr(af, "get_index_info", lambda i, s: {"datas": []})
    monkeypatch.setattr(af, "get_nav_history",
                        lambda c, r: {"data": {"nav_history": {"items": []}}})
    from src import akshare_client as ac
    monkeypatch.setattr(ac, "get_etf_snapshot", lambda: __import__("pandas").DataFrame())
    monkeypatch.setattr(ac, "get_margin_sh", lambda: __import__("pandas").DataFrame())
    monkeypatch.setattr(ac, "get_north_flow", lambda s, m: __import__("pandas").DataFrame())
    monkeypatch.setattr(ac, "get_us_stock_index", lambda: __import__("pandas").DataFrame())
    monkeypatch.setattr(ac, "get_etf_history",
                        lambda c: __import__("pandas").DataFrame())


# ── Required flag ─────────────────────────────────────────────────────────────

class TestConfigFlagRequired:
    def test_missing_config_flag_prints_help(self, capsys, monkeypatch):
        """No --config → SystemExit (argparse error)."""
        monkeypatch.setattr(sys, "argv", ["collector_daily.py"])
        with pytest.raises(SystemExit):
            cd.main()
        captured = capsys.readouterr()
        # argparse prints 'required' in error
        assert "required" in captured.err.lower() or "config" in captured.err.lower()

    def test_help_lists_config_flag(self, monkeypatch, capsys):
        """--help output mentions --config."""
        monkeypatch.setattr(sys, "argv", ["collector_daily.py", "--help"])
        with pytest.raises(SystemExit):
            cd.main()
        captured = capsys.readouterr()
        assert "--config" in captured.out


# ── Successful --config ──────────────────────────────────────────────────────

class TestConfigFlagSuccess:
    def test_valid_config_runs_close_mode(self, tmp_path, monkeypatch):
        cfg = _write_minimal(tmp_path / "cfg.json")
        _mock_all_collect(monkeypatch)

        # Force-reload collector_daily so it doesn't carry stale config state
        # from earlier tests. (Same pattern as test_collector_errors._reload.)
        import importlib
        importlib.reload(cd)

        from src import config as config_mod
        config_mod._initialized = False  # allow init again after reload

        monkeypatch.setattr(sys, "argv", [
            "collector_daily.py", "--mode", "close", "--config", str(cfg)
        ])
        cd.main()  # should not raise

        # Verify init happened: config_mod.ETF_WATCH_LIST now has 1 entry.
        assert len(config_mod.ETF_WATCH_LIST) == 1

    def test_valid_config_runs_morning_mode(self, tmp_path, monkeypatch):
        cfg = _write_minimal(tmp_path / "cfg.json")
        _mock_all_collect(monkeypatch)

        import importlib
        importlib.reload(cd)
        from src import config as config_mod
        config_mod._initialized = False

        monkeypatch.setattr(sys, "argv", [
            "collector_daily.py", "--mode", "morning", "--config", str(cfg)
        ])
        cd.main()

        assert len(config_mod.ETF_WATCH_LIST) == 1


# ── Failing --config ─────────────────────────────────────────────────────────

class TestConfigFlagFailure:
    def test_missing_config_file_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        """--config with a non-existent file → SystemExit(1) + clear error."""
        import importlib
        importlib.reload(cd)
        from src import config as config_mod
        config_mod._initialized = False

        monkeypatch.setattr(sys, "argv", [
            "collector_daily.py", "--config", str(tmp_path / "nope.json")
        ])
        with pytest.raises(SystemExit) as exc_info:
            cd.main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "configloaderror" in captured.err.lower()

    def test_bad_json_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json")

        import importlib
        importlib.reload(cd)
        from src import config as config_mod
        config_mod._initialized = False

        monkeypatch.setattr(sys, "argv", [
            "collector_daily.py", "--config", str(bad)
        ])
        with pytest.raises(SystemExit) as exc_info:
            cd.main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "json" in captured.err.lower()


# ── CLI ordering ─────────────────────────────────────────────────────────────

class TestConfigFlagWithExtra:
    def test_config_plus_extra_holdings(self, tmp_path, monkeypatch):
        """--config and --extra-holdings coexist (ADR-004 doesn't break ADR-003)."""
        cfg = _write_minimal(tmp_path / "cfg.json")
        _mock_all_collect(monkeypatch)

        import importlib
        importlib.reload(cd)
        from src import config as config_mod
        config_mod._initialized = False

        monkeypatch.setattr(sys, "argv", [
            "collector_daily.py", "--mode", "morning",
            "--config", str(cfg),
            "--extra-holdings", '[{"code": "512480"}]',
        ])
        cd.main()  # should not raise

        # Extra-holdings deduplicates against loaded config; both paths run.
        assert config_mod.is_initialized() is True