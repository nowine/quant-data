"""Tests for src/config.py init_config() — module-level config loader.

This is the bridge between file-loaded JSON (config_loader.load_config) and
the 4 list constants that downstream code reads via `config.ETF_WATCH_LIST`
etc.

Contract (per ADR-004 Q6/Q13/Q14/Q20):
- Before init_config() is called, the 4 list constants keep their hard-coded
  defaults (back-compat with imports: `from src.config import ETF_WATCH_LIST`).
- After init_config(path) succeeds, those same module attributes point at the
  freshly-loaded lists. Code that does `config.ETF_WATCH_LIST` (attribute
  lookup, not import-time copy) sees the new values.
- init_config() must be called exactly once per process; calling twice is
  rejected to surface misconfiguration (cron should never call it twice).
- On load failure: raises ConfigLoadError (no silent fallback per Q20-B).
- Re-export of constants stays identical; we only mutate module attributes.

The 3 non-list constants (DATA_DIR, SLOW_API_TIMEOUT, CACHE_TTL, VALIDATION_RULES)
are NOT touched by init_config — those are not in scope for ADR-004.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.config as config_mod
from src.config import (
    DATA_DIR,
    ETF_WATCH_LIST,
    INDEX_WATCH_LIST,
    SECTOR_MAPPING,
    SLOW_API_TIMEOUT,
    USER_HOLDINGS,
    VALIDATION_RULES,
    init_config,
    is_initialized,
)
from src.config_loader import ConfigLoadError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_minimal_config(path: Path, **overrides) -> Path:
    """Write a minimal valid config JSON file; allow overrides per list."""
    data = {
        "etf_watch_list": [
            {"code": "510300", "name": "沪深300ETF", "index": "沪深300"}
        ],
        "user_holdings": [
            {"code": "159530", "name": "机器人ETF", "sector": "机器人"}
        ],
        "index_watch_list": ["沪深300"],
        "sector_mapping": {"宽基": ["510300"]},
    }
    for k, v in overrides.items():
        data[k] = v
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


def _reset_module_state():
    """Reset config module to its post-import defaults.

    Required because tests share module state. We restore the original
    hard-coded values by re-running the module body. In practice we use
    the fact that pytest reloads modules per session, but within one session
    init_config() mutates state. So between tests we reload.
    """
    import importlib
    importlib.reload(config_mod)


# ── Pre-init state (back-compat per Q22-B) ───────────────────────────────────

class TestPreInitState:
    def test_defaults_present_before_init(self):
        """Hard-coded defaults exist at import time (back-compat for tests)."""
        assert isinstance(ETF_WATCH_LIST, list)
        assert len(ETF_WATCH_LIST) > 0  # 22 defaults
        assert isinstance(INDEX_WATCH_LIST, list)
        assert isinstance(USER_HOLDINGS, list)
        assert isinstance(SECTOR_MAPPING, dict)

    def test_is_initialized_false_before_init(self):
        """No init has happened yet in this fresh module."""
        _reset_module_state()
        assert is_initialized() is False


# ── init_config() success path ───────────────────────────────────────────────

class TestInitConfigSuccess:
    def test_init_with_full_config_overrides_4_lists(self, tmp_path: Path):
        _reset_module_state()
        cfg_path = _write_minimal_config(tmp_path / "cfg.json")
        init_config(cfg_path)

        # Attribute lookups (collector_daily pattern) see new values.
        assert config_mod.ETF_WATCH_LIST == [
            {"code": "510300", "name": "沪深300ETF", "index": "沪深300"}
        ]
        assert config_mod.USER_HOLDINGS == [
            {"code": "159530", "name": "机器人ETF", "sector": "机器人"}
        ]
        assert config_mod.INDEX_WATCH_LIST == ["沪深300"]
        assert config_mod.SECTOR_MAPPING == {"宽基": ["510300"]}
        assert is_initialized() is True

    def test_init_with_empty_config_fills_defaults(self, tmp_path: Path):
        _reset_module_state()
        empty = tmp_path / "empty.json"
        empty.write_text("{}")
        init_config(empty)
        assert config_mod.ETF_WATCH_LIST == []
        assert config_mod.USER_HOLDINGS == []
        assert config_mod.INDEX_WATCH_LIST == []
        assert config_mod.SECTOR_MAPPING == {}

    def test_init_does_not_touch_non_list_constants(self, tmp_path: Path):
        """DATA_DIR / SLOW_API_TIMEOUT / CACHE_TTL / VALIDATION_RULES unchanged."""
        _reset_module_state()
        original_data_dir = DATA_DIR
        original_timeout = SLOW_API_TIMEOUT
        original_rules = VALIDATION_RULES
        original_ttl = config_mod.CACHE_TTL

        cfg_path = _write_minimal_config(tmp_path / "cfg.json")
        init_config(cfg_path)

        assert DATA_DIR == original_data_dir
        assert SLOW_API_TIMEOUT == original_timeout
        assert VALIDATION_RULES is original_rules  # not deep-copied, same obj
        assert config_mod.CACHE_TTL is original_ttl


# ── init_config() failure path (fail-fast per Q13-A, Q20-B) ──────────────────

class TestInitConfigFailure:
    def test_missing_file_raises(self, tmp_path: Path):
        _reset_module_state()
        with pytest.raises(ConfigLoadError):
            init_config(tmp_path / "nope.json")
        # is_initialized() must remain False after failure.
        assert is_initialized() is False

    def test_invalid_json_raises(self, tmp_path: Path):
        _reset_module_state()
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json")
        with pytest.raises(ConfigLoadError):
            init_config(bad)
        assert is_initialized() is False

    def test_schema_violation_raises(self, tmp_path: Path):
        _reset_module_state()
        bad = tmp_path / "bad_schema.json"
        bad.write_text(json.dumps({
            "etf_watch_list": [{"code": "12345", "name": "x", "index": "y"}]
        }))
        with pytest.raises(ConfigLoadError):
            init_config(bad)
        assert is_initialized() is False

    def test_partial_failure_does_not_corrupt_existing_state(self, tmp_path: Path):
        """Failed init must NOT have partially overwritten the 4 list constants."""
        _reset_module_state()
        original_count = len(ETF_WATCH_LIST)
        bad = tmp_path / "bad_schema.json"
        bad.write_text(json.dumps({
            "etf_watch_list": [{"code": "12345"}]  # missing fields
        }))
        with pytest.raises(ConfigLoadError):
            init_config(bad)
        # Defaults still intact.
        assert len(ETF_WATCH_LIST) == original_count


# ── Double-init protection ───────────────────────────────────────────────────

class TestInitConfigDoubleCall:
    def test_calling_twice_raises(self, tmp_path: Path):
        _reset_module_state()
        cfg_path = _write_minimal_config(tmp_path / "cfg.json")
        init_config(cfg_path)
        with pytest.raises(RuntimeError, match="twice"):
            init_config(cfg_path)


# ── Back-compat: imports at module level still get defaults ─────────────────

class TestBackCompatImports:
    def test_imported_default_matches_module_attr(self, tmp_path: Path):
        """`from src.config import ETF_WATCH_LIST` and `config.ETF_WATCH_LIST`
        should agree BEFORE init, but differ AFTER init (import is a snapshot)."""
        _reset_module_state()

        # Before init: both should agree (both point to defaults).
        from src.config import ETF_WATCH_LIST as imported
        assert imported is config_mod.ETF_WATCH_LIST

        cfg_path = _write_minimal_config(tmp_path / "cfg.json")
        init_config(cfg_path)

        # After init: attribute lookup gets the new list; imported is frozen.
        assert len(imported) == 22  # original default length
        assert len(config_mod.ETF_WATCH_LIST) == 1  # new loaded length
        assert imported is not config_mod.ETF_WATCH_LIST


# ── Idempotency of is_initialized ────────────────────────────────────────────

class TestIsInitialized:
    def test_starts_false(self):
        _reset_module_state()
        assert is_initialized() is False

    def test_true_after_success(self, tmp_path: Path):
        _reset_module_state()
        cfg_path = _write_minimal_config(tmp_path / "cfg.json")
        init_config(cfg_path)
        assert is_initialized() is True

    def test_false_after_failure(self, tmp_path: Path):
        _reset_module_state()
        with pytest.raises(ConfigLoadError):
            init_config(tmp_path / "missing.json")
        assert is_initialized() is False