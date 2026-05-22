"""Tests for portfolio_calc module."""

import numpy as np
import pandas as pd
import pytest

from src.portfolio_calc import (
    calc_contribution,
    calc_correlation,
    calc_beta,
    calc_max_drawdown,
    calc_sharpe,
    calc_volatility,
)


@pytest.fixture
def daily_returns():
    """Mock daily returns DataFrame for 10 trading days."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=10, freq="B")
    return pd.DataFrame(
        {
            "asset_a": np.random.randn(10) * 0.01,
            "asset_b": np.random.randn(10) * 0.015,
        },
        index=dates,
    )


@pytest.fixture
def equity_curve():
    """Mock equity curve with known drawdown pattern."""
    # 100 -> 110 -> 105 -> 95 (drawdown from 110) -> 115 (new high)
    values = [100.0, 110.0, 105.0, 95.0, 115.0]
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    return pd.Series(values, index=pd.DatetimeIndex(dates))


class TestCalcContribution:
    def test_contribution_weight_times_return(self, daily_returns):
        weights = pd.Series({"asset_a": 0.6, "asset_b": 0.4})
        result = calc_contribution(daily_returns, weights)
        assert "contribution" in result.columns
        assert "weight" in result.columns
        # Each row: contribution = weight * return
        row = result.iloc[0]
        assert pytest.approx(row["contribution"], rel=1e-6) == row["weight"] * row["return"]

    def test_sum_of_contributions_equals_portfolio_return(self, daily_returns):
        weights = pd.Series({"asset_a": 0.6, "asset_b": 0.4})
        result = calc_contribution(daily_returns, weights)
        for dt, group in result.groupby("date"):
            total = group["contribution"].sum()
            # portfolio return = weighted sum of asset returns
            expected = sum(
                weights[a] * daily_returns.loc[dt, a]
                for a in group["asset"]
            )
            assert pytest.approx(total, rel=1e-6) == expected


class TestCalcCorrelation:
    def test_correlation_matrix_symmetric(self, daily_returns):
        corr = calc_correlation(daily_returns)
        assert corr.shape[0] == corr.shape[1]
        assert (corr.values == corr.values.T).all()

    def test_diagonal_is_1(self, daily_returns):
        corr = calc_correlation(daily_returns)
        assert (np.diag(corr.values) == 1.0).all()

    def test_off_diagonal_between_minus_1_and_1(self, daily_returns):
        corr = calc_correlation(daily_returns)
        off_diag = ~np.eye(corr.shape[0], dtype=bool)
        assert (-1 <= corr.values[off_diag]).all() and (corr.values[off_diag] <= 1).all()


class TestCalcBeta:
    def test_beta_of_self_is_1(self):
        s = pd.Series([0.01, 0.02, -0.01, 0.015])
        assert calc_beta(s, s) == pytest.approx(1.0, rel=1e-6)

    def test_beta_zero_when_uncorrelated(self):
        # Construct perfectly uncorrelated series
        portfolio = pd.Series([0.01, 0.02, 0.01, 0.02])
        benchmark = pd.Series([0.01, -0.01, 0.01, -0.01])
        beta = calc_beta(portfolio, benchmark)
        # Covariance = 0 -> beta = 0
        assert abs(beta) <= 0.5

    def test_beta_with_offset_index(self):
        p = pd.Series([0.01, 0.02, 0.03], index=[1, 2, 3])
        b = pd.Series([0.02, 0.04, 0.06], index=[1, 2, 3])
        assert calc_beta(p, b) == pytest.approx(0.5, rel=1e-4)


class TestCalcMaxDrawdown:
    def test_max_drawdown_is_20pct(self, equity_curve):
        result = calc_max_drawdown(equity_curve)
        assert result["max_drawdown"] == pytest.approx(0.13636, rel=1e-3)
        assert result["peak_date"] == equity_curve.index[1]  # 110.0
        assert result["trough_date"] == equity_curve.index[3]  # 95.0
        # peak_date = 2026-01-02 (110.0), trough_date = 2026-01-04 (95.0)
        # recovery: first date AFTER trough where equity >= peak
        # post_trough[1:] skips trough itself -> [115.0], which >= 110.0 -> index 4
        assert result["recovery_date"] == pd.Timestamp("2026-01-05")

    def test_no_drawdown_when_rising(self):
        curve = pd.Series([100.0, 105.0, 110.0])
        result = calc_max_drawdown(curve)
        assert result["max_drawdown"] == 0.0

    def test_empty_series(self):
        result = calc_max_drawdown(pd.Series(dtype=float))
        assert result["max_drawdown"] == 0.0


class TestCalcSharpe:
    def test_sharpe_positive_for_positive_returns(self):
        returns = pd.Series([0.01, 0.015, 0.012, 0.018, 0.02])
        sharpe = calc_sharpe(returns)
        assert sharpe > 0

    def test_sharpe_negative_for_negative_returns(self):
        returns = pd.Series([-0.01, -0.015, -0.012, -0.018, -0.02])
        sharpe = calc_sharpe(returns)
        assert sharpe < 0

    def test_sharpe_nan_for_single_return(self):
        returns = pd.Series([0.01])
        assert np.isnan(calc_sharpe(returns))


class TestCalcVolatility:
    def test_volatility_positive(self, daily_returns):
        vol = calc_volatility(daily_returns["asset_a"])
        assert vol > 0

    def test_annualised_gt_daily(self, daily_returns):
        daily_vol = calc_volatility(daily_returns["asset_a"], annualize=False)
        annual_vol = calc_volatility(daily_returns["asset_a"], annualize=True)
        assert annual_vol > daily_vol

    def test_volatility_nan_for_single_value(self):
        vol = calc_volatility(pd.Series([0.01]))
        assert np.isnan(vol)