"""TTFund API client — thin HTTP wrapper for the天天基金 skills API.

Call format:
    POST https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill/invoke
    Header: X-API-Key: {TTFUND_APIKEY}
    Body: {"skill_id": "...", "_skill_version": "...", ...}

Response: {"code": 0, "message": "ok", "data": {"raw_result": {"body": {...}}}}

Public API:
    call(skill_id, params, version="1.0") -> body dict
"""

from __future__ import annotations

import time
from typing import Any

import requests

from src.config import TTFUND_API_URL


# ── Custom Exceptions ─────────────────────────────────────────────────────────

class TTFundError(Exception):
    """Base exception for all TTFund client errors."""

    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.code = code


class IntervalTooShortError(TTFundError):
    """Raised when two API calls occur less than 1 second apart."""

    def __init__(self, elapsed: float):
        super().__init__(
            f"API call interval {elapsed:.3f}s is below the 1-second minimum"
        )
        self.elapsed = elapsed


class TTFundTimeoutError(TTFundError):
    """Raised when the request times out."""

    def __init__(self, cause: Exception):
        super().__init__(f"Request timed out: {cause}")
        self.cause = cause


class TTFundRateLimitError(TTFundError):
    """Raised when the server returns HTTP 429."""

    def __init__(self):
        super().__init__("Rate limit hit (HTTP 429)", code=429)


class TTFundNetworkError(TTFundError):
    """Raised on network / connection errors."""

    def __init__(self, cause: Exception):
        super().__init__(f"Network error: {cause}")
        self.cause = cause


class TTFundAPIError(TTFundError):
    """Raised when the API response code is non-zero."""

    def __init__(self, code: int, message: str):
        super().__init__(f"API error {code}: {message}", code=code)
        self.message = message


class TTFundMissingKeyError(TTFundError):
    """Raised when TTFUND_APIKEY is not set."""

    def __init__(self):
        super().__init__("TTFUND_APIKEY environment variable is not set")


# ── Module-level session (lazy init) ─────────────────────────────────────────

_session: requests.Session | None = None

_last_call_time: float = 0.0


def _get_session() -> requests.Session:
    """Lazily initialise and return a requests.Session.

    Using a shared Session enables connection pooling and keep-alive.
    """
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


# ── High-level API wrappers ─────────────────────────────────────────────────────

def get_fund_info(fcode: str) -> dict:
    """"Return basic info for fund ``fcode`` via FUND_BASE_INFOS."""
    return call("FUND_BASE_INFOS", {"fcode": fcode})



def get_nav_history(fund_id: str, range: str = "y") -> dict:
    """Return NAV history for fund ``fund_id`` via FUND_NAV_INFO.

    Args:
        fund_id: Fund identifier.
        range:   One of y / 3y / 6y / n / 2n / 3n / ln.
    """
    return call("FUND_NAV_INFO", {"fund_id": fund_id, "range": range})


def get_index_info(index_id: str, scope: str = "all") -> dict:
    """Return index details via FUND_INDEX_INFO.

    Args:
        index_id: Index identifier.
        scope:    One of all / gold / macro / risk.
    """
    return call("FUND_INDEX_INFO", {"index_id": index_id, "scope": scope})


def get_holdings(fund_id: str, holding_type: str = "stock") -> dict:
    """Return holdings for fund ``fund_id`` via FUND_HOLDING_INFO.

    Args:
        fund_id:      Fund identifier.
        holding_type: One of stock / bond / all.
    """
    return call("FUND_HOLDING_INFO", {"fund_id": fund_id, "holding_type": holding_type})


def search_funds(page: int = 1, page_num: int = 20, order: str = "desc") -> dict:
    """Screen funds by criteria via FUND_CONDITION_SELECT.


    Args:
        page:     Page number (1-based).
        page_num: Results per page.
        order:    Sort order, e.g. "desc" or "asc".
    """
    return call("FUND_CONDITION_SELECT", {"page": page, "pageNum": page_num, "order": order})



def get_manager_info(name: str) -> dict:
    """Return manager profile via FUND_MANAGER_INFO."""
    return call("FUND_MANAGER_INFO", {"manager_name": name})



def get_gold_info(scope: str = "all") -> dict:
    """Return gold fund info via FUND_HUAAN_GOLD_INFO.


    Args:
        scope: One of all / gold / macro / risk.
    """
    return call("FUND_HUAAN_GOLD_INFO", {"scope": scope})


def get_strategy(name: str, scope: str = "all") -> dict:
    """Return investment-advisory strategy via FUND_TG_STRATEGY_INFO.

    Args:
        name:  Strategy name.
        scope: One of all / gold / macro / risk.
    """
    return call("FUND_TG_STRATEGY_INFO", {"strategy_name": name, "scope": scope})



# ── Public API ───────────────────────────────────────────────────────────────

_MIN_INTERVAL = 1.0  # seconds between consecutive calls


def call(
    skill_id: str,
    params: dict[str, Any],
    *,
    version: str = "1.0",
) -> dict[str, Any]:
    """Call a天天基金 skill and return the parsed body.

    Args:
        skill_id:     Skill identifier, e.g. "fund_etf_info".
        params:       Additional parameters passed in the request body.
        version:      Skill version string, default "1.0".

    Returns:
        The ``data.raw_result.body`` dict from the API response.

    Raises:
        TTFundMissingKeyError:   TTFUND_APIKEY is not set.
        IntervalTooShortError:   Called less than 1 s after the previous call.
        TTFundTimeoutError:      Request timed out.
        TTFundRateLimitError:    Server returned HTTP 429.
        TTFundNetworkError:      Network / connection error.
        TTFundAPIError:          API returned a non-zero ``code``.
    """
    from src.config import TTFUND_APIKEY

    if not TTFUND_APIKEY:
        raise TTFundMissingKeyError()

    # ── Interval enforcement ───────────────────────────────────────────────────
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if _last_call_time > 0 and elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
        now = time.time()
    _last_call_time = now

    # ── Build request ──────────────────────────────────────────────────────────
    session = _get_session()
    body = {
        "skill_id": skill_id,
        "_skill_version": version,
        **params,
    }
    headers = {
        "X-API-Key": TTFUND_APIKEY,
    }

    try:
        response = session.post(
            TTFUND_API_URL,
            json=body,
            headers=headers,
            timeout=45,
        )
    except requests.exceptions.Timeout as e:
        raise TTFundTimeoutError(e) from e
    except requests.exceptions.ConnectionError as e:
        raise TTFundNetworkError(e) from e

    # ── HTTP-level errors ─────────────────────────────────────────────────────
    if response.status_code == 429:
        raise TTFundRateLimitError()

    if response.status_code >= 400:
        response.raise_for_status()

    # ── Parse JSON response ────────────────────────────────────────────────────
    payload = response.json()
    code = payload.get("code")
    message = payload.get("message", "")

    if code != 0:
        raise TTFundAPIError(code=code, message=message)

    return payload["data"]["raw_result"]["body"]