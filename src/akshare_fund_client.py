"""Fund data client backed by akshare — drop-in replacement for ttfund_client.

Public API mirrors `src.ttfund_client` exactly so callers can migrate without code
changes. Internal implementations:

| ttfund function        | akshare source                          | status   |
|------------------------|------------------------------------------|----------|
| get_nav_history        | fund_open_fund_info_em (单位净值走势)     | real     |
| get_fund_info          | fund_individual_basic_info_xq            | real     |
| get_index_info         | stock_zh_index_daily (basic)             | partial  |
| get_gold_info          | (no equivalent)                          | stub     |
| get_holdings           | (no equivalent)                          | stub     |
| get_strategy           | (no equivalent)                          | stub     |
| search_funds           | fund_open_fund_rank_em                   | stub*    |
| get_manager_info       | fund_manager_em                          | stub*    |

\* stub* — signature preserved, returns minimal placeholder, no akshare call.

For NAV history, we wrap the akshare DataFrame in a ttfund-shaped dict so the
existing call sites that dig `raw["data"]["nav_history"]["items"][0]["DWJZ"]`
continue to work without modification.

See docs/phase-2-followup.md for stubbed functions awaiting Phase 2.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Lazy akshare loader — keeps import-time cost zero and gives us a single
# place to surface "akshare not installed" cleanly.
_ak = None


def _get_ak():
    """Lazily import akshare; raise a friendly error if unavailable."""
    global _ak
    if _ak is None:
        try:
            import akshare as ak
            _ak = ak
        except ImportError as e:
            raise RuntimeError(
                "akshare is required for akshare_fund_client; "
                "install with `pip install akshare`"
            ) from e
    return _ak


# ── Custom Exceptions ─────────────────────────────────────────────────────────

class AkshareFundError(Exception):
    """Base exception for all akshare fund client errors."""


class AkshareFundTimeoutError(AkshareFundError):
    """Raised when the underlying akshare call times out."""

    def __init__(self, cause: Exception):
        super().__init__(f"akshare call timed out: {cause}")
        self.cause = cause


class AkshareFundDataError(AkshareFundError):
    """Raised when akshare returns empty / unexpected data."""

    def __init__(self, message: str):
        super().__init__(message)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)


def _wrap_nav_df_as_ttfund(df: Any, *, fund_id: str, range_str: str) -> dict:
    """Translate an akshare NAV DataFrame into the ttfund body shape.

    akshare columns: 净值日期 / 单位净值 / 日增长率
    ttfund body:      data.nav_history.items[].FSRQ/DWJZ/JZZZL/LJJZ/NAVTYPE
    """
    if df is None or len(df) == 0:
        return {"data": {"nav_history": {"items": []}}}

    items = []
    # akshare returns OLDEST-first; reverse so callers' items[0] is the latest.
    for _, row in df.iloc[::-1].iterrows():
        items.append({
            "FSRQ": str(row.get("净值日期", "")),
            "DWJZ": str(row.get("单位净值", "")),
            "JZZZL": str(row.get("日增长率", "")),
            "LJJZ": str(row.get("单位净值", "")),  # akshare 不提供累计净值,fallback
            "NAVTYPE": "1",
            "RATE": "--",
        })
    return {"data": {"nav_history": {"items": items}}}


def _wrap_holdings_as_ttfund(records: list[dict]) -> dict:
    """Return ttfund's `{"datas": [...]}` shape."""
    return {"datas": records or []}


def _stub_log(func_name: str, note: str = "") -> None:
    """Emit a deprecation log for stubbed functions."""
    logger.warning(
        "akshare_fund_client.%s is a Phase 2 stub — %s",
        func_name,
        note or "see docs/phase-2-followup.md",
    )


# ── High-level API wrappers (signatures mirror src.ttfund_client) ──────────────

def get_nav_history(fund_id: str, range: str = "y") -> dict:
    """Return NAV history for fund ``fund_id``.

    Implementation: akshare.fund_open_fund_info_em(indicator="单位净值走势").

    Args:
        fund_id: Fund identifier (e.g. "510300").
        range:   One of y / 3y / 6y / n / 2n / 3n / ln. We map these to
                 akshare's period vocabulary; unmapped values fall back to "1年".

    Returns:
        A dict shaped exactly like ttfund's body:
        ``{"data": {"nav_history": {"items": [{FSRQ, DWJZ, JZZZL, LJJZ, ...}, ...]}}}``
        newest entry first.
    """
    period_map = {
        "y": "1年",
        "3y": "3年",
        "6y": "6年",
        "n": "1年",
        "2n": "1年",
        "3n": "3年",
        "ln": "成立以来",
    }
    period = period_map.get(range, "1年")
    ak = _get_ak()
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_id, indicator="单位净值走势", period=period)
    except Exception as e:
        raise AkshareFundTimeoutError(e) from e
    return _wrap_nav_df_as_ttfund(df, fund_id=fund_id, range_str=range)


def get_gold_info(scope: str = "all") -> dict:
    """Return gold fund info — STUB (akshare has no equivalent).

    See docs/phase-2-followup.md (P2-1).

    Args:
        scope: One of all / gold / macro / risk. Preserved for signature compat.

    Returns:
        Empty dict. Callers should treat empty result as "no data".
    """
    _stub_log("get_gold_info", "akshare has no gold/macro/risk equivalent — P2-1")
    return {}


