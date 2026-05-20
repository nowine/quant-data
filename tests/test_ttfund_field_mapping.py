"""Field mapping verification tests for TTFUND API — calls real API.

These tests hit the live 天天基金 skills API and record the actual
response field names so we can document the correct mapping.

Run with:  pytest tests/test_ttfund_field_mapping.py -v -s
"""

import os
import sys

import pytest
import requests

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TTFUND_APIKEY = os.environ.get("TTFUND_APIKEY", "")
if not TTFUND_APIKEY:
    pytest.skip("TTFUND_APIKEY not set", allow_module_level=True)

API_URL = "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill/invoke"
HEADERS = {"X-API-Key": TTFUND_APIKEY}

# ── Low-level helper to call the API directly (bypasses interval guard) ──────

def _raw_call(skill_id: str, params: dict) -> dict:
    body = {"skill_id": skill_id, "_skill_version": "1.0", **params}
    resp = requests.post(API_URL, json=body, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"API error {payload.get('code')}: {payload.get('message')}")
    return payload["data"]["raw_result"]["body"]


# ── Test: FUND_NAV_INFO ────────────────────────────────────────────────────────

def test_fund_nav_info_field_mapping():
    """Call FUND_NAV_INFO and print all response fields."""
    result = _raw_call("FUND_NAV_INFO", {"fund_id": "510300", "range": "y"})

    print("\n=== FUND_NAV_INFO ===")
    _print_dict(result, indent=0)

    # Assertions
    assert result["success"] is True
    assert result["errorCode"] == 0
    assert "data" in result
    nav_items = result["data"]["nav_history"]["items"]
    assert len(nav_items) > 0
    first = nav_items[0]
    assert "FSRQ" in first,  f"Date field FSRQ missing, got: {list(first.keys())}"
    assert "DWJZ" in first,  f"NAV field DWJZ missing, got: {list(first.keys())}"
    assert "JZZZL" in first, f"Growth field JZZZL missing, got: {list(first.keys())}"


# ── Test: FUND_BASE_INFOS ────────────────────────────────────────────────────

def test_fund_base_infos_field_mapping():
    """Call FUND_BASE_INFOS and print all response fields."""
    result = _raw_call("FUND_BASE_INFOS", {"fcode": "510300"})

    print("\n=== FUND_BASE_INFOS ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert result["errorCode"] == 0
    assert len(result["data"]) > 0
    fund = result["data"][0]
    assert "FCODE" in fund,    f"FCODE missing, got: {list(fund.keys())}"
    assert "SHORTNAME" in fund, f"SHORTNAME missing, got: {list(fund.keys())}"


# ── Test: FUND_HOLDING_INFO ──────────────────────────────────────────────────

def test_fund_holding_info_field_mapping():
    """Call FUND_HOLDING_INFO and print all response fields."""
    result = _raw_call("FUND_HOLDING_INFO", {"fund_id": "510300", "holdingType": "stock"})

    print("\n=== FUND_HOLDING_INFO ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result
    top_holdings = result["data"]["top_holdings"]["stock"]
    assert len(top_holdings) > 0
    first = top_holdings[0]
    assert "GPDM" in first,  f"Stock code field GPDM missing, got: {list(first.keys())}"
    assert "GPJC" in first,  f"Stock name field GPJC missing, got: {list(first.keys())}"
    assert "JZBL" in first,  f"Holding ratio field JZBL missing, got: {list(first.keys())}"


# ── Test: FUND_INDEX_INFO ─────────────────────────────────────────────────────

def test_fund_index_info_field_mapping():
    """Call FUND_INDEX_INFO and print all response fields."""
    result = _raw_call("FUND_INDEX_INFO", {"index_id": "000300", "scope": "all"})

    print("\n=== FUND_INDEX_INFO ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result
    profile = result["data"]["index_profile"]
    assert "index_code" in profile
    assert "index_name" in profile
    quote = result["data"]["quote"]
    assert "current_point" in quote
    val = result["data"]["valuation"]
    assert "pe_ttm" in val
    assert "pe_percentile_10y" in val


# ── Test: FUND_MANAGER_INFO ───────────────────────────────────────────────────

def test_fund_manager_info_field_mapping():
    """Call FUND_MANAGER_INFO and print all response fields."""
    result = _raw_call("FUND_MANAGER_INFO", {"manager_name": "柳军"})

    print("\n=== FUND_MANAGER_INFO ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result
    profile = result["data"]["manager_profile"]
    assert "manager_id" in profile
    assert "manager_name" in profile
    assert "current_fund_count" in profile
    assert len(result["data"]["managed_funds"]) > 0


# ── Test: FUND_CONDITION_SELECT ───────────────────────────────────────────────

def test_fund_condition_select_field_mapping():
    """Call FUND_CONDITION_SELECT and print all response fields."""
    result = _raw_call("FUND_CONDITION_SELECT", {"page": 1, "pageNum": 5, "order": "desc"})

    print("\n=== FUND_CONDITION_SELECT ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result


# ── Test: FUND_HUAAN_GOLD_INFO ────────────────────────────────────────────────

def test_fund_huaan_gold_info_field_mapping():
    """Call FUND_HUAAN_GOLD_INFO and print all response fields."""
    result = _raw_call("FUND_HUAAN_GOLD_INFO", {"scope": "all"})

    print("\n=== FUND_HUAAN_GOLD_INFO ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result


# ── Test: FUND_TG_STRATEGY_INFO ──────────────────────────────────────────────

def test_fund_tg_strategy_info_field_mapping():
    """Call FUND_TG_STRATEGY_INFO and print all response fields."""
    result = _raw_call("FUND_TG_STRATEGY_INFO", {"name": "红利", "scope": "all"})

    print("\n=== FUND_TG_STRATEGY_INFO ===")
    _print_dict(result, indent=0)

    assert result["success"] is True
    assert "data" in result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_dict(d: dict, indent: int = 0, depth: int = 0, max_depth: int = 5):
    """Recursively print dict keys and value types, truncated for readability."""
    prefix = "  " * indent
    if depth >= max_depth:
        print(f"{prefix}  ... (max depth)")
        return
    if not isinstance(d, dict):
        print(f"{prefix}  {type(d).__name__}: {repr(d)[:100]}")
        return
    for k, v in list(d.items())[:60]:
        if isinstance(v, dict):
            print(f"{prefix}  {k}: dict (len={len(v)})")
            _print_dict(v, indent=indent + 1, depth=depth + 1)
        elif isinstance(v, list):
            print(f"{prefix}  {k}: list (len={len(v)})")
            if v and isinstance(v[0], dict) and depth < max_depth:
                _print_dict(v[0], indent=indent + 1, depth=depth + 1)
        else:
            print(f"{prefix}  {k}: {type(v).__name__} = {repr(v)[:80]}")