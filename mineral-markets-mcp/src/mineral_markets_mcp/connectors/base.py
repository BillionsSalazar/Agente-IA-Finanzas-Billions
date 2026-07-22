"""Interfaz común que implementa cada proveedor de datos de mercado."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from mineral_markets_mcp.core.models import (
    EntityMatch,
    FundamentalsResult,
    HealthStatus,
    Quote,
    TimeseriesResult,
)


class BaseConnector(ABC):
    """Contrato que deben cumplir todos los conectores (premium u "open").

    Los conectores premium deben lanzar `ConnectorNotConfiguredError` desde
    cualquier método de datos si faltan credenciales, y reflejarlo en
    `health_check()`. Ningún conector debe lanzar una excepción sin
    controlar hacia la capa de tools MCP.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador corto y estable del conector (p. ej. "factset")."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Precio/cotización actual (o la más reciente disponible) de `symbol`."""

    @abstractmethod
    def get_timeseries(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> TimeseriesResult:
        """Serie histórica de `symbol` entre `start` y `end` al `interval` dado."""

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> FundamentalsResult:
        """Ratios/métricas fundamentales de `ticker`."""

    @abstractmethod
    def search_entity(self, query: str) -> list[EntityMatch]:
        """Busca entidades (tickers, compañías, commodities) que coincidan con `query`."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Estado del conector: configurado/ok, degradado, no configurado o error."""
