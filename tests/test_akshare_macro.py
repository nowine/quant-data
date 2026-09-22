"""Tests for akshare macro data methods.

TDD Step 1: Write tests first (Red phase).
Each test mocks the underlying akshare function and verifies the
caching wrapper returns a DataFrame.
"""

import importlib

import pandas as pd
import pytest


def test_get_pmi_returns_dataframe(monkeypatch):
    """PMI should return a DataFrame (mocked akshare call)."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak, "macro_china_pmi", lambda: pd.DataFrame({"PMI": [51.5]})
    )
    result = akshare_client.get_pmi()
    assert isinstance(result, pd.DataFrame)


def test_get_cpi_returns_dataframe(monkeypatch):
    """CPI yearly should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_cpi_yearly",
        lambda: pd.DataFrame({"CPI": [2.1]}),
    )
    result = akshare_client.get_cpi()
    assert isinstance(result, pd.DataFrame)


def test_get_ppi_returns_dataframe(monkeypatch):
    """PPI yearly should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_ppi_yearly",
        lambda: pd.DataFrame({"PPI": [-1.2]}),
    )
    result = akshare_client.get_ppi()
    assert isinstance(result, pd.DataFrame)


def test_get_m2_returns_dataframe(monkeypatch):
    """Money supply M2 should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_money_supply",
        lambda: pd.DataFrame({"M2": [2850000.0]}),
    )
    result = akshare_client.get_m2()
    assert isinstance(result, pd.DataFrame)


def test_get_lpr_returns_dataframe(monkeypatch):
    """LPR should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak, "macro_china_lpr", lambda: pd.DataFrame({"LPR_1Y": [3.45]})
    )
    result = akshare_client.get_lpr()
    assert isinstance(result, pd.DataFrame)


def test_get_shrzgm_returns_dataframe(monkeypatch):
    """SH/RZGM should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_shrzgm",
        lambda: pd.DataFrame({"社融规模": [35000.0]}),
    )
    result = akshare_client.get_shrzgm()
    assert isinstance(result, pd.DataFrame)


def test_get_gdp_returns_dataframe(monkeypatch):
    """GDP should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak, "macro_china_gdp", lambda: pd.DataFrame({"GDP": [1260000.0]})
    )
    result = akshare_client.get_gdp()
    assert isinstance(result, pd.DataFrame)


def test_get_industrial_returns_dataframe(monkeypatch):
    """Industrial production YoY should return a DataFrame."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_industrial_production_yoy",
        lambda: pd.DataFrame({"工业增加值": [6.5]}),
    )
    result = akshare_client.get_industrial()
    assert isinstance(result, pd.DataFrame)


def test_get_industry_alloc_returns_dataframe(monkeypatch):
    """Industry allocation should return a DataFrame given a year."""
    from src import akshare_client

    importlib.reload(akshare_client)
    monkeypatch.setattr(
        akshare_client.ak,
        "fund_portfolio_industry_allocation_em",
        lambda year: pd.DataFrame({"行业": ["银行"], "占比": [15.0]}),
    )
    result = akshare_client.get_industry_alloc(2023)
    assert isinstance(result, pd.DataFrame)
