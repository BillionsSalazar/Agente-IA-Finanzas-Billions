"""Indicadores técnicos: SMA/EMA, RSI, MACD, VWAP y bandas de Bollinger.

Implementados a mano con pandas/numpy en vez de `pandas-ta`: la librería tiene
un bug conocido de incompatibilidad con numpy>=2.0 (usa `np.NaN`, removido en
numpy 2.x) que rompe la instalación en entornos recientes. El cálculo directo
es poco código y evita esa fragilidad — ver README para más detalle.

Todos los indicadores se calculan sobre velas **diarias** (`interval="1d"` de
`OpenDataConnector.get_timeseries`), no intradía: `yfinance` gratuito no
garantiza suficiente historial intradía para ventanas como SMA50. El VWAP
calculado aquí es por lo tanto una media ponderada por volumen sobre la
ventana diaria configurada, no el VWAP intradía que resetea cada sesión.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mineral_markets_mcp.config.loader import SignalsConfig
from mineral_markets_mcp.core.models import TimeseriesResult

MIN_POINTS_FOR_INDICATORS = 2


def sma(closes: pd.Series, period: int) -> pd.Series:
    return closes.rolling(window=period, min_periods=period).mean()


def ema(closes: pd.Series, period: int) -> pd.Series:
    return closes.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder (media móvil exponencial de ganancias/pérdidas)."""
    delta = closes.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100.0 - (100.0 / (1.0 + rs))
    return result.where(avg_loss != 0.0, 100.0)


def macd(
    closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(closes, fast) - ema(closes, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def vwap(highs: pd.Series, lows: pd.Series, closes: pd.Series, volumes: pd.Series, period: int = 20) -> pd.Series:
    typical_price = (highs + lows + closes) / 3.0
    pv = typical_price * volumes
    return pv.rolling(window=period, min_periods=period).sum() / volumes.rolling(
        window=period, min_periods=period
    ).sum().replace(0.0, np.nan)


def bollinger_bands(closes: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series]:
    mid = sma(closes, period)
    std = closes.rolling(window=period, min_periods=period).std()
    return mid + num_std * std, mid - num_std * std


def _last_or_none(series: pd.Series) -> float | None:
    if series.empty:
        return None
    value = series.iloc[-1]
    return None if pd.isna(value) else float(value)


def compute_indicators(history: TimeseriesResult, signals_config: SignalsConfig) -> dict[str, Any]:
    """Calcula todos los indicadores sobre un histórico diario y devuelve el
    último valor de cada uno, listo para persistir en `snapshots`.
    """
    if len(history.points) < MIN_POINTS_FOR_INDICATORS:
        return {
            "rsi_14": None,
            "macd": None,
            "macd_signal": None,
            "macd_hist": None,
            "sma_20": None,
            "sma_50": None,
            "ema_20": None,
            "vwap": None,
            "bb_upper": None,
            "bb_lower": None,
        }

    closes = pd.Series([p.close for p in history.points], dtype=float)
    highs = pd.Series([p.high if p.high is not None else p.close for p in history.points], dtype=float)
    lows = pd.Series([p.low if p.low is not None else p.close for p in history.points], dtype=float)
    volumes = pd.Series([p.volume or 0.0 for p in history.points], dtype=float)

    rsi_series = rsi(closes, signals_config.rsi.period)
    macd_line, signal_line, hist_line = macd(
        closes, signals_config.macd.fast, signals_config.macd.slow, signals_config.macd.signal
    )
    bb_upper, bb_lower = bollinger_bands(closes, period=20)

    return {
        "rsi_14": _last_or_none(rsi_series),
        "macd": _last_or_none(macd_line),
        "macd_signal": _last_or_none(signal_line),
        "macd_hist": _last_or_none(hist_line),
        "sma_20": _last_or_none(sma(closes, 20)),
        "sma_50": _last_or_none(sma(closes, 50)),
        "ema_20": _last_or_none(ema(closes, 20)),
        "vwap": _last_or_none(vwap(highs, lows, closes, volumes, period=20)),
        "bb_upper": _last_or_none(bb_upper),
        "bb_lower": _last_or_none(bb_lower),
        # serie completa de SMA de ruptura configurable, para que signals/engine.py
        # compare el precio de hoy vs. ayer contra la media sin recalcularla.
        "sma_breakout_series": sma(closes, signals_config.sma_breakout.period),
    }
