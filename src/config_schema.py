"""JSON schema definition + jsonschema validator for etf_config.json.

This module owns the schema (single source of truth) and a strict-fail
validator. The schema is intentionally lenient on extra fields (ADR-004 Q12-B):
- Extra top-level keys: silently ignored (allows 皮皮 to add `_notes` etc.)
- Extra entry fields: silently ignored (allows 皮皮 to add `notes`/`added_at`)
- Missing top-level lists: OK (defaults to empty list downstream)
- Missing entry required fields: REJECTED (fail-fast per ADR-004 Q13-A)

Public seam:
    - validate_config(data: dict) -> None
        Strict-fail validator. Raises ConfigSchemaError with a structured
        message naming the exact failing path so 皮皮 can fix JSON without
        reading code.

    - ETF_CONFIG_SCHEMA: dict
        The schema itself, exposed for documentation / future UI consumption.

See ADR-004 (docs/adr-004-externalize-config.md) for full design rationale.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

import jsonschema
from jsonschema import Draft202012Validator


# Reuse the 6-digit code pattern from extra_holdings (single source of truth).
# We deliberately don't import from extra_holdings to keep config_schema
# dependency-free of any runtime modules; if extra_holdings' pattern changes,
# update both.
_CODE_PATTERN = re.compile(r"^\d{6}$")


# ── Schema ────────────────────────────────────────────────────────────────────

ETF_CONFIG_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "etf_config",
    "description": (
        "quant-data ETF monitoring configuration. All top-level keys are optional; "
        "an empty config validates. Per-entry required fields are strict."
    ),
    "type": "object",
    "additionalProperties": True,  # Q12-B: lenient on extra top-level keys
    "required": [],
    "properties": {
        "etf_watch_list": {
            "type": "array",
            "description": (
                "ETFs in the core watch list (轮动分析 framework). Each entry "
                "needs code (6-digit string), name, and index (the underlying "
                "index name, e.g. '沪深300')."
            ),
            "items": {
                "type": "object",
                "additionalProperties": True,  # Q12-B: lenient on extra fields
                "required": ["code", "name", "index"],
                "properties": {
                    "code": {
                        "type": "string",
                        "pattern": r"^\d{6}$",
                        "description": "6-digit ETF code (e.g. '510300').",
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "ETF display name.",
                    },
                    "index": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "Underlying index name. Must match an entry in "
                            "index_watch_list for valuation tracking."
                        ),
                    },
                },
            },
        },
        "user_holdings": {
            "type": "array",
            "description": (
                "User's actual ETF holdings (早报 premium / sector aggregation). "
                "Each entry needs code, name, and sector (industry category)."
            ),
            "items": {
                "type": "object",
                "additionalProperties": True,  # Q12-B
                "required": ["code", "name", "sector"],
                "properties": {
                    "code": {"type": "string", "pattern": r"^\d{6}$"},
                    "name": {"type": "string", "minLength": 1},
                    "sector": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Industry sector (e.g. '机器人', '半导体/芯片').",
                    },
                },
            },
        },
        "index_watch_list": {
            "type": "array",
            "description": (
                "Index names for valuation tracking (估值分位). "
                "Each entry must match the 'index' field of an etf_watch_list item."
            ),
            "items": {
                "type": "string",
                "minLength": 1,
            },
        },
        "sector_mapping": {
            "type": "object",
            "description": (
                "Sector → ETF code mapping. Used by sector_aggregator to roll up "
                "watch-list ETFs into industry buckets. Keys are sector names "
                "(matching user_holdings.sector), values are 6-digit ETF code arrays."
            ),
            "additionalProperties": True,  # Q12-B: lenient on extra sectors
            "patternProperties": {
                "^.+$": {  # any non-empty sector name
                    "type": "array",
                    "items": {"type": "string", "pattern": r"^\d{6}$"},
                },
            },
        },
    },
}


# ── Validator ─────────────────────────────────────────────────────────────────


class ConfigSchemaError(ValueError):
    """Raised when etf_config.json fails schema validation.

    The message names the exact failing path (e.g. 'etf_watch_list[3].code')
    so 皮皮 can fix the JSON file directly without reading code.
    """


def _format_path(path: Iterable[Any]) -> str:
    """Format a jsonschema path as a JSON-pointer-like string."""
    parts = []
    for p in path:
        if isinstance(p, int):
            parts.append(f"[{p}]")
        else:
            parts.append(f".{p}" if parts else str(p))
    return "".join(parts) or "<root>"


def _aggregate_errors(errors: list[jsonschema.ValidationError]) -> str:
    """Aggregate multiple ValidationErrors into a single readable message.

    jsonschema yields one error per violation; we collect all of them and
    present a bulleted list so 皮皮 can fix everything in one pass instead of
    playing whack-a-mole.
    """
    lines = ["etf_config.json schema validation failed:"]
    seen: set[tuple] = set()
    for err in errors:
        # Skip sub-errors of 'anyOf'/'oneOf' to avoid noise.
        if err.validator in ("anyOf", "oneOf"):
            continue
        # Deduplicate by (path, message).
        key = (tuple(err.absolute_path), err.message)
        if key in seen:
            continue
        seen.add(key)
        path_str = _format_path(err.absolute_path)
        lines.append(f"  - {path_str}: {err.message}")
    return "\n".join(lines)


def validate_config(data: dict) -> None:
    """Validate parsed etf_config.json dict against ETF_CONFIG_SCHEMA.

    Args:
        data: Parsed JSON dict (caller responsible for JSON parsing).

    Raises:
        ConfigSchemaError: If the data fails schema validation. The message
            lists ALL violations so 皮皮 can fix everything in one pass.
    """
    if not isinstance(data, dict):
        raise ConfigSchemaError(
            f"etf_config.json must be a JSON object at top level; got {type(data).__name__}"
        )

    validator = Draft202012Validator(ETF_CONFIG_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))

    if errors:
        # Surface only leaf-level errors (skip nested anyOf/oneOf noise).
        leaf_errors = [e for e in errors if e.validator not in ("anyOf", "oneOf")]
        if not leaf_errors:
            leaf_errors = errors  # fallback if all were filtered
        raise ConfigSchemaError(_aggregate_errors(leaf_errors))