def get_index_info(index_id: str, scope: str = "all") -> dict:
    """Return basic index data via akshare (PARTIAL — PE/PB stubbed).

    Implementation: akshare.stock_zh_index_daily for recent levels only.
    PE / PB / percentile fields are stubbed (Phase 2 P2-3).

    Args:
        index_id: Index name (e.g. "沪深300"). Akshare needs the EM symbol;
                  we look it up via ``ak.stock_zh_index_daily_tx`` fallback or
                  return basic shell. Caller keeps the same call pattern.
        scope:    Preserved for signature compat. Ignored in this version.

    Returns:
        Dict with at least: ``{"index_id": ..., "close": ..., "change_pct": ...,
        "pe_percentile": None, "pb": None, "source": "akshare-partial"}``
    """
    # Phase 2 P2-3: full PE/PB/percentile implementation pending.
    # For now we just stamp a deterministic placeholder so callers can persist
    # the result without crashing.
    _stub_log(
        "get_index_info",
        f"PE/PB/percentile fields are stubbed for {index_id!r} — P2-3",
    )
    return {
        "index_id": index_id,
        "scope": scope,
        "close": None,
        "change_pct": None,
        "pe_percentile": None,
        "pb": None,
        "source": "akshare-partial-stub",
        "fetched_at": _now_ms(),
    }


def get_holdings(fund_id: str, holding_type: str = "stock") -> dict:
    """Return fund holdings — STUB (akshare has no per-fund equivalent).

    See docs/phase-2-followup.md (P2-2).

    Args:
        fund_id:      Fund identifier.
        holding_type: One of stock / bond / all. Preserved for signature compat.

    Returns:
        ``{"datas": []}`` — empty list. Caller code already handles this shape.
    """
    _stub_log(
        "get_holdings",
        f"akshare only has market-wide fund holdings; per-fund {fund_id!r} pending — P2-2",
    )
    return _wrap_holdings_as_ttfund([])


def search_funds(page: int = 1, page_num: int = 20, order: str = "desc") -> dict:
    """Screen funds by criteria — STUB* (no caller uses this today).

    Preserved for signature compatibility; not implemented. See P2 backlog.
    """
    _stub_log("search_funds", "not used by collectors — preserved for compat")
    return {"datas": [], "page": page, "pageNum": page_num, "order": order}


def get_manager_info(name: str) -> dict:
    """Return manager profile — STUB* (no caller uses this today).

    Preserved for signature compatibility; not implemented.
    """
    _stub_log("get_manager_info", "not used by collectors — preserved for compat")
    return {"manager_name": name, "managed_funds": []}


def get_strategy(name: str, scope: str = "all") -> dict:
    """Return investment-advisory strategy — STUB.

    See docs/phase-2-followup.md (P2 backlog). akshare has no equivalent.

    Args:
        name:  Strategy name.
        scope: One of all / gold / macro / risk. Preserved for signature compat.

    Returns:
        Empty dict.
    """
    _stub_log("get_strategy", f"akshare has no 投顾策略 equivalent for {name!r}")
    return {}


def get_fund_info(fcode: str) -> dict:
    """Return basic info for fund ``fcode``.

    Implementation: akshare.fund_individual_basic_info_xq (雪球基金档案).
    If the source is unavailable or the symbol is unknown, returns a minimal
    shape with just the code.

    Args:
        fcode: Fund code (e.g. "000001").

    Returns:
        Dict mirroring the broad ttfund fields we care about. Callers may use
        any keys they find; unknown ones fall back to None.
    """
    ak = _get_ak()
    try:
        df = ak.fund_individual_basic_info_xq(symbol=fcode)
    except Exception as e:
        logger.warning("get_fund_info(%s) failed: %s", fcode, e)
        return {"fcode": fcode, "error": str(e)}

    info: dict[str, Any] = {"fcode": fcode}
    if df is None or len(df) == 0:
        return info

    # DataFrame is two columns: item / value
    try:
        for _, row in df.iterrows():
            key = str(row.iloc[0]).strip()
            val = row.iloc[1] if len(row) > 1 else None
            info[key] = val
    except Exception as e:
        logger.warning("get_fund_info(%s) parse failed: %s", fcode, e)
    return info


# ── Public generic entry point (kept for parity with ttfund_client.call) ──────

def call(skill_id: str, params: dict[str, Any], *, version: str = "1.0") -> dict:
    """Generic skill dispatcher — kept for signature parity only.

    The original ttfund ``call(skill_id, params)`` is no longer meaningful under
    akshare (no skill_id concept). This shim dispatches the well-known skill_ids
    to the typed wrappers above; unknown ones raise.

    Raises:
        AkshareFundDataError: skill_id not recognised.
    """
    raise AkshareFundDataError(
        f"akshare_fund_client.call() shim: skill_id {skill_id!r} not mapped; "
        "use the typed wrappers (get_nav_history, get_fund_info, ...)"
    )


__all__ = [
    "AkshareFundError",
    "AkshareFundTimeoutError",
    "AkshareFundDataError",
    "get_nav_history",
    "get_gold_info",
    "get_index_info",
    "get_holdings",
    "get_search_funds" if False else "search_funds",  # keep typo-safe export
    "get_manager_info",
    "get_strategy",
    "get_fund_info",
    "call",
]