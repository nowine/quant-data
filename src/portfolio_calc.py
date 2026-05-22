"""Portfolio-level calculations: contribution, correlation, beta, drawdown, Sharpe.

This module provides pure computational functions with no API dependencies.
All inputs are DataFrames/Series of returns or equity curves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Contribution ───────────────────────────────────────────────────────────────

def calc_contribution(returns_df: pd.DataFrame, weights: pd.Series) -> pd.DataFrame:
    """Calculate each holding's return contribution to portfolio return.

    Args:
        returns_df: DataFrame with date index, columns = individual asset returns.
        weights:    Series mapping column names to portfolio weights (must sum ~1).

    Returns:
        DataFrame with columns: date, asset, weight, return, contribution.
    """
    rows = []
    for asset in returns_df.columns:
        if asset not in weights:
            continue
        w = weights[asset]
        for dt, ret in returns_df[asset].items():
            rows.append(
                {
                    "date": dt,
                    "asset": asset,
                    "weight": w,
                    "return": ret,
                    "contribution": w * ret,
                }
            )
    return pd.DataFrame(rows)


# ── Correlation ───────────────────────────────────────────────────────────────

def calc_correlation(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate pairwise Pearson correlation matrix of asset returns.

    Args:
        returns_df: DataFrame with date index, columns = individual asset returns.

    Returns:
        Correlation matrix (square DataFrame).
    """
    return returns_df.corr(method="pearson")


# ── Beta ───────────────────────────────────────────────────────────────────────

def calc_beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """Calculate portfolio beta vs a benchmark.

    beta = Cov(portfolio, benchmark) / Var(benchmark)

    Args:
        portfolio_returns:  series of portfolio period returns.
        benchmark_returns: series of benchmark period returns.

    Returns:
        float beta. Positive = moves with market, negative = inverse.
    """
    # Align by index
    common = portfolio_returns.index.intersection(benchmark_returns.index)
    p = portfolio_returns.loc[common]
    b = benchmark_returns.loc[common]

    if len(common) < 2:
        return np.nan

    cov = p.cov(b)
    var = b.var()
    if var == 0:
        return np.nan
    return float(cov / var)


# ── Max Drawdown ───────────────────────────────────────────────────────────────

def calc_max_drawdown(equity_curve: pd.Series) -> dict:
    """Calculate maximum drawdown and its duration.

    Args:
        equity_curve: Series of portfolio NAV / equity values (date index).

    Returns:
        dict with keys:
            - max_drawdown: maximum drawdown as a positive decimal (e.g. 0.20 = 20%)
            - peak_date:     date of the peak before max drawdown
            - trough_date:   date of the trough
            - recovery_date: first date after trough where equity >= peak (NaT if not recovered)
    """
    if len(equity_curve) < 2:
        return {"max_drawdown": 0.0, "peak_date": None, "trough_date": None, "recovery_date": None}

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max  # negative values

    trough_idx = drawdown.idxmin()
    trough_date = trough_idx
    peak_before = equity_curve.loc[:trough_idx].idxmax()
    peak_date = peak_before
    max_dd = float(-drawdown.loc[trough_idx])  # positive

    # Find recovery date
    recovery_date = None
    post_trough = equity_curve.loc[trough_idx:]
    recovered = post_trough[post_trough >= equity_curve.loc[peak_date]]
    if len(recovered) > 0:
        # First date after trough that meets or exceeds peak
        recovery_date = recovered.index[0]

    return {
        "max_drawdown": max_dd,
        "peak_date": peak_date,
        "trough_date": trough_date,
        "recovery_date": recovery_date,
    }


# ── Sharpe Ratio ───────────────────────────────────────────────────────────────

def calc_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate annualised Sharpe ratio.

    Args:
        returns:          series of period returns (e.g. daily returns).
        risk_free_rate:   annual risk-free rate, default 0.
        periods_per_year: number of periods per year, default 252 (daily).

    Returns:
        Annualised Sharpe ratio.
    """
    if len(returns) < 2:
        return np.nan

    excess = returns - risk_free_rate / periods_per_year
    mean_excess = excess.mean()
    std_excess = excess.std(ddof=1)

    if std_excess == 0:
        return np.nan

    return float(mean_excess / std_excess * np.sqrt(periods_per_year))


# ── Volatility ─────────────────────────────────────────────────────────────────

def calc_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
    annualize: bool = True,
) -> float:
    """Calculate return volatility.

    Args:
        returns:          series of period returns.
        periods_per_year: default 252 (daily).
        annualize:        if True, annualise by multiplying by sqrt(periods_per_year).

    Returns:
        Volatility (annualised if annualize=True).
    """
    if len(returns) < 2:
        return np.nan

    vol = float(returns.std(ddof=1))
    if annualize:
        vol *= np.sqrt(periods_per_year)
    return vol