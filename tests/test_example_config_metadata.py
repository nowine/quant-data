"""Tests that examples/etf_config.example.json stays皮皮-friendly.

These tests guard the _comment / _quick_start metadata so future edits don't
accidentally strip the operator-facing guidance. The metadata is purely
documentation (additionalProperties: True ignores it) but removing it leaves
皮皮 without an entry point.
"""

from __future__ import annotations

import json
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "etf_config.example.json"


def test_example_file_exists():
    assert EXAMPLE.exists(), f"Missing example: {EXAMPLE}"


def test_example_has_comment():
    """Top-level _comment explains where to copy the file."""
    data = json.loads(EXAMPLE.read_text())
    assert "_comment" in data, (
        "_comment key missing — this is the first thing 皮皮 sees "
        "when opening the example file. Don't strip it."
    )
    comment = data["_comment"]
    assert "Copy" in comment or "copy" in comment, (
        "_comment should include 'copy' instruction"
    )
    assert "etf_config.json" in comment, (
        "_comment should reference the target filename"
    )


def test_example_has_quick_start():
    """_quick_start is the 5-step bootstrap 皮皮 reads first."""
    data = json.loads(EXAMPLE.read_text())
    assert "_quick_start" in data, (
        "_quick_start missing — 皮皮 won't know how to bootstrap. "
        "See docs/CONFIG.md for the 5-step guide that should be inlined here."
    )
    qs = data["_quick_start"]
    # Must contain the canonical 5 steps
    expected_keys = ["1_copy", "2_verify_load", "3_user_holds_vs_watch", "4_required_fields", "5_help"]
    for k in expected_keys:
        assert k in qs, f"_quick_start missing key: {k}"
        assert isinstance(qs[k], str) and qs[k], f"_quick_start[{k}] must be non-empty string"


def test_example_validates_against_schema():
    """The example must pass validate_config (ignoring _comment / _quick_start)."""
    import sys
    sys.path.insert(0, str(EXAMPLE.parent.parent))
    from src.config_schema import validate_config
    data = json.loads(EXAMPLE.read_text())
    # Strip metadata so validator sees only the 4 schema fields
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    validate_config(payload)  # raises ConfigValidationError on failure


def test_example_contains_core_user_holdings():
    """The 3 user-holdings entries must be present (consumed by all 4 collectors)."""
    data = json.loads(EXAMPLE.read_text())
    holdings = {h["code"] for h in data["user_holdings"]}
    # 159530 (机器人) and 159934 (黄金) are non-negotiable per MEMORY #20-08
    assert "159530" in holdings, "Example must include 159530 (机器人ETF易方达)"
    assert "159934" in holdings, "Example must include 159934 (黄金ETF易方达)"
    assert len(holdings) >= 3, f"Example should have ≥3 holdings, got {holdings}"
