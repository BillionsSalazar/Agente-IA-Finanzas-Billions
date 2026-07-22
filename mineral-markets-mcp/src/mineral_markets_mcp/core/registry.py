"""Registro de conectores y resolución de la fuente ("source") pedida por cada tool.

Reglas de resolución (ver plan de arquitectura):
  - Si el usuario pide un `source` concreto: debe existir en el registro. Si
    existe pero no está configurado (premium sin credenciales), se informa
    explícitamente — nunca se sustituye en silencio por otra fuente.
  - Si no se pide `source`: se prueban, en orden, los `preferred` (conectores
    premium relevantes para esa tool) y se cae a "open" si ninguno está
    configurado. La fuente efectivamente usada siempre se declara en la
    respuesta.
"""

from __future__ import annotations

from mineral_markets_mcp.connectors.base import BaseConnector
from mineral_markets_mcp.core.exceptions import ConnectorNotConfiguredError, UnknownSourceError
from mineral_markets_mcp.core.models import HealthStatus


class ConnectorRegistry:
    def __init__(self, connectors: dict[str, BaseConnector]) -> None:
        self._connectors = connectors

    def get(self, name: str) -> BaseConnector | None:
        return self._connectors.get(name)

    def all(self) -> dict[str, BaseConnector]:
        return dict(self._connectors)

    def health_check_all(self) -> list[HealthStatus]:
        return [c.health_check() for c in self._connectors.values()]

    def resolve(self, requested: str | None, preferred: tuple[str, ...] = ()) -> BaseConnector:
        """Devuelve el conector a usar, o lanza una excepción explicativa.

        `preferred`: orden de conectores premium a intentar cuando no se pide
        `source` explícito, antes de caer a "open".
        """
        if requested:
            connector = self._connectors.get(requested)
            if connector is None:
                raise UnknownSourceError(requested, sorted(self._connectors))
            status = connector.health_check()
            if status.status not in ("ok", "degraded"):
                raise ConnectorNotConfiguredError(requested, status.missing_env_vars, status.docs_url)
            return connector

        for name in preferred:
            connector = self._connectors.get(name)
            if connector is None:
                continue
            if connector.health_check().status in ("ok", "degraded"):
                return connector

        fallback = self._connectors.get("open")
        if fallback is None:
            raise UnknownSourceError("open", sorted(self._connectors))
        return fallback
