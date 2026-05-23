"""Tests for akshare_client market data methods (TASK-502)."""

import pandas as pd
import pytest


def test_get_etf_history_fallback(monkeypatch, tmp_path):
    """模拟 fund_etf_hist_sina 失败，自动降级到 fund_etf_hist_em"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    # Mock sina fails, em succeeds
    def sina_fail(**kwargs):
        raise Exception("sina failed")

    def em_succeed(**kwargs):
        return pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})

    monkeypatch.setattr(akshare_client.ak, "fund_etf_hist_sina", sina_fail)
    monkeypatch.setattr(akshare_client.ak, "fund_etf_hist_em", em_succeed)

    result = akshare_client.get_etf_history("510300")
    assert len(result) > 0
    assert "close" in result.columns


class TestGetEtfSnapshot:
    """TDD: get_etf_snapshot should use THS source (fund_etf_category_ths).

    Bug: Sina source (fund_etf_category_sina) returns only 382 ETFs with prefixed
    codes (sz/sh). THS returns 1576 ETFs with pure numeric codes matching config.
    """

    def _reload_with_ths_mock(self, monkeypatch, tmp_path, ths_mock, sina_mock=None):
        """Reload akshare_client with THS mock set BEFORE import.

        Must set mock on the `akshare` module BEFORE importing akshare_client
        (which holds a direct reference to the original function at import time).
        """
        import importlib
        import os
        from src import config, logger as logger_module

        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))

        # Clear any existing cache so the mock is actually called
        cache_dir = os.path.join(str(tmp_path), "cache")
        os.makedirs(cache_dir, exist_ok=True)

        importlib.reload(logger_module)

        # Patch akshare module BEFORE reloading akshare_client
        import akshare as ak
        ak.fund_etf_category_ths = lambda: ths_mock
        if sina_mock is not None:
            ak.fund_etf_category_sina = lambda: sina_mock
        else:
            # If sina_mock not provided, make it return empty to prove it's not used
            ak.fund_etf_category_sina = lambda: pd.DataFrame({"should_not": ["appear"]})

        from src import akshare_client
        importlib.reload(akshare_client)
        return akshare_client

    def test_uses_fund_etf_category_ths_not_sina(self, monkeypatch, tmp_path):
        """get_etf_snapshot must call fund_etf_category_ths, not fund_etf_category_sina."""
        ths_mock = pd.DataFrame({
            "序号": [1], "基金代码": ["510300"], "基金名称": ["test"],
            "当前-单位净值": [3.8], "当前-累计净值": [3.8],
            "前一日-单位净值": [3.7], "前一日-累计净值": [3.7],
            "增长值": [0.1], "增长率": [2.7],
            "赎回状态": ["开放"], "申购状态": ["开放"],
            "最新-交易日": ["2026-05-22"], "最新-单位净值": [3.8],
            "最新-累计净值": [3.8], "基金类型": ["股票型"], "查询日期": ["2026-05-22"],
        })

        ak_client = self._reload_with_ths_mock(monkeypatch, tmp_path, ths_mock)
        result = ak_client.get_etf_snapshot()

        assert len(result) == 1
        assert result.iloc[0]["代码"] == "510300"

    def test_returns_pure_numeric_codes(self, monkeypatch, tmp_path):
        """Output codes must be pure numeric strings (e.g. '510300'), not prefixed (e.g. 'sz510300')."""
        ths_mock = pd.DataFrame({
            "序号": [1, 2, 3],
            "基金代码": ["510300", "159530", "588750"],
            "基金名称": ["沪深300ETF", "机器人ETF", "芯片ETF"],
            "当前-单位净值": [3.8, 1.7, 2.4],
            "当前-累计净值": [3.8, 1.7, 2.4],
            "前一日-单位净值": [3.7, 1.6, 2.3],
            "前一日-累计净值": [3.7, 1.6, 2.4],
            "增长值": [0.1, 0.1, 0.1],
            "增长率": [2.7, 6.2, 4.3],
            "赎回状态": ["开放", "开放", "开放"],
            "申购状态": ["开放", "开放", "开放"],
            "最新-交易日": ["2026-05-22", "2026-05-22", "2026-05-22"],
            "最新-单位净值": [3.8, 1.7, 2.4],
            "最新-累计净值": [3.8, 1.7, 2.4],
            "基金类型": ["股票型", "股票型", "股票型"],
            "查询日期": ["2026-05-22", "2026-05-22", "2026-05-22"],
        })

        ak_client = self._reload_with_ths_mock(monkeypatch, tmp_path, ths_mock)
        result = ak_client.get_etf_snapshot()

        assert "代码" in result.columns
        codes = result["代码"].tolist()
        for code in codes:
            assert not str(code).startswith(("sz", "sh", "sz1", "sh5", "sz5")), \
                f"Code '{code}' should be pure numeric, not prefixed"

    def test_output_column_names_match_config(self, monkeypatch, tmp_path):
        """Output must have columns compatible with SECTOR_MAPPING: 代码, 涨跌幅."""
        ths_mock = pd.DataFrame({
            "序号": [1],
            "基金代码": ["510300"],
            "基金名称": ["test"],
            "当前-单位净值": [3.8],
            "当前-累计净值": [3.8],
            "前一日-单位净值": [3.7],
            "前一日-累计净值": [3.7],
            "增长值": [0.1],
            "增长率": [2.7],
            "赎回状态": ["开放"],
            "申购状态": ["开放"],
            "最新-交易日": ["2026-05-22"],
            "最新-单位净值": [3.8],
            "最新-累计净值": [3.8],
            "基金类型": ["股票型"],
            "查询日期": ["2026-05-22"],
        })

        ak_client = self._reload_with_ths_mock(monkeypatch, tmp_path, ths_mock)
        result = ak_client.get_etf_snapshot()

        assert "代码" in result.columns
        assert "涨跌幅" in result.columns
        assert "名称" in result.columns or "基金名称" in result.columns

    def test_ths_covers_more_etfs_than_sina(self, monkeypatch, tmp_path):
        """THS mock returning 3 ETFs must result in DataFrame with 3 rows."""
        ths_mock = pd.DataFrame({
            "序号": [1, 2, 3],
            "基金代码": ["510300", "159530", "588750"],
            "基金名称": ["沪深300", "机器人", "芯片"],
            "当前-单位净值": [3.8, 1.7, 2.4],
            "当前-累计净值": [3.8, 1.7, 2.4],
            "前一日-单位净值": [3.7, 1.6, 2.3],
            "前一日-累计净值": [3.7, 1.6, 2.4],
            "增长值": [0.1, 0.1, 0.1],
            "增长率": [2.7, 6.2, 4.3],
            "赎回状态": ["开放", "开放", "开放"],
            "申购状态": ["开放", "开放", "开放"],
            "最新-交易日": ["2026-05-22", "2026-05-22", "2026-05-22"],
            "最新-单位净值": [3.8, 1.7, 2.4],
            "最新-累计净值": [3.8, 1.7, 2.4],
            "基金类型": ["股票型", "股票型", "股票型"],
            "查询日期": ["2026-05-22", "2026-05-22", "2026-05-22"],
        })

        ak_client = self._reload_with_ths_mock(monkeypatch, tmp_path, ths_mock)
        result = ak_client.get_etf_snapshot()

        assert len(result) == 3


def test_get_north_flow_returns_dataframe(monkeypatch, tmp_path):
    """get_north_flow should return a DataFrame"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    monkeypatch.setattr(
        akshare_client.ak,
        "stock_hsgt_hist_em",
        lambda symbol: pd.DataFrame({"date": ["2024-01-01"], "flow": [1.5]}),
    )

    result = akshare_client.get_north_flow("北向资金", months=3)
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0


def test_get_etf_scale_returns_dataframe(monkeypatch, tmp_path):
    """get_etf_scale should return a DataFrame"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    monkeypatch.setattr(
        akshare_client.ak,
        "fund_etf_scale_sse",
        lambda: pd.DataFrame({"symbol": ["510300"], "scale": [1e9]}),
    )

    result = akshare_client.get_etf_scale()
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0


def test_get_margin_sh_returns_dataframe(monkeypatch, tmp_path):
    """get_margin_sh should return a DataFrame"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    monkeypatch.setattr(
        akshare_client.ak,
        "macro_china_market_margin_sh",
        lambda: pd.DataFrame({"date": ["2024-01-01"], "margin": [1e8]}),
    )

    result = akshare_client.get_margin_sh()
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
