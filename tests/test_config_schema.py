"""Tests for src/config_schema.py — JSON schema + jsonschema validator seam.

Public seam: `validate_config(data: dict) -> None`.

Contract (per ADR-004 / grill-me 2026-08-20 Q11/Q12/Q13):
- Input: parsed JSON dict from etf_config.json.
- Output: None on success; raises ConfigSchemaError on any validation failure.
- Strict on REQUIRED fields (code/name/index/sector); lenient on EXTRA fields
  (ignored — ADR-004 §校验策略 Q12-B). Rationale: keeps schema maintenance low
  while still catching missing essentials.
- Error messages must name the failing path so 皮皮 can fix the JSON file
  directly without reading code (per ADR-004 §文档分层, ADR-003 教训).

Schema coverage (matches config.py current 4 list constants):
- etf_watch_list: list of {code: str(6digits), name: str, index: str}
- user_holdings: list of {code: str(6digits), name: str, sector: str}
- index_watch_list: list of str (index names)
- sector_mapping: dict[str, list[str(6digits)]]
- All four keys OPTIONAL at top level — a partial config still validates
  (empty list defaults). This matters for 皮皮 who may stage edits.
"""

from __future__ import annotations

import pytest

from src.config_schema import (
    ETF_CONFIG_SCHEMA,
    ConfigSchemaError,
    validate_config,
)


# ── Happy path ────────────────────────────────────────────────────────────────

class TestValidateConfigHappyPath:
    def test_full_config_passes(self):
        """All 4 lists present with valid entries → validate_config returns None."""
        data = {
            "etf_watch_list": [{"code": "159530", "name": "机器人ETF易方达", "index": "中证机器人"}],
            "user_holdings": [{"code": "159530", "name": "机器人ETF易方达", "sector": "机器人"}],
            "index_watch_list": ["沪深300", "中证500"],
            "sector_mapping": {"机器人": ["159530"], "宽基": ["510300", "510500"]},
        }
        # No exception → success
        assert validate_config(data) is None

    def test_empty_config_passes(self):
        """All 4 keys absent → empty config is valid (皮皮 stages edits)."""
        assert validate_config({}) is None

    def test_partial_config_passes(self):
        """Only one list present → valid; missing lists default to empty."""
        data = {"etf_watch_list": [{"code": "510300", "name": "沪深300ETF", "index": "沪深300"}]}
        assert validate_config(data) is None

    def test_extra_top_level_keys_ignored(self):
        """Per ADR-004 Q12-B: extra fields are silently ignored, not rejected."""
        data = {
            "etf_watch_list": [],
            "unknown_future_field": {"anything": "goes"},
            "_internal_notes": "皮皮 scratch space",
        }
        assert validate_config(data) is None

    def test_extra_entry_fields_ignored(self):
        """Per ADR-004 Q12-B: entries may carry extra fields (notes, color, etc.)."""
        data = {
            "etf_watch_list": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "index": "沪深300",
                    "notes": "皮皮 added: keep an eye",
                    "added_at": "2026-08-20",
                }
            ]
        }
        assert validate_config(data) is None


# ── Required-field violations (fail-fast per ADR-004 Q13-A) ─────────────────

class TestValidateConfigMissingFields:
    def test_missing_etf_code_raises(self):
        data = {"etf_watch_list": [{"name": "无code条目", "index": "沪深300"}]}
        with pytest.raises(ConfigSchemaError, match="etf_watch_list"):
            validate_config(data)

    def test_etf_code_not_six_digits_raises(self):
        data = {"etf_watch_list": [{"code": "12345", "name": "x", "index": "y"}]}
        with pytest.raises(ConfigSchemaError, match="6"):
            validate_config(data)

    def test_etf_code_not_string_raises(self):
        data = {"etf_watch_list": [{"code": 159530, "name": "x", "index": "y"}]}
        with pytest.raises(ConfigSchemaError, match="etf_watch_list"):
            validate_config(data)

    def test_missing_etf_name_raises(self):
        data = {"etf_watch_list": [{"code": "510300", "index": "沪深300"}]}
        with pytest.raises(ConfigSchemaError, match="name"):
            validate_config(data)

    def test_missing_etf_index_raises(self):
        data = {"etf_watch_list": [{"code": "510300", "name": "沪深300ETF"}]}
        with pytest.raises(ConfigSchemaError, match="index"):
            validate_config(data)

    def test_user_holding_missing_sector_raises(self):
        data = {"user_holdings": [{"code": "159530", "name": "机器人ETF易方达"}]}
        with pytest.raises(ConfigSchemaError, match="sector"):
            validate_config(data)

    def test_user_holding_missing_name_raises(self):
        data = {"user_holdings": [{"code": "159530", "sector": "机器人"}]}
        with pytest.raises(ConfigSchemaError, match="name"):
            validate_config(data)


