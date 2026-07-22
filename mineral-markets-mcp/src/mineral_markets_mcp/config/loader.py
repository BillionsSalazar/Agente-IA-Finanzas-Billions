"""Carga y valida `config.yaml`: universo de activos, umbrales de señales y frecuencia de polling.

El universo se declara por categoría (metales, equities, índices, macro) y se
"aplana" a una lista de `AssetSpec` que alimenta el catálogo `assets` en
SQLite. Los símbolos de metales se resuelven aquí a su ticker real de Yahoo
Finance (mismo mapeo que usa `OpenDataConnector`) solo para dejarlo persistido
en el catálogo — la resolución efectiva al pedir datos la sigue haciendo el
conector.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from mineral_markets_mcp.connectors.open_data import METAL_TICKER_MAP

AssetClass = Literal["metal", "equity", "index", "macro"]


class AssetEntry(BaseModel):
    symbol: str
    label: str | None = None


class UniverseConfig(BaseModel):
    metals: list[AssetEntry] = Field(default_factory=list)
    equities: list[AssetEntry] = Field(default_factory=list)
    custom_tickers: list[str] = Field(default_factory=list)
    indices: list[AssetEntry] = Field(default_factory=list)
    macro: list[AssetEntry] = Field(default_factory=list)


class PollingConfig(BaseModel):
    interval_minutes: float = 5.0
    market_hours_only: bool = True
    timezone: str = "America/New_York"


class RSIConfig(BaseModel):
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0


class MACDConfig(BaseModel):
    fast: int = 12
    slow: int = 26
    signal: int = 9


class SMABreakoutConfig(BaseModel):
    period: int = 50


class SignalsConfig(BaseModel):
    rsi: RSIConfig = Field(default_factory=RSIConfig)
    macd: MACDConfig = Field(default_factory=MACDConfig)
    sma_breakout: SMABreakoutConfig = Field(default_factory=SMABreakoutConfig)
    intraday_move_pct: float = 3.0
    gsr_shift_pct: float = 2.0


class AlertsConfig(BaseModel):
    log_level_on_signal: str = "WARNING"
    notify_hook: str | None = None


class MonitorConfig(BaseModel):
    polling: PollingConfig = Field(default_factory=PollingConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)


class AssetSpec(BaseModel):
    """Activo ya resuelto: símbolo de dominio + ticker real de Yahoo Finance."""

    symbol: str
    display_name: str
    asset_class: AssetClass
    yf_symbol: str
    is_custom: bool = False


def load_config(path: str | Path = "config.yaml") -> MonitorConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return MonitorConfig.model_validate(raw)


def _yf_symbol_for_metal(symbol: str) -> str:
    key = symbol.strip().upper()
    mapped = METAL_TICKER_MAP.get(key)
    return mapped["yf_symbol"] if mapped else symbol


def flatten_universe(universe: UniverseConfig) -> list[AssetSpec]:
    """Aplana las categorías del config en una lista única de `AssetSpec`."""
    specs: list[AssetSpec] = []

    for entry in universe.metals:
        specs.append(
            AssetSpec(
                symbol=entry.symbol,
                display_name=entry.label or entry.symbol,
                asset_class="metal",
                yf_symbol=_yf_symbol_for_metal(entry.symbol),
            )
        )
    for entry in universe.equities:
        specs.append(
            AssetSpec(
                symbol=entry.symbol,
                display_name=entry.label or entry.symbol,
                asset_class="equity",
                yf_symbol=entry.symbol,
            )
        )
    for ticker in universe.custom_tickers:
        specs.append(
            AssetSpec(
                symbol=ticker,
                display_name=ticker,
                asset_class="equity",
                yf_symbol=ticker,
                is_custom=True,
            )
        )
    for entry in universe.indices:
        specs.append(
            AssetSpec(
                symbol=entry.symbol,
                display_name=entry.label or entry.symbol,
                asset_class="index",
                yf_symbol=entry.symbol,
            )
        )
    for entry in universe.macro:
        specs.append(
            AssetSpec(
                symbol=entry.symbol,
                display_name=entry.label or entry.symbol,
                asset_class="macro",
                yf_symbol=entry.symbol,
            )
        )
    return specs
