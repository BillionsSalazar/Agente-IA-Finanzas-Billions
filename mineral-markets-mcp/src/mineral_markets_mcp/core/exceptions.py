"""Excepciones del dominio. Nunca deben escapar hasta el cliente MCP sin
convertirse antes en una respuesta explícita — ver tools/market_tools.py."""

from __future__ import annotations


class ConnectorError(Exception):
    """Error base de cualquier conector."""

    def __init__(self, connector: str, message: str) -> None:
        self.connector = connector
        self.message = message
        super().__init__(f"[{connector}] {message}")


class ConnectorNotConfiguredError(ConnectorError):
    """El conector no tiene credenciales/licencia configuradas.

    No es un fallo transitorio: indica que faltan variables de entorno.
    La capa de tools debe capturar esto y responder de forma explícita en
    lugar de dejar que la excepción se propague.
    """

    def __init__(self, connector: str, missing_env_vars: list[str], docs_url: str | None = None) -> None:
        self.missing_env_vars = missing_env_vars
        self.docs_url = docs_url
        vars_str = ", ".join(missing_env_vars) if missing_env_vars else "credenciales"
        message = f"conector no configurado — faltan: {vars_str}"
        if docs_url:
            message += f" (docs: {docs_url})"
        super().__init__(connector, message)


class ConnectorAPIError(ConnectorError):
    """La API subyacente respondió con error tras agotar los reintentos."""


class SymbolNotFoundError(ConnectorError):
    """El símbolo/entidad solicitado no fue encontrado por este conector."""


class UnknownSourceError(ConnectorError):
    """Se pidió un `source` que no existe en el registro de conectores."""

    def __init__(self, requested: str, known_sources: list[str]) -> None:
        self.requested = requested
        self.known_sources = known_sources
        super().__init__(requested, f"fuente desconocida — disponibles: {', '.join(known_sources)}")
