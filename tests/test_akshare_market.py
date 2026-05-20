"""Tests for akshare_client market data methods (TASK-502)."""

import pandas as pd


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


def test_get_etf_snapshot_returns_dataframe(monkeypatch, tmp_path):
    """get_etf_snapshot should return a DataFrame"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    monkeypatch.setattr(
        akshare_client.ak,
        "fund_etf_category_sina",
        lambda: pd.DataFrame({"symbol": ["510300"], "name": ["test"]}),
    )

    result = akshare_client.get_etf_snapshot()
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0


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
        lambda symbol, adjust: pd.DataFrame({"date": ["2024-01-01"], "flow": [1.5]}),
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
