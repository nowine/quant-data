"""Tests for tech_indicator module."""

import numpy as np
import pandas as pd
import pytest

from src.tech_indicator import (
    calc_ma,
    calc_ma_deviation,
    calc_atr,
    calc_rsi,
    calc_volume_ratio,
    calc_bollinger,
    calc_macd,
    calc_premium_rate,
)


@pytest.fixture
def ohlcv_df():
    """Minimal OHLCV DataFrame for testing — 30 rows of synthetic data."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    close = 10 + np.cumsum(np.random.randn(30) * 0.5)
    high = close + np.random.rand(30) * 0.5
    low = close - np.random.rand(30) * 0.5
    open_prices = low + (high - low) * np.random.rand(30)
    volume = np.random.randint(100_000, 1_000_000, size=30)

    return pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=pd.DatetimeIndex(dates),
    )


class TestCalcMA:
    def test_returns_dataframe_with_ma_columns(self, ohlcv_df):
        result = calc_ma(ohlcv_df, periods=(20, 60))
        assert "MA20" in result.columns
        assert "MA60" in result.columns
        assert len(result) == len(ohlcv_df)

    def test_ma_values_all_present(self, ohlcv_df):
        # min_periods=1 means all rows get a value (early rows are NaN-free averages)
        result = calc_ma(ohlcv_df, periods=(20,))
        assert len(result) == len(ohlcv_df)

    def test_default_periods(self, ohlcv_df):
        result = calc_ma(ohlcv_df)
        assert "MA20" in result.columns
        assert "MA60" in result.columns


class TestCalcMADeviation:
    def test_deviation_is_percentage(self, ohlcv_df):
        result = calc_ma_deviation(ohlcv_df, periods=(20,))
        valid = result["DEV20"].dropna()
        assert all(valid > -50)  # reasonable range


class TestCalcATR:
    def test_returns_series(self, ohlcv_df):
        result = calc_atr(ohlcv_df)
        assert isinstance(result, pd.Series)

    def test_atr_positive(self, ohlcv_df):
        result = calc_atr(ohlcv_df)
        assert result.dropna().ge(0).all()

    def test_atr_has_valid_values(self, ohlcv_df):
        result = calc_atr(ohlcv_df, period=14)
        valid = result.dropna()
        assert len(valid) >= 1  # at least one valid ATR value


class TestCalcRSI:
    def test_returns_series(self, ohlcv_df):
        result = calc_rsi(ohlcv_df)
        assert isinstance(result, pd.Series)

    def test_rsi_range_0_to_100(self, ohlcv_df):
        result = calc_rsi(ohlcv_df)
        valid = result.dropna()
        assert valid.between(0, 100).all()

    def test_rsi_has_valid_values(self, ohlcv_df):
        result = calc_rsi(ohlcv_df, period=14)
        valid = result.dropna()
        assert len(valid) >= 1


class TestCalcVolumeRatio:
    def test_returns_series(self, ohlcv_df):
        result = calc_volume_ratio(ohlcv_df)
        assert isinstance(result, pd.Series)

    def test_first_nan_for_insufficient_data(self, ohlcv_df):
        result = calc_volume_ratio(ohlcv_df, period=20)
        assert result.iloc[:19].isna().all()

    def test_volume_ratio_last_row(self, ohlcv_df):
        result = calc_volume_ratio(ohlcv_df, period=20)
        last_vr = result.iloc[-1]
        assert not pd.isna(last_vr)
        assert 0 < last_vr < 20


class TestCalcBollinger:
    def test_returns_dataframe_with_three_columns(self, ohlcv_df):
        result = calc_bollinger(ohlcv_df)
        assert "BB_UPPER" in result.columns
        assert "BB_MIDDLE" in result.columns
        assert "BB_LOWER" in result.columns

    def test_upper_gt_middle_gt_lower(self, ohlcv_df):
        result = calc_bollinger(ohlcv_df)
        valid = result.dropna()
        assert (valid["BB_UPPER"] >= valid["BB_MIDDLE"]).all()
        assert (valid["BB_MIDDLE"] >= valid["BB_LOWER"]).all()


class TestCalcMACD:
    def test_returns_dataframe_with_dif_dea_macd(self, ohlcv_df):
        result = calc_macd(ohlcv_df)
        assert "DIF" in result.columns
        assert "DEA" in result.columns
        assert "MACD" in result.columns

    def test_macd_is_dif_minus_dea(self, ohlcv_df):
        result = calc_macd(ohlcv_df)
        valid = result.dropna()
        assert np.allclose(valid["MACD"], valid["DIF"] - valid["DEA"], atol=1e-10)


class TestCalcPremiumRate:
    def test_scalar_premium_rate(self):
        rate = calc_premium_rate(1.012, 1.0)
        assert pytest.approx(rate, abs=1e-6) == 0.012

    def test_premium_is_positive_when_price_above_nav(self):
        rate = calc_premium_rate(1.05, 1.0)
        assert rate > 0

    def test_discount_is_negative(self):
        rate = calc_premium_rate(0.95, 1.0)
        assert rate < 0

    def test_series_premium_rate(self):
        prices = pd.Series([1.0, 1.05, 0.98])
        nav = 1.0
        rates = calc_premium_rate(prices, nav)
        expected = pd.Series([0.0, 0.05, -0.02])
        assert np.allclose(rates, expected, atol=1e-10)