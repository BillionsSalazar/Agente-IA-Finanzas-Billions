"""Modelos de datos tipados devueltos por todos los conectores.

Cada respuesta declara siempre `source` (qué conector la produjo) e
`is_delayed`/`as_of` (frescura del dato), para que el agente Analista
Financiero nunca tenga que adivinar la procedencia de una cifra.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

HealthStatusValue = Literal["ok", "degraded", "not_configured", "error"]


class Quote(BaseModel):
    symbol: str
    price: float
    currency: str = "USD"
    change: float | None = None
    change_percent: float | None = None
    as_of: datetime
    source: str
    is_delayed: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class TimeseriesPoint(BaseModel):
    timestamp: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None


class TimeseriesResult(BaseModel):
    symbol: str
    interval: str
    points: list[TimeseriesPoint]
    source: str
    as_of: datetime
    is_delayed: bool = True


class FundamentalsResult(BaseModel):
    ticker: str
    metrics: dict[str, Any]
    source: str
    as_of: datetime
    is_delayed: bool = True


class EntityMatch(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None
    source: str


class HealthStatus(BaseModel):
    connector: str
    status: HealthStatusValue
    message: str
    missing_env_vars: list[str] = Field(default_factory=list)
    docs_url: str | None = None


class RatingResult(BaseModel):
    entity: str
    rating: str
    outlook: str | None = None
    agency: str
    as_of: datetime
    source: str
    is_delayed: bool = True


class ESGScore(BaseModel):
    entity: str
    score: float | None = None
    rating: str | None = None
    pillar_scores: dict[str, float] = Field(default_factory=dict)
    source: str
    as_of: datetime
    is_delayed: bool = True


class TranscriptResult(BaseModel):
    ticker: str
    event_type: str
    event_date: datetime
    title: str
    summary: str | None = None
    url: str | None = None
    source: str
    is_delayed: bool = True


class PrivateMarketMatch(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None
    source: str


class CorrelationResult(BaseModel):
    symbol_a: str
    symbol_b: str
    window: int
    correlation: float
    source: str
    as_of: datetime
