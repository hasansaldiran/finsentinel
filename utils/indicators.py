"""
Teknik indikatör hesaplamaları — pandas/numpy tabanlı, harici bağımlılık yok.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder smoothing)."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).rename("RSI")


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    fast_ema   = ema(series, fast)
    slow_ema   = ema(series, slow)
    macd_line  = (fast_ema - slow_ema).rename("MACD")
    signal_line = ema(macd_line, signal_period).rename("Signal")
    histogram  = (macd_line - signal_line).rename("Hist")
    return macd_line, signal_line, histogram


def bollinger(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower) Bollinger Bands."""
    middle = series.rolling(period).mean()
    std    = series.rolling(period).std()
    return (
        (middle + num_std * std).rename("BB_upper"),
        middle.rename("BB_mid"),
        (middle - num_std * std).rename("BB_lower"),
    )


def vwap(df: pd.DataFrame) -> pd.Series:
    """
    Typical-price VWAP over the full series.
    Uses Volume column if available; falls back to uniform weights.
    """
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    vol     = df["Volume"].fillna(0) if "Volume" in df.columns else pd.Series(1.0, index=df.index)
    cum_vol    = vol.cumsum()
    cum_tp_vol = (typical * vol).cumsum()
    return (cum_tp_vol / cum_vol.replace(0, np.nan)).rename("VWAP")


def supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[pd.Series, pd.Series]:
    """
    Supertrend indicator (vectorized with single forward pass).
    Accepts both lowercase (yfinance) and uppercase column names.

    Returns:
        (st_line, direction)
        st_line   — price level of the Supertrend band currently active
        direction — +1 = bullish (price above band), -1 = bearish
    """
    # Accept both lower- and upper-case column names
    _c = {col.lower(): col for col in df.columns}
    high  = df[_c.get("high",  "High")]
    low   = df[_c.get("low",   "Low")]
    close = df[_c.get("close", "Close")]

    # ATR (Wilder EMA)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()

    hl2          = (high + low) / 2
    basic_upper  = (hl2 + multiplier * atr).values.copy()
    basic_lower  = (hl2 - multiplier * atr).values.copy()
    close_arr    = close.values

    n        = len(close_arr)
    upper    = basic_upper.copy()
    lower    = basic_lower.copy()
    st_arr   = np.full(n, np.nan)
    dir_arr  = np.zeros(n, dtype=float)

    for i in range(1, n):
        # Tighten upper band (never widen while in downtrend)
        upper[i] = upper[i] if upper[i] < upper[i - 1] or close_arr[i - 1] > upper[i - 1] else upper[i - 1]
        # Tighten lower band (never widen while in uptrend)
        lower[i] = lower[i] if lower[i] > lower[i - 1] or close_arr[i - 1] < lower[i - 1] else lower[i - 1]

        prev_st = st_arr[i - 1]
        if np.isnan(prev_st) or prev_st == upper[i - 1]:
            # Was bearish (or uninitialised)
            if close_arr[i] > upper[i]:
                st_arr[i], dir_arr[i] = lower[i],  1.0
            else:
                st_arr[i], dir_arr[i] = upper[i], -1.0
        else:
            # Was bullish (prev_st == lower[i-1])
            if close_arr[i] < lower[i]:
                st_arr[i], dir_arr[i] = upper[i], -1.0
            else:
                st_arr[i], dir_arr[i] = lower[i],  1.0

    return (
        pd.Series(st_arr,  index=close.index, name="Supertrend"),
        pd.Series(dir_arr, index=close.index, name="ST_Dir"),
    )
