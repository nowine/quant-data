"""Tests for akshare_client module."""

import pandas as pd


def test_with_cache_miss_calls_fetch_fn(monkeypatch, tmp_path):
    """Cache miss should call fetch_fn and save result"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client
    importlib.reload(akshare_client)

    fetch_called = False

    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"value": [42]})

    result = akshare_client._with_cache("test_key", 24, fake_fetch)
    assert fetch_called, "Should call fetch_fn on cache miss"
    assert result["value"][0] == 42


def test_with_cache_hit_does_not_call_fetch_fn(monkeypatch, tmp_path):
    """Cache hit should not call fetch_fn"""
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    # Pre-populate cache
    from src.storage import save_csv
    cache_file = tmp_path / "cache" / "cached_key.csv"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    save_csv(pd.DataFrame({"value": [99]}), str(cache_file))

    from src import akshare_client
    importlib.reload(akshare_client)

    fetch_called = False

    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"value": [999]})

    result = akshare_client._with_cache("cached_key", 24, fake_fetch)
    assert not fetch_called, "Should not call fetch_fn on cache hit"
    assert result["value"][0] == 99