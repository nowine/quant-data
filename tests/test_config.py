"""Tests for src/config.py — ETF Data Collection System"""

import os
import pytest


class TestConfigBasics:
    """TASK-101 test cases"""

    def test_etf_watch_list_not_empty(self):
        """ETF_WATCH_LIST must have at least 20 entries"""
        from src.config import ETF_WATCH_LIST
        assert len(ETF_WATCH_LIST) >= 20

    def test_etf_watch_list_entry_structure(self):
        """Each ETF entry must have code, name, index keys"""
        from src.config import ETF_WATCH_LIST
        for e in ETF_WATCH_LIST:
            assert 'code' in e, f"Missing 'code' in entry: {e}"
            assert 'name' in e, f"Missing 'name' in entry: {e}"
            assert 'index' in e, f"Missing 'index' in entry: {e}"

    def test_index_watch_list_not_empty(self):
        """INDEX_WATCH_LIST must have at least 16 entries"""
        from src.config import INDEX_WATCH_LIST
        assert len(INDEX_WATCH_LIST) >= 16

    def test_ttfund_api_url_https(self):
        """TTFUND_API_URL must start with https://"""
        from src.config import TTFUND_API_URL
        assert TTFUND_API_URL.startswith("https://")

    def test_ttfund_api_key_from_env(self, monkeypatch):
        """TTFUND_APIKEY must be read from environment variable"""
        monkeypatch.setenv("TTFUND_APIKEY", "test-key-12345")
        import importlib
        import src.config
        importlib.reload(src.config)
        from src.config import TTFUND_APIKEY
        assert TTFUND_APIKEY == "test-key-12345"

    def test_data_dir_contains_project_name(self):
        """DATA_DIR must contain 'ETF轮动分析框架'"""
        from src.config import DATA_DIR
        assert "ETF轮动分析框架" in DATA_DIR

    def test_slow_api_timeout_default(self):
        """SLOW_API_TIMEOUT must default to 45"""
        from src.config import SLOW_API_TIMEOUT
        assert SLOW_API_TIMEOUT == 45