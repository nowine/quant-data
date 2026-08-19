"""Technical indicator calculations on OHLCV price data.

This module provides pure computational functions with no API dependencies.
All indicators accept a DataFrame with standard OHLCV columns and return
either a Series or DataFrame of indicator values.

Columns expected in input DataFrame:
    - date (or index): date/datetime
    - open: float
    - high: float
    - low: float
    - close: float
    - volume: float (optional for some indicators)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── MA / Moving Average ────────────────────────────────────────────────────────

def calc_ma(data: pd.DataFrame, periods: list[int] | tuple[int, ...] = (20, 60)) -> pd.DataFrame:
    """Calculate moving averages for given periods.

    Args:
        data: DataFrame with 'close' column.
        periods: tuple of periods, default (20, 60).

    Returns:
        DataFrame with columns MA_{period} for each period.
    """
    close = data["close"]
    result = pd.DataFrame(index=data.index)
    for p in periods:
        result[f"MA{p}"] = close.rolling(window=p, min_periods=1).mean()
    return result


def calc_ma_deviation(data: pd.DataFrame, periods: list[int] | tuple[int, ...] = (20, 60)) -> pd.DataFrame:
    """Calculate how far price deviates from its moving average.

    Args:
        data: DataFrame with 'close' column.
        periods: tuple of periods, default (20, 60).

    Returns:
        DataFrame with columns DEV_{period} = (close - MA{period}) / MA{period} * 100 (%)
    """
    close = data["close"]
    result = pd.DataFrame(index=data.index)
    for p in periods:
        ma = close.rolling(window=p, min_periods=1).mean()
        result[f"DEV{p}"] = (close - ma) / ma * 100
    return result


# ── ATR / Average True Range ───────────────────────────────────────────────────

def calc_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range.

    Args:
        data: DataFrame with high, low, close columns.
        period: lookback period, default 14.

    Returns:
        Series with ATR values.
    """
    high = data["high"]
    low = data["low"]
    close = data["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


# ── RSI ────────────────────────────────────────────────────────────────────────

def calc_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index.

    Args:
        data: DataFrame with 'close' column.
        period: RSI period, default 14.

    Returns:
        Series with RSI values (0-100).
    """
    close = data["close"]
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ── Volume Ratio (量比) ─────────────────────────────────────────────────────────

def calc_volume_ratio(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate volume ratio — current volume vs N-period average.

    Args:
        data: DataFrame with 'volume' column.
        period: lookback for average volume, default 20.

    Returns:
        Series with volume ratio values.
    """
    vol = data["volume"]
    avg_vol = vol.rolling(window=period, min_periods=period).mean()
    vr = vol / avg_vol
    return vr


# ── Bollinger Bands ────────────────────────────────────────────────────────────

def calc_bollinger(data: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Calculate Bollinger Bands.

    Args:
        data: DataFrame with 'close' column.
        period: moving average period, default 20.
        num_std: number of standard deviations, default 2.0.

    Returns:
        DataFrame with BB_UPPER, BB_MIDDLE, BB_LOWER columns.
    """
    close = data["close"]
    mid = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    return pd.DataFrame(
        {
            "BB_UPPER": mid + num_std * std,
            "BB_MIDDLE": mid,
            "BB_LOWER": mid - num_std * std,
        },
        index=data.index,
    )


# ── MACD ───────────────────────────────────────────────────────────────────────

def calc_macd(
    data: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Calculate MACD (Moving Average Convergence Divergence).

    Args:
        data: DataFrame with 'close' column.
        fast: fast EMA period, default 12.
        slow: slow EMA period, default 26.
        signal: signal line EMA period, default 9.

    Returns:
        DataFrame with DIF, DEA, MACD (histogram = DIF - DEA).
    """
    close = data["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = dif - dea

    return pd.DataFrame(
        {"DIF": dif, "DEA": dea, "MACD": macd},
        index=data.index,
    )


# ── Premium Rate (溢价率) ───────────────────────────────────────────────────────

def calc_premium_rate(snapshot_price: float | pd.Series, nav: float | pd.Series) -> float | pd.Series:
    """Calculate ETF premium/discount rate.

    Args:
        snapshot_price: real-time market price (from snapshot).
        nav: net asset value (from akshare_fund_client nav_history).

    Returns:
        premium rate = snapshot_price / nav - 1 (as decimal, e.g. 0.012 = 1.2%).
    """
    return snapshot_price / nav - 1