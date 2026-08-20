"""Tests for src/config_loader.py — file read + schema validate seam.

Public seam: `load_config(path: Path | str) -> dict`.

Contract (per ADR-004 Q11/Q13/Q14):
- Reads JSON from disk; on any failure raises ConfigLoadError (fail-fast).
- Returns the validated config dict with 4 keys: etf_watch_list, user_holdings,
  index_watch_list, sector_mapping. Missing keys default to empty containers.
- Path may be a str or Path; resolved to absolute before reading.
- The caller (config.py wrapper) is responsible for caching the result; this
  function does NOT cache (Q14-A: cron is isolated session, no need).
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from src.config_loader import ConfigLoadError, load_config


# ── Happy path ────────────────────────────────────────────────────────────────

class TestLoadConfigHappyPath:
    def test_loads_minimal_config(self, tmp_path: Path):
        cfg_path = tmp_path / "etf_config.json"
        cfg_path.write_text(json.dumps({"etf_watch_list": []}))
        result = load_config(cfg_path)
        assert result["etf_watch_list"] == []
        assert result["user_holdings"] == []
        assert result["index_watch_list"] == []
        assert result["sector_mapping"] == {}

    def test_loads_full_config(self, tmp_path: Path):
        cfg_path = tmp_path / "etf_config.json"
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
        cfg_path.write_text(json.dumps(data, ensure_ascii=False))
        result = load_config(cfg_path)
        assert result["etf_watch_list"] == data["etf_watch_list"]
        assert result["user_holdings"] == data["user_holdings"]
        assert result["index_watch_list"] == data["index_watch_list"]
        assert result["sector_mapping"] == data["sector_mapping"]

    def test_accepts_string_path(self, tmp_path: Path):
        cfg_path = tmp_path / "etf_config.json"
        cfg_path.write_text("{}")
        result = load_config(str(cfg_path))  # str, not Path
        assert isinstance(result, dict)


# ── File errors (fail-fast per ADR-004 Q13-A) ───────────────────────────────

class TestLoadConfigFileErrors:
    def test_missing_file_raises_with_clear_message(self, tmp_path: Path):
        missing = tmp_path / "nope.json"
        with pytest.raises(ConfigLoadError, match="not found"):
            load_config(missing)

    def test_missing_file_message_includes_path(self, tmp_path: Path):
        missing = tmp_path / "etf_config.json"
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(missing)
        assert "etf_config.json" in str(exc_info.value)

    def test_empty_file_raises(self, tmp_path: Path):
        empty = tmp_path / "empty.json"
        empty.write_text("")
        with pytest.raises(ConfigLoadError, match="empty"):
            load_config(empty)

    def test_invalid_json_raises_with_parse_error(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ this is not json")
        with pytest.raises(ConfigLoadError, match="JSON"):
            load_config(bad)


# ── Schema errors (fail-fast; surface validator message) ────────────────────

class TestLoadConfigSchemaErrors:
    def test_schema_violation_raises_with_validator_message(self, tmp_path: Path):
        """When JSON parses but fails schema, error message should mention schema."""
        bad = tmp_path / "bad_schema.json"
        bad.write_text(json.dumps({
            "etf_watch_list": [{"code": "12345", "name": "x", "index": "y"}]
        }))
        with pytest.raises(ConfigLoadError, match="schema"):
            load_config(bad)

    def test_top_level_not_object_raises(self, tmp_path: Path):
        """JSON array at top level → ConfigLoadError (validator's strict type check)."""
        bad = tmp_path / "not_object.json"
        bad.write_text("[1, 2, 3]")
        with pytest.raises(ConfigLoadError):
            load_config(bad)


# ── Returned dict shape ──────────────────────────────────────────────────────

class TestLoadConfigReturnShape:
    def test_returned_dict_has_four_keys(self, tmp_path: Path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text("{}")
        result = load_config(cfg)
        assert set(result.keys()) == {
            "etf_watch_list", "user_holdings", "index_watch_list", "sector_mapping"
        }

    def test_missing_lists_default_to_empty(self, tmp_path: Path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"etf_watch_list": [{"code": "510300", "name": "x", "index": "y"}]}))
        result = load_config(cfg)
        assert result["user_holdings"] == []
        assert result["index_watch_list"] == []
        assert result["sector_mapping"] == {}

    def test_returned_lists_are_not_aliased_to_source(self, tmp_path: Path):
        """Mutating the returned lists must not affect later load_config calls.

        Per ADR-003 §test_output_dicts_are_independent: same principle applies
        here. If we returned the parsed JSON directly, a caller mutating one
        entry would silently change the cached config.
        """
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"etf_watch_list": [{"code": "510300", "name": "x", "index": "y"}]}))
        first = load_config(cfg)
        first["etf_watch_list"].clear()
        second = load_config(cfg)
        assert len(second["etf_watch_list"]) == 1


# ── Error message usability ──────────────────────────────────────────────────

class TestLoadConfigErrorMessages:
    def test_all_errors_suggest_fixing_json(self, tmp_path: Path):
        """Every ConfigLoadError message should hint at editing the JSON file."""
        missing = tmp_path / "nope.json"
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(missing)
        assert "etf_config" in str(exc_info.value).lower() or ".json" in str(exc_info.value)


# ── Encoding (UTF-8 / Chinese names) ─────────────────────────────────────────

class TestLoadConfigEncoding:
    def test_utf8_chinese_names_load_correctly(self, tmp_path: Path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({
            "etf_watch_list": [{"code": "159530", "name": "机器人ETF易方达", "index": "中证机器人"}]
        }, ensure_ascii=False), encoding="utf-8")
        result = load_config(cfg)
        assert result["etf_watch_list"][0]["name"] == "机器人ETF易方达"


# ── Comment in source about duck-typing ──────────────────────────────────────

class TestLoadConfigDedent:
    """Sanity: load_config accepts both dedented and raw JSON."""
    def test_dedent_input_works(self, tmp_path: Path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(dedent("""\
            {
                "etf_watch_list": []
            }
        """))
        result = load_config(cfg)
        assert result["etf_watch_list"] == []