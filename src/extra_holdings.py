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
import os
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

# 6-digit numeric ETF code (Shanghai/Shenzhen funds). Not strict about leading
# zeros; e.g. "015930" is a valid Shenzhen code in some classifications, but
# the watch list uses unprefixed 6-digit codes. Keep it permissive at parse
# time; tighter validation belongs at the akshare layer if needed.
_CODE_PATTERN = re.compile(r"^\d{6}$")

# Cache configuration (see ADR-003).
CACHE_FILENAME = "fund_name.csv"
CACHE_TTL_HOURS = 24
_AKSHORE_CODE_COL = "基金代码"
_AKSHORE_NAME_COL = "基金简称"


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


# ── akshare enrichment seam (ADR-003 Q2) ─────────────────────────────────────


def _cache_path() -> Path:
    """Return the fund_name cache file path under $HOME/.cache/quant-data/."""
    return Path(os.path.expanduser("~")) / ".cache" / "quant-data" / CACHE_FILENAME


def _fetch_fund_name_from_akshare() -> pd.DataFrame:
    """Call akshare.fund_name_em() and return the raw DataFrame.

    This is a separate function so it can be mocked at the seam. The actual
    import is lazy to keep test collection fast and to avoid requiring akshare
    for the parser-only seam (commit 1).

    Raises whatever akshare raises on failure; the caller (build_extra_holdings_set)
    catches and degrades gracefully.
    """
    import akshare as ak  # lazy import — see module docstring

    return ak.fund_name_em()


def _read_cache(path: Path) -> pd.DataFrame | None:
    """Read cache file if it exists and is fresh; else return None.

    Stale caches are returned as None so the caller refreshes. This is the
    only place we judge cache validity (testable, single source of truth).
    """
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > CACHE_TTL_HOURS:
        return None
    try:
        df = pd.read_csv(path, dtype={_AKSHORE_CODE_COL: str})
        if _AKSHORE_CODE_COL not in df.columns or _AKSHORE_NAME_COL not in df.columns:
            # Cache file from an older schema — treat as stale.
            return None
        return df
    except Exception:
        # Corrupt cache → treat as stale; caller will refresh.
        return None


def _write_cache(path: Path, df: pd.DataFrame) -> None:
    """Persist the akshare table to CSV. Best-effort: failures are logged, not raised."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Force code column to str so leading zeros and 6-digit shape round-trip.
        out = df.copy()
        out[_AKSHORE_CODE_COL] = out[_AKSHORE_CODE_COL].astype(str)
        out.to_csv(path, index=False)
    except Exception:
        # Cache write failure must not break the caller. ADR-003 §后果.
        pass


def build_extra_holdings_set(codes: list[str]) -> pd.DataFrame:
    """Enrich a list of ETF codes with name (and sector=None) via akshare.

    Sees a cache at ~/.cache/quant-data/fund_name.csv (24h TTL). On cache miss
    or staleness, fetches fund_name_em() and rewrites the cache. On akshare
    failure, returns rows with name="" and sector=None (no exception) so the
    caller (collector_daily) can keep going.

    Output DataFrame columns: [code, name, sector], dtype code=str.

    Empty input returns an empty DataFrame with the right columns.
    """
    if not codes:
        return pd.DataFrame(columns=["code", "name", "sector"])

    cache_path = _cache_path()
    fund_df = _read_cache(cache_path)

    if fund_df is None:
        try:
            fund_df = _fetch_fund_name_from_akshare()
        except Exception:
            # akshare unavailable: best-effort fallback per ADR-003.
            return _empty_result(codes)
        _write_cache(cache_path, fund_df)

    # Build the result by joining on string codes. Use merge with dtype safety.
    fund_df = fund_df.copy()
    fund_df[_AKSHORE_CODE_COL] = fund_df[_AKSHORE_CODE_COL].astype(str)

    requested = pd.DataFrame({"code": [str(c) for c in codes]})
    merged = requested.merge(
        fund_df[[_AKSHORE_CODE_COL, _AKSHORE_NAME_COL]],
        left_on="code",
        right_on=_AKSHORE_CODE_COL,
        how="left",
    )

    # Normalize columns and fill missing.
    result = pd.DataFrame(
        {
            "code": merged["code"].astype(str),
            "name": merged[_AKSHORE_NAME_COL].fillna("").astype(str),
            "sector": None,
        }
    )
    return result


def _empty_result(codes: list[str]) -> pd.DataFrame:
    """Return a DataFrame with the right shape but no enrichment."""
    return pd.DataFrame(
        {
            "code": [str(c) for c in codes],
            "name": ["" for _ in codes],
            "sector": [None for _ in codes],
        }
    )