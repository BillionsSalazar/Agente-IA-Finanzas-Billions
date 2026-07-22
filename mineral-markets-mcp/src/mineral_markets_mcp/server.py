"""Entrypoint del servidor MCP "mineral-markets-mcp".

Uso:
    python -m mineral_markets_mcp.server                 # stdio (por defecto)
    python -m mineral_markets_mcp.server --transport sse --port 8000
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from mineral_markets_mcp.connectors.base import BaseConnector
from mineral_markets_mcp.connectors.open_data import OpenDataConnector
from mineral_markets_mcp.core.logging_config import configure_logging, get_logger
from mineral_markets_mcp.core.registry import ConnectorRegistry
from mineral_markets_mcp.settings import Settings, get_settings
from mineral_markets_mcp.tools import market_tools

logger = get_logger(__name__)


def build_registry(settings: Settings) -> ConnectorRegistry:
    """Instancia los conectores disponibles.

    Hoy solo "open" (Yahoo Finance, sin credenciales) está implementado
    end-to-end. Los 11 conectores premium (FactSet, S&P Global, LSEG, MSCI,
    PitchBook, Morningstar, Moody's, Aiera, Daloopa, Chronograph, Egnyte) se
    añaden aquí en una fase posterior, cada uno degradando con elegancia si
    faltan credenciales (ver `connectors/base.py`).
    """
    connectors: dict[str, BaseConnector] = {
        "open": OpenDataConnector(
            cache_ttl_seconds=settings.cache_ttl_seconds,
            rate_limit_per_second=settings.rate_limit_per_second,
            retry_max_attempts=settings.retry_max_attempts,
        ),
    }
    return ConnectorRegistry(connectors)


def create_server() -> FastMCP:
    settings = get_settings()
    configure_logging(settings.log_level)
    registry = build_registry(settings)

    mcp = FastMCP("mineral-markets-mcp")

    @mcp.tool()
    def get_market_snapshot() -> dict:
        """Panel consolidado: metales, mineras principales, índice de referencia y Gold/Silver Ratio."""
        return market_tools.build_market_snapshot(registry)

    logger.info("servidor inicializado", extra={"connector": "registry"})
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="mineral-markets-mcp — servidor MCP del Analista Financiero")
    parser.add_argument(
        "--transport", choices=["stdio", "sse", "streamable-http"], default="stdio", help="Transporte MCP a usar"
    )
    args = parser.parse_args()

    server = create_server()
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
