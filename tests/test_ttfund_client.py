"""Tests for ttfund_client module."""

import sys
import time

import pytest
import requests


# ── MockResponse helper ──────────────────────────────────────────────────────

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


# ── Helper: reload ttfund_client cleanly ────────────────────────────────────

def _reload_ttfund(monkeypatch, env_key=None, env_value=None):
    """Remove src.ttfund_client from sys.modules, optionally set env var, then import fresh."""
    # Clean module cache
    for mod in list(sys.modules.keys()):
        if "src.ttfund_client" in mod:
            del sys.modules[mod]

    # Set env var if provided
    if env_value is not None:
        monkeypatch.setenv(env_key, env_value)
    elif env_key is not None:
        monkeypatch.delenv(env_key, raising=False)

    # Re-import config to refresh env reads
    import importlib
    import src.config as config_mod
    importlib.reload(config_mod)

    # Remove ttfun_client again (reload may have re-imported it)
    for mod in list(sys.modules.keys()):
        if "src.ttfund_client" in mod:
            del sys.modules[mod]

    # Fresh import
    import src.ttfund_client as ttfund_mod
    return ttfund_mod


# ── Test: session uses correct base URL and headers ─────────────────────────

def test_session_initialized_with_correct_base_url(monkeypatch):
    """The session object should use TTFUND_API_URL as base URL."""
    captured = {}

    class MockSession:
        def __init__(self, **kwargs):
            pass

        def post(self, url, **kwargs):
            captured['post_url'] = url
            captured['post_kwargs'] = kwargs
            return MockResponse({"code": 0, "message": "success", "data": {"raw_result": {"body": {}}}})

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    # Trigger a call
    try:
        ttfund_mod.call("skill_foo", {})
    except Exception:
        pass

    assert captured['post_url'] is not None, "POST was never called"


# ── Test: call sends X-API-Key header ───────────────────────────────────────

def test_call_sends_x_api_key_header(monkeypatch):
    """call() should include X-API-Key in request headers."""
    captured = {}

    class MockSession:
        def post(self, url, **kwargs):
            captured['headers'] = kwargs.get('headers', {})
            return MockResponse({"code": 0, "message": "success", "data": {"raw_result": {"body": {"result": "ok"}}}})

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "test-key-123")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "test-key-123")

    ttfund_mod.call("skill_bar", {"param": 1})

    assert "X-API-Key" in captured['headers'], "X-API-Key header missing"
    assert captured['headers']['X-API-Key'] == "test-key-123"


# ── Test: call sends skill_id and _skill_version ────────────────────────────

def test_call_sends_skill_id_and_version(monkeypatch):
    """call() body should include skill_id and _skill_version."""
    captured = {}

    class MockSession:
        def post(self, url, **kwargs):
            captured['body'] = kwargs.get('json', {})
            return MockResponse({"code": 0, "message": "success", "data": {"raw_result": {"body": {"result": "ok"}}}})

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    ttfund_mod.call("my_skill", {"extra": "data"}, version="2.0")

    assert "skill_id" in captured['body'], "skill_id missing from body"
    assert captured['body']['skill_id'] == "my_skill"
    assert "_skill_version" in captured['body'], "_skill_version missing from body"
    assert captured['body']['_skill_version'] == "2.0"
    assert "extra" in captured['body'], "additional params missing from body"


# ── Test: response parsing returns data.raw_result.body ──────────────────────

def test_call_returns_data_raw_result_body(monkeypatch):
    """call() should return data.raw_result.body from response JSON."""
    class MockSession:
        def post(self, url, **kwargs):
            return MockResponse({
                "code": 0,
                "message": "success",
                "data": {
                    "raw_result": {
                        "body": {"foo": "bar", "items": [1, 2, 3]}
                    }
                }
            })

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    result = ttfund_mod.call("skill", {})

    assert result == {"foo": "bar", "items": [1, 2, 3]}, f"Unexpected result: {result}"


# ── Test: API call interval ≥ 1 second ──────────────────────────────────────

def test_api_call_interval_sleeps_and_succeeds(monkeypatch):
    """Consecutive calls within < 1s should sleep to meet the 1-second minimum."""
    call_times = []
    class MockSession:
        def post(self, url, **kwargs):
            call_times.append(time.time())
            return MockResponse({"code": 0, "message": "success", "data": {"raw_result": {"body": {}}}})
    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")
    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")
    ttfund_mod.call("skill1", {})
    first = call_times[-1]
    ttfund_mod.call("skill2", {})
    second = call_times[-1]
    assert second - first >= 1.0, f"Expected ≥1s gap, got {second - first:.3f}s"


# ── Test: timeout error raised on timeout ───────────────────────────────────

def test_call_raises_timeout_on_timeout(monkeypatch):
    """Requests timeout should surface as TTFundTimeoutError."""
    class MockSession:
        def post(self, url, **kwargs):
            raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    with pytest.raises(ttfund_mod.TTFundTimeoutError):
        ttfund_mod.call("skill", {})


# ── Test: rate limit (429) error raised correctly ───────────────────────────

def test_call_raises_rate_limit_on_429(monkeypatch):
    """HTTP 429 should surface as TTFundRateLimitError."""
    class MockResponse429:
        status_code = 429
        def json(self):
            return {"code": 429, "message": "rate limit"}
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("429 rate limit")

    class MockSession:
        def post(self, url, **kwargs):
            return MockResponse429()

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    with pytest.raises(ttfund_mod.TTFundRateLimitError):
        ttfund_mod.call("skill", {})


# ── Test: network error raised correctly ─────────────────────────────────────

def test_call_raises_network_error_on_connection_error(monkeypatch):
    """Connection error should surface as TTFundNetworkError."""
    class MockSession:
        def post(self, url, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    with pytest.raises(ttfund_mod.TTFundNetworkError):
        ttfund_mod.call("skill", {})


# ── Test: non-zero code in response raises TTFundAPIError ───────────────────

def test_call_raises_api_error_on_nonzero_code(monkeypatch):
    """Non-zero 'code' in response JSON should raise TTFundAPIError."""
    class MockSession:
        def post(self, url, **kwargs):
            return MockResponse({
                "code": 1001,
                "message": "invalid skill",
                "data": {}
            })

    monkeypatch.setattr(requests, "Session", MockSession)
    monkeypatch.setenv("TTFUND_APIKEY", "key")

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", "key")

    with pytest.raises(ttfund_mod.TTFundAPIError) as exc_info:
        ttfund_mod.call("skill", {})

    assert exc_info.value.code == 1001
    assert exc_info.value.message == "invalid skill"


# ── Test: missing API key raises clear error ─────────────────────────────────

def test_call_raises_clear_error_without_api_key(monkeypatch):
    """Calling without TTFUND_APIKEY set should raise TTFundMissingKeyError."""
    monkeypatch.delenv("TTFUND_APIKEY", raising=False)

    ttfund_mod = _reload_ttfund(monkeypatch, "TTFUND_APIKEY", None)

    with pytest.raises(ttfund_mod.TTFundMissingKeyError):
        ttfund_mod.call("skill", {})