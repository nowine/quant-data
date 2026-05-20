"""Tests for CACHE_TTL and VALIDATION_RULES in config.py."""

import pytest


def test_cache_ttl_has_required_keys():
    from src.config import CACHE_TTL
    required_keys = [
        "etf_snapshot", "macro_north_flow", "etf_scale", "margin",
        "macro_pmi", "macro_cpi", "macro_ppi", "macro_m2",
        "macro_lpr", "macro_shrzgm", "macro_gdp", "macro_industrial",
        "nav_history", "index_valuation", "holdings"
    ]
    for key in required_keys:
        assert key in CACHE_TTL, f"CACHE_TTL missing key: {key}"


def test_cache_ttl_values_reasonable():
    from src.config import CACHE_TTL
    for key, hours in CACHE_TTL.items():
        assert 1 <= hours <= 8760, f"CACHE_TTL[{key}]={hours} out of range [1, 8760]"


def test_validation_rules_has_required_keys():
    from src.config import VALIDATION_RULES
    required_keys = ["PMI", "CPI_YOY", "PPI_YOY", "PE_PERCENTILE", "NAV"]
    for key in required_keys:
        assert key in VALIDATION_RULES, f"VALIDATION_RULES missing key: {key}"


def test_validation_rules_structure():
    from src.config import VALIDATION_RULES
    for key, rule in VALIDATION_RULES.items():
        assert "min" in rule and "max" in rule, f"VALIDATION_RULES[{key}] missing min/max"
        assert rule["min"] <= rule["max"], f"VALIDATION_RULES[{key}] min > max"