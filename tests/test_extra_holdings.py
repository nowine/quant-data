"""Tests for src/extra_holdings.py — CLI-side parser for ad-hoc ETF additions.

Public seam: `parse_extra_holdings_arg(raw: str) -> list[dict]`.

Contract (per Q11 in grill-me session 2026-08-20):
- Input: JSON array string of {"code": str(6 digits), "name"?: str, "sector"?: str}.
- name and sector are optional; missing fields stay absent from the output dict.
- Empty / whitespace input → [].
- Malformed JSON or wrong shape → raise ValueError with a clear message
  (the CLI caller can wrap that into a friendly error, but the function
  itself is strict — no silent degradation at this seam).
- Codes are validated as 6-digit strings; non-matching entries raise.
- This is a pure function: no I/O, no akshare calls, no side effects.

These tests verify the parser seam only. The akshare-backed enrichment seam
(`build_extra_holdings_set`) lives in a separate module and is covered by
test_extra_holdings_enrich.py.
"""

from __future__ import annotations

import pytest

from src.extra_holdings import parse_extra_holdings_arg


class TestParseExtraHoldingsHappyPath:
    def test_single_entry_minimal(self):
        result = parse_extra_holdings_arg('[{"code": "159530"}]')
        assert result == [{"code": "159530"}]

    def test_single_entry_with_name(self):
        result = parse_extra_holdings_arg(
            '[{"code": "159530", "name": "机器人ETF易方达"}]'
        )
        assert result == [{"code": "159530", "name": "机器人ETF易方达"}]

    def test_multiple_entries_mixed_fields(self):
        raw = (
            '['
            '{"code": "159530", "name": "机器人ETF易方达", "sector": "机器人"}, '
            '{"code": "512480"}, '
            '{"code": "512690", "name": "白酒ETF鹏华"}'
            ']'
        )
        result = parse_extra_holdings_arg(raw)
        assert result == [
            {"code": "159530", "name": "机器人ETF易方达", "sector": "机器人"},
            {"code": "512480"},
            {"code": "512690", "name": "白酒ETF鹏华"},
        ]


class TestParseExtraHoldingsEmpty:
    def test_empty_string_returns_empty_list(self):
        assert parse_extra_holdings_arg("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert parse_extra_holdings_arg("   \n\t  ") == []


class TestParseExtraHoldingsMalformed:
    def test_not_json_raises_value_error(self):
        with pytest.raises(ValueError, match="extra-holdings"):
            parse_extra_holdings_arg("159530,512480")

    def test_json_but_not_array_raises(self):
        with pytest.raises(ValueError, match="extra-holdings"):
            parse_extra_holdings_arg('{"code": "159530"}')

    def test_missing_code_field_raises(self):
        with pytest.raises(ValueError, match="code"):
            parse_extra_holdings_arg('[{"name": "foo"}]')

    def test_code_not_six_digits_raises(self):
        with pytest.raises(ValueError, match="6"):
            parse_extra_holdings_arg('[{"code": "15953"}]')

    def test_code_with_letters_raises(self):
        with pytest.raises(ValueError, match="6"):
            parse_extra_holdings_arg('[{"code": "159530A"}]')


class TestParseExtraHoldingsStability:
    def test_output_dicts_are_independent(self):
        """Mutating the returned dict must not affect future parses."""
        first = parse_extra_holdings_arg('[{"code": "159530"}]')
        first[0]["code"] = "MUTATED"
        second = parse_extra_holdings_arg('[{"code": "159530"}]')
        assert second == [{"code": "159530"}]