"""Implementaciones de las tools MCP de mercado.

Cada función pública devuelve un `dict` serializable (nunca lanza excepciones
hacia el llamador MCP): los errores de conector se capturan aquí y se
convierten en un campo `error` explícito, para que el agente Analista
Financiero siempre pueda distinguir "dato real" de "fuente no disponible".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mineral_markets_mcp.core.exceptions import ConnectorError
from mineral_markets_mcp.core.logging_config import get_logger
from mineral_markets_mcp.core.registry import ConnectorRegistry

logger = get_logger(__name__)

# Watchlist por defecto del panel consolidado — alineada con el alcance pedido:
# metales, mineras principales e índice de referencia.
DEFAULT_METALS = ["XAU", "XAG", "HG"]
DEFAULT_EQUITIES = ["NEM", "FCX", "BHP", "RIO", "VALE"]
DEFAULT_INDICES = ["^GSPC"]

# Conectores premium candidatos por tipo de dato, en orden de preferencia,
# usados cuando la tool no recibe un `source` explícito. Hoy ninguno está
# registrado todavía (se añaden en la fase de conectores premium) — el
# registro cae automáticamente a "open".
PREFERRED_EQUITY_SOURCES = ("factset", "sp_global", "lseg")
PREFERRED_METAL_SOURCES = ("factset", "lseg")
PREFERRED_FUNDAMENTALS_SOURCES = ("daloopa", "sp_global", "morningstar", "factset")


def _error_payload(exc: ConnectorError) -> dict[str, Any]:
    payload: dict[str, Any] = {"connector": exc.connector, "message": exc.message}
    missing = getattr(exc, "missing_env_vars", None)
    if missing:
        payload["missing_env_vars"] = missing
    docs_url = getattr(exc, "docs_url", None)
    if docs_url:
        payload["docs_url"] = docs_url
    return payload


def _safe_quote(
    registry: ConnectorRegistry, symbol: str, source: str | None, preferred: tuple[str, ...]
) -> dict[str, Any]:
    try:
        connector = registry.resolve(source, preferred)
        quote = connector.get_quote(symbol)
        return {"ok": True, "data": quote.model_dump(mode="json")}
    except ConnectorError as exc:
        logger.warning("quote fallida", extra={"symbol": symbol, "connector": getattr(exc, "connector", source)})
        return {"ok": False, "symbol": symbol, "error": _error_payload(exc)}


def get_metal_price(registry: ConnectorRegistry, symbol: str, source: str | None = None) -> dict[str, Any]:
    return _safe_quote(registry, symbol, source, PREFERRED_METAL_SOURCES)


def get_equity_quote(registry: ConnectorRegistry, ticker: str, source: str | None = None) -> dict[str, Any]:
    return _safe_quote(registry, ticker, source, PREFERRED_EQUITY_SOURCES)


def build_market_snapshot(registry: ConnectorRegistry) -> dict[str, Any]:
    metals = {s: _safe_quote(registry, s, None, PREFERRED_METAL_SOURCES) for s in DEFAULT_METALS}
    equities = {s: _safe_quote(registry, s, None, PREFERRED_EQUITY_SOURCES) for s in DEFAULT_EQUITIES}
    indices = {s: _safe_quote(registry, s, None, PREFERRED_EQUITY_SOURCES) for s in DEFAULT_INDICES}

    ratio_result = _gold_silver_ratio_from_quotes(metals.get("XAU"), metals.get("XAG"))

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "metals": metals,
        "equities": equities,
        "indices": indices,
        "gold_silver_ratio": ratio_result,
        "note": (
            "Cada entrada declara su propia fuente ('source') y si el dato es delayed. "
            "Los símbolos sin fuente configurada aparecen con 'ok': false y el detalle del error."
        ),
    }


def _gold_silver_ratio_from_quotes(gold: dict[str, Any] | None, silver: dict[str, Any] | None) -> dict[str, Any]:
    if not gold or not gold.get("ok") or not silver or not silver.get("ok"):
        return {"ok": False, "error": "faltan cotizaciones de oro y/o plata para calcular el ratio"}
    gold_price = gold["data"]["price"]
    silver_price = silver["data"]["price"]
    if not silver_price:
        return {"ok": False, "error": "precio de plata inválido (0)"}
    return {
        "ok": True,
        "data": {
            "ratio": gold_price / silver_price,
            "gold_price": gold_price,
            "silver_price": silver_price,
            "gold_source": gold["data"]["source"],
            "silver_source": silver["data"]["source"],
            "as_of": datetime.now(timezone.utc).isoformat(),
        },
    }


def get_gold_silver_ratio(registry: ConnectorRegistry) -> dict[str, Any]:
    gold = _safe_quote(registry, "XAU", None, PREFERRED_METAL_SOURCES)
    silver = _safe_quote(registry, "XAG", None, PREFERRED_METAL_SOURCES)
    return _gold_silver_ratio_from_quotes(gold, silver)
