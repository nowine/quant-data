"""Ad-hoc extra holdings — supports one-shot CLI additions for ETF monitoring.

Background (see ADR-003, 2026-08-20):
    The collector only iterates `config.ETF_WATCH_LIST` and `config.USER_HOLDINGS`,
    both static. To answer ad-hoc prompts like "also watch 512480", an operator
    can pass `--extra-holdings '[...]'` on the CLI. This module owns the
    parsing + enrichment seams; the collector_daily CLI wires them in.

Public seams:
    - parse_extra_holdings_arg(raw: str) -> list[dict]
        Pure function. CLI string → list of {code, name?, sector?} dicts.
        Strict on shape (raises ValueError); does no I/O.

    - build_extra_holdings_set(codes: list[str]) -> pd.DataFrame
        Enriches codes via akshare (search_funds / get_fund_info) to fill
        name/sector. See test_extra_holdings_enrich.py.

This module does NOT:
    - read or write config.USER_HOLDINGS (one-shot only, per grill-me Q6).
    - merge / dedupe against existing lists (caller's job, at the call site).
    - send alerts or interact with cron (caller's job).
"""

from __future__ import annotations

import json
import re
from typing import Any

# 6-digit numeric ETF code (Shanghai/Shenzhen funds). Not strict about leading
# zeros; e.g. "015930" is a valid Shenzhen code in some classifications, but
# the watch list uses unprefixed 6-digit codes. Keep it permissive at parse
# time; tighter validation belongs at the akshare layer if needed.
_CODE_PATTERN = re.compile(r"^\d{6}$")


def parse_extra_holdings_arg(raw: str) -> list[dict[str, Any]]:
    """Parse the --extra-holdings CLI argument.

    Args:
        raw: JSON array string, e.g. '[{"code": "159530"}]'.
            Empty / whitespace-only returns [].

    Returns:
        List of dicts, each with at minimum {"code": str(6 digits)}.
        Optional keys "name" and "sector" are present iff supplied in input.

    Raises:
        ValueError: If `raw` is not a JSON array of dicts with a 6-digit code.
    """
    if not raw or not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"--extra-holdings must be a JSON array of {{code, name?, sector?}} "
            f"objects; got invalid JSON: {e.msg}"
        ) from e

    if not isinstance(data, list):
        raise ValueError(
            f"--extra-holdings must be a JSON array; got {type(data).__name__}"
        )

    result: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(
                f"--extra-holdings[{i}] must be an object; got {type(item).__name__}"
            )
        if "code" not in item:
            raise ValueError(f"--extra-holdings[{i}] missing required field 'code'")
        code = item["code"]
        if not isinstance(code, str) or not _CODE_PATTERN.match(code):
            raise ValueError(
                f"--extra-holdings[{i}].code must be a 6-digit string; got {code!r}"
            )

        # Build a fresh dict per entry so callers can't mutate shared state.
        entry: dict[str, Any] = {"code": code}
        if "name" in item and item["name"] is not None:
            entry["name"] = item["name"]
        if "sector" in item and item["sector"] is not None:
            entry["sector"] = item["sector"]
        result.append(entry)

    return result