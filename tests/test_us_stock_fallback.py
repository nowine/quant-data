"""Tests for us_stock_index dual-source fallback (2026-09-28).

Primary : akshare.stock_us_spot_em (eastmoney), filtered to major indices.
Fallback: akshare.index_us_stock_sina daily bars, normalized output.

Background: eastmoney endpoint had recurring RemoteDisconnected outages
(9/28 evening cron) and its old "empty filter → return all rows" fallback
leaked junk stock rows into historical CSVs.
"""

from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Isolate DATA_DIR (no prod log/cache writes) and skip the 5s inter-call sleep.

    log_collect resolves DATA_DIR at call time; without isolation the degraded
    logs from these tests leaked into the repo's real data/logs/*.csv.
    """
    import importlib

    from src import config
    from src import logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src import akshare_client as ac

    importlib.reload(ac)
    monkeypatch.setattr(ac, "_rate_limit", lambda: None)


def _fake_spot_df():
    """Eastmoney-shaped spot df with the 3 major indices + junk rows."""
    rows = [
        {"名称": "大自然药业", "最新价": 13.46, "涨跌幅": 354.73, "代码": "105.UPC"},
        {"名称": "标普500指数", "最新价": 7743.41, "涨跌幅": 0.51, "代码": ".INX"},
        {"名称": "纳斯达克综合指数", "最新价": 27068.72, "涨跌幅": 0.48, "代码": ".IXIC"},
        {"名称": "道琼斯工业指数", "最新价": 51828.62, "涨跌幅": 0.93, "代码": ".DJI"},
    ]
    return pd.DataFrame(rows)


def _fake_sina_hist(closes):
    """Sina-shaped daily-bar df: date/open/high/low/close/volume/amount."""
    dates = ["2026-09-24", "2026-09-25"][-len(closes):]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c * 0.99 for c in closes],
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.98 for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
            "amount": [0] * len(closes),
        }
    )


# ── Primary source ────────────────────────────────────────────────────────────


class TestPrimary:
    def test_filters_major_indices(self):
        from src import akshare_client as ac

        with patch.object(ac.ak, "stock_us_spot_em", return_value=_fake_spot_df()):
            df = ac._fetch_us_index_primary()
        assert len(df) == 3
        assert set(df["指数代码"]) == {".INX", ".IXIC", ".DJI"}
        inx = df[df["指数代码"] == ".INX"].iloc[0]
        assert inx["收盘价"] == pytest.approx(7743.41)
        assert inx["涨跌幅"] == pytest.approx(0.51)

    def test_raises_when_filter_empty(self):
        """Index rows missing must raise (old code returned the whole junk table)."""
        from src import akshare_client as ac

        junk = pd.DataFrame([{"名称": "大自然药业", "最新价": 13.46}])
        with patch.object(ac.ak, "stock_us_spot_em", return_value=junk):
            with pytest.raises(Exception):
                ac._fetch_us_index_primary()


# ── Sina fallback ─────────────────────────────────────────────────────────────


class TestSinaFallback:
    def test_normalizes_three_indices(self):
        from src import akshare_client as ac

        hist_by_sym = {
            ".INX": _fake_sina_hist([7704.13, 7743.41]),
            ".IXIC": _fake_sina_hist([26939.37, 27068.72]),
            ".DJI": _fake_sina_hist([51349.98, 51828.62]),
        }

        def fake_sina(symbol):
            return hist_by_sym[symbol]

        with patch.object(ac.ak, "index_us_stock_sina", side_effect=fake_sina):
            df = ac._fetch_us_index_sina()

        assert len(df) == 3
        assert list(df.columns) == ["指数代码", "指数名称", "日期", "收盘价", "涨跌幅"]
        assert set(df["指数代码"]) == {".INX", ".IXIC", ".DJI"}
        inx = df[df["指数代码"] == ".INX"].iloc[0]
        assert inx["收盘价"] == pytest.approx(7743.41)
        assert inx["日期"] == "2026-09-25"

    def test_pct_change_from_previous_close(self):
        from src import akshare_client as ac

        with patch.object(
            ac.ak, "index_us_stock_sina", return_value=_fake_sina_hist([100.0, 101.0])
        ):
            df = ac._fetch_us_index_sina()
        assert df.iloc[0]["涨跌幅"] == pytest.approx(1.0)

    def test_raises_on_insufficient_history(self):
        from src import akshare_client as ac

        with patch.object(ac.ak, "index_us_stock_sina", return_value=_fake_sina_hist([100.0])):
            with pytest.raises(Exception):
                ac._fetch_us_index_sina()


# ── Combined fetch (primary → fallback) ───────────────────────────────────────


class TestFetchUsIndices:
    def test_primary_success_skips_fallback(self):
        from src import akshare_client as ac

        with patch.object(ac.ak, "stock_us_spot_em", return_value=_fake_spot_df()), patch.object(
            ac.ak, "index_us_stock_sina", side_effect=AssertionError("fallback must not run")
        ):
            df = ac._fetch_us_indices()
        assert len(df) == 3
        assert "指数代码" in df.columns

    def test_primary_failure_uses_sina(self):
        from src import akshare_client as ac

        hist_by_sym = {
            ".INX": _fake_sina_hist([7704.13, 7743.41]),
            ".IXIC": _fake_sina_hist([26939.37, 27068.72]),
            ".DJI": _fake_sina_hist([51349.98, 51828.62]),
        }

        with patch.object(
            ac.ak, "stock_us_spot_em", side_effect=ConnectionError("RemoteDisconnected")
        ), patch.object(
            ac.ak, "index_us_stock_sina", side_effect=lambda symbol: hist_by_sym[symbol]
        ):
            df = ac._fetch_us_indices()

        assert len(df) == 3
        assert "指数代码" in df.columns

    def test_both_fail_raises_runtime_error(self):
        from src import akshare_client as ac

        with patch.object(
            ac.ak, "stock_us_spot_em", side_effect=ConnectionError("down")
        ), patch.object(ac.ak, "index_us_stock_sina", side_effect=ConnectionError("down too")):
            with pytest.raises(RuntimeError, match="both sources failed"):
                ac._fetch_us_indices()

    def test_fallback_logs_degraded(self):
        """Fallback engagement must be visible in the collect log."""
        from src import akshare_client as ac

        calls = []
        with patch.object(ac, "log_collect", side_effect=lambda **kw: calls.append(kw)):
            with patch.object(
                ac.ak, "stock_us_spot_em", side_effect=ConnectionError("down")
            ), patch.object(
                ac.ak, "index_us_stock_sina", return_value=_fake_sina_hist([100.0, 101.0])
            ):
                ac._fetch_us_indices()

        degraded = [c for c in calls if c.get("status") == "degraded"]
        assert len(degraded) == 1
        assert degraded[0]["task"] == "us_stock_index"
        assert "sina" in degraded[0]["message"]


# ── Cached wrapper ────────────────────────────────────────────────────────────


class TestCachedWrapper:
    def test_get_us_stock_index_writes_cache(self, monkeypatch, tmp_path):
        """Full path: fetch via fallback → cache file created under DATA_DIR/cache."""
        import importlib

        from src import config
        from src import logger as logger_module

        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ac

        importlib.reload(ac)

        def _raise(exc):
            def _f(*a, **kw):
                raise exc

            return _f

        monkeypatch.setattr(ac, "_rate_limit", lambda: None)
        monkeypatch.setattr(ac.ak, "stock_us_spot_em", _raise(ConnectionError("down")))
        monkeypatch.setattr(
            ac.ak, "index_us_stock_sina", lambda symbol=None: _fake_sina_hist([100.0, 101.0])
        )

        df = ac.get_us_stock_index()
        assert len(df) == 3
        assert (tmp_path / "cache" / "us_stock_index.csv").exists()
