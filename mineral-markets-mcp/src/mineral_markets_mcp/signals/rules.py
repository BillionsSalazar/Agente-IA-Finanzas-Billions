"""Reglas de señales del MVP: RSI sobreventa/sobrecompra, ruptura de SMA y
movimiento intradía. Cada regla es una función pura `RuleContext -> Signal | None`.

MACD y el cambio del Gold/Silver Ratio quedan para la siguiente iteración (ver
plan de arquitectura) — sus valores ya se calculan y persisten en `snapshots`
pero todavía no disparan señales.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel

from mineral_markets_mcp.config.loader import SignalsConfig

Direction = Literal["bullish", "bearish", "neutral"]


class Signal(BaseModel):
    symbol: str
    rule_name: str
    direction: Direction
    value: float | None
    threshold: float | None
    message: str


@dataclass
class RuleContext:
    symbol: str
    price: float
    change_percent: float | None
    indicators: dict[str, Any]
    closes: pd.Series
    config: SignalsConfig


def rsi_rule(ctx: RuleContext) -> Signal | None:
    rsi_value = ctx.indicators.get("rsi_14")
    if rsi_value is None:
        return None
    cfg = ctx.config.rsi
    if rsi_value < cfg.oversold:
        return Signal(
            symbol=ctx.symbol,
            rule_name="rsi_oversold",
            direction="bullish",
            value=rsi_value,
            threshold=cfg.oversold,
            message=f"{ctx.symbol}: RSI({cfg.period}) en {rsi_value:.1f}, bajo el umbral de sobreventa ({cfg.oversold}).",
        )
    if rsi_value > cfg.overbought:
        return Signal(
            symbol=ctx.symbol,
            rule_name="rsi_overbought",
            direction="bearish",
            value=rsi_value,
            threshold=cfg.overbought,
            message=f"{ctx.symbol}: RSI({cfg.period}) en {rsi_value:.1f}, sobre el umbral de sobrecompra ({cfg.overbought}).",
        )
    return None


def intraday_move_rule(ctx: RuleContext) -> Signal | None:
    if ctx.change_percent is None:
        return None
    threshold = ctx.config.intraday_move_pct
    if abs(ctx.change_percent) < threshold:
        return None
    direction: Direction = "bullish" if ctx.change_percent > 0 else "bearish"
    return Signal(
        symbol=ctx.symbol,
        rule_name="intraday_move",
        direction=direction,
        value=ctx.change_percent,
        threshold=threshold,
        message=f"{ctx.symbol}: movimiento de {ctx.change_percent:+.2f}% frente al cierre anterior (umbral {threshold}%).",
    )


def sma_breakout_rule(ctx: RuleContext) -> Signal | None:
    sma_series: pd.Series | None = ctx.indicators.get("sma_breakout_series")
    if sma_series is None or len(sma_series) < 2 or len(ctx.closes) < 2:
        return None
    today_sma, prev_sma = sma_series.iloc[-1], sma_series.iloc[-2]
    today_close, prev_close = ctx.closes.iloc[-1], ctx.closes.iloc[-2]
    if pd.isna(today_sma) or pd.isna(prev_sma):
        return None

    period = ctx.config.sma_breakout.period
    if prev_close <= prev_sma and today_close > today_sma:
        return Signal(
            symbol=ctx.symbol,
            rule_name="sma_breakout_up",
            direction="bullish",
            value=float(today_close),
            threshold=float(today_sma),
            message=f"{ctx.symbol}: precio ({today_close:.2f}) rompió al alza la SMA({period}) ({today_sma:.2f}).",
        )
    if prev_close >= prev_sma and today_close < today_sma:
        return Signal(
            symbol=ctx.symbol,
            rule_name="sma_breakout_down",
            direction="bearish",
            value=float(today_close),
            threshold=float(today_sma),
            message=f"{ctx.symbol}: precio ({today_close:.2f}) rompió a la baja la SMA({period}) ({today_sma:.2f}).",
        )
    return None


RULES: list[Callable[[RuleContext], Signal | None]] = [rsi_rule, intraday_move_rule, sma_breakout_rule]
