"""Tests for the 8 new ttfund API wrapper methods."""

import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def _reload_ttfund(monkeypatch, env_value="test-key"):
    """Remove src.ttfund_client from sys.modules, set env var, return fresh module."""
    for mod in list(sys.modules.keys()):
        if "src.ttfund_client" in mod:
            del sys.modules[mod]

    import importlib
    import src.config as config_mod
    importlib.reload(config_mod)

    for mod in list(sys.modules.keys()):
        if "src.ttfund_client" in mod:
            del sys.modules[mod]

    if env_value is not None:
        monkeypatch.setenv("TTFUND_APIKEY", env_value)
    else:
        monkeypatch.delenv("TTFUND_APIKEY", raising=False)

    import src.ttfund_client as ttfund_mod
    return ttfund_mod


# ── Test: get_fund_info ──────────────────────────────────────────────────────

def test_get_fund_info_returns_dataframe(monkeypatch):
    """get_fund_info should call FUND_BASE_INFOS skill and return DataFrame/dict."""
    import requests as req_lib

    class MockSession:
        def post(self, url, **kwargs):
            return MockResponse({
                "code": 0,
                "message": "success",
                "data": {
                    "raw_result": {
                        "body": {
                            "success": True,
                            "errorCode": 0,
                            "data": {
                                "fundName": "测试基金",
                                "fcode": "000001"
                            }
                        }
                    }
                }
            })

    monkeypatch.setattr(req_lib, "Session", lambda: MockSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    result = ttfund_mod.get_fund_info("000001")

    assert isinstance(result, (pd.DataFrame, dict))


def test_get_fund_info_sends_correct_skill_id(monkeypatch):
    """get_fund_info should send skill_id FUND_BASE_INFOS."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_fund_info("510300")

    assert captured["body"]["skill_id"] == "FUND_BASE_INFOS"
    assert captured["body"]["fcode"] == "510300"


# ── Test: get_nav_history ────────────────────────────────────────────────────

def test_get_nav_history_returns_dataframe(monkeypatch):
    """get_nav_history should call FUND_NAV_INFO and return DataFrame/dict."""
    import requests as req_lib

    class MockSession:
        def post(self, url, **kwargs):
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {
                    "success": True, "errorCode": 0, "data": {}
                }}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: MockSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    result = ttfund_mod.get_nav_history("510300", "y")

    assert isinstance(result, (pd.DataFrame, dict))


def test_get_nav_history_sends_correct_params(monkeypatch):
    """get_nav_history should send fundId and range."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_nav_history("510300", "3y")

    assert captured["body"]["skill_id"] == "FUND_NAV_INFO"
    assert captured["body"]["fundId"] == "510300"
    assert captured["body"]["range"] == "3y"


# ── Test: get_index_info ────────────────────────────────────────────────────

def test_get_index_info_sends_correct_params(monkeypatch):
    """get_index_info should send indexId and scope."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_index_info("000001", "all")

    assert captured["body"]["skill_id"] == "FUND_INDEX_INFO"
    assert captured["body"]["indexId"] == "000001"
    assert captured["body"]["scope"] == "all"


# ── Test: get_holdings ──────────────────────────────────────────────────────

def test_get_holdings_sends_correct_params(monkeypatch):
    """get_holdings should send fundId and holdingType."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_holdings("510300", "stock")

    assert captured["body"]["skill_id"] == "FUND_HOLDING_INFO"
    assert captured["body"]["fundId"] == "510300"
    assert captured["body"]["holdingType"] == "stock"


# ── Test: search_funds ──────────────────────────────────────────────────────

def test_search_funds_sends_correct_params(monkeypatch):
    """search_funds should send page, pageNum, order."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.search_funds(1, 20, "desc")

    assert captured["body"]["skill_id"] == "FUND_CONDITION_SELECT"
    assert captured["body"]["page"] == 1
    assert captured["body"]["pageNum"] == 20
    assert captured["body"]["order"] == "desc"


# ── Test: get_manager_info ───────────────────────────────────────────────────

def test_get_manager_info_sends_correct_name(monkeypatch):
    """get_manager_info should send name."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_manager_info("张三")

    assert captured["body"]["skill_id"] == "FUND_MANAGER_INFO"
    assert captured["body"]["name"] == "张三"


# ── Test: get_gold_info ─────────────────────────────────────────────────────

def test_get_gold_info_sends_correct_scope(monkeypatch):
    """get_gold_info should send scope."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_gold_info("all")

    assert captured["body"]["skill_id"] == "FUND_HUAAN_GOLD_INFO"
    assert captured["body"]["scope"] == "all"


# ── Test: get_strategy ──────────────────────────────────────────────────────

def test_get_strategy_sends_correct_params(monkeypatch):
    """get_strategy should send name and scope."""
    import requests as req_lib
    captured = {}

    class CapturingSession:
        def post(self, url, **kwargs):
            captured["body"] = kwargs.get("json", {})
            return MockResponse({
                "code": 0, "message": "success",
                "data": {"raw_result": {"body": {"success": True, "errorCode": 0, "data": {}}}}
            })

    monkeypatch.setattr(req_lib, "Session", lambda: CapturingSession())
    monkeypatch.setenv("TTFUND_APIKEY", "test-key")

    ttfund_mod = _reload_ttfund(monkeypatch, "test-key")
    ttfund_mod.get_strategy("稳健型", "all")

    assert captured["body"]["skill_id"] == "FUND_TG_STRATEGY_INFO"
    assert captured["body"]["name"] == "稳健型"
    assert captured["body"]["scope"] == "all"