# ── Type violations ──────────────────────────────────────────────────────────

class TestValidateConfigWrongTypes:
    def test_etf_watch_list_must_be_list(self):
        with pytest.raises(ConfigSchemaError, match="etf_watch_list"):
            validate_config({"etf_watch_list": {"code": "510300"}})

    def test_index_watch_list_must_be_list(self):
        with pytest.raises(ConfigSchemaError, match="index_watch_list"):
            validate_config({"index_watch_list": "沪深300"})

    def test_sector_mapping_must_be_object(self):
        with pytest.raises(ConfigSchemaError, match="sector_mapping"):
            validate_config({"sector_mapping": ["should", "be", "object"]})

    def test_sector_mapping_value_must_be_list(self):
        with pytest.raises(ConfigSchemaError, match="sector_mapping"):
            validate_config({"sector_mapping": {"机器人": "159530"}})

    def test_sector_mapping_value_must_be_six_digit_codes(self):
        with pytest.raises(ConfigSchemaError, match="sector_mapping"):
            validate_config({"sector_mapping": {"机器人": ["15953"]}})


# ── Error message usability ──────────────────────────────────────────────────

class TestValidateConfigErrorMessages:
    def test_error_includes_path_to_offending_field(self):
        """Error must name the exact field so 皮皮 can fix JSON without reading code."""
        data = {"user_holdings": [{"code": "159530", "name": "机器人ETF易方达", "sector": ""}]}
        with pytest.raises(ConfigSchemaError) as exc_info:
            validate_config(data)
        # Message should mention 'sector' AND 'user_holdings' for navigation
        msg = str(exc_info.value)
        assert "sector" in msg
        assert "user_holdings" in msg

    def test_multiple_errors_aggregated(self):
        """If multiple entries fail, all errors surface (not just the first)."""
        data = {
            "etf_watch_list": [
                {"code": "12345", "name": "x", "index": "y"},  # bad code (5 digits)
                {"code": "510300", "name": "ok", "index": "z"},  # ok
                {"code": "999999", "index": "missing name"},  # missing name field
            ]
        }
        with pytest.raises(ConfigSchemaError) as exc_info:
            validate_config(data)
        msg = str(exc_info.value)
        # Both bad entries should be flagged by their path; ok entry should not appear.
        # Don't assert on specific error message text (jsonschema wording is brittle);
        # only verify path navigation works for 皮皮.
        assert "[0]" in msg  # bad code entry
        assert "[2]" in msg  # missing-name entry
        assert "[1]" not in msg  # ok entry should NOT be in error


# ── Schema export ────────────────────────────────────────────────────────────

class TestSchemaExport:
    def test_schema_is_dict(self):
        """Schema is exposed as a public constant for documentation/UI use."""
        assert isinstance(ETF_CONFIG_SCHEMA, dict)
        assert "type" in ETF_CONFIG_SCHEMA
        assert ETF_CONFIG_SCHEMA["type"] == "object"

    def test_schema_documents_required_keys(self):
        """Schema top-level should mark no required keys (all optional)."""
        # Per ADR-004: all 4 lists are optional so 皮皮 can stage edits.
        assert ETF_CONFIG_SCHEMA.get("required", []) == []