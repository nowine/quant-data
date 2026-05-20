"""TTFund API client — thin HTTP wrapper for the天天基金 skills API.

Call format:
    POST https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill/invoke
    Header: X-API-Key: {TTFUND_APIKEY}
    Body: {"skill_id": "...", "_skill_version": "...", ...}

Response: {"code": 0, "message": "ok", "data": {"raw_result": {"body": {...}}}}

Public API:
    call(skill_id, params, version="1.0") -> body dict
"""

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
        raise IntervalTooShortError(elapsed)
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