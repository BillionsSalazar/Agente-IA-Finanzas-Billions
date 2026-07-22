"""Conector "open": única fuente 100% funcional sin credenciales.

Decisión de arquitectura: en vez de combinar dos librerías distintas (yfinance
+ scraping CSV de Stooq), todo pasa por `yfinance` (Yahoo Finance, gratuito,
sin API key):
  - Equities/índices/ETFs de materiales y mineras: ticker directo (NEM, FCX,
    ^GSPC, SPY, XLB, GDX...).
  - Metales: se mapean a los tickers públicos de Yahoo Finance equivalentes —
    pares FX spot (`XAUUSD=X`, `XAGUSD=X`) para oro/plata, y futuros COMEX
    (`HG=F`, `PL=F`, `PA=F`) para cobre/platino/paladio.

Commodities sin ticker libre fiable en Yahoo (níquel, litio, aluminio LME,
uranio, tierras raras) NO se inventan: `get_quote`/`get_timeseries` lanzan
`SymbolNotFoundError` explicando que requieren un conector premium (LSEG,
FactSet, S&P Global) con acceso a LME/mercados especializados.

Este conector nunca debe considerarse "real-time" institucional: Yahoo Finance
entrega cotizaciones con delay típico de 15-20 minutos para muchas plazas.
`Quote.is_delayed` se marca siempre en `True` aquí.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import yfinance as yf

from mineral_markets_mcp.connectors.base import BaseConnector
from mineral_markets_mcp.core.cache import cached
from mineral_markets_mcp.core.exceptions import ConnectorAPIError, SymbolNotFoundError
from mineral_markets_mcp.core.logging_config import get_logger
from mineral_markets_mcp.core.models import (
    EntityMatch,
    FundamentalsResult,
    HealthStatus,
    Quote,
    TimeseriesPoint,
    TimeseriesResult,
)
from mineral_markets_mcp.core.ratelimit import RateLimiter
from mineral_markets_mcp.core.retry import with_retry

logger = get_logger(__name__)

# Mapea símbolos "de dominio" de metales a tickers reales de Yahoo Finance.
METAL_TICKER_MAP: dict[str, dict[str, str]] = {
    "XAU": {"yf_symbol": "XAUUSD=X", "label": "Gold Spot (XAU/USD)"},
    "GOLD": {"yf_symbol": "XAUUSD=X", "label": "Gold Spot (XAU/USD)"},
    "XAG": {"yf_symbol": "XAGUSD=X", "label": "Silver Spot (XAG/USD)"},
    "SILVER": {"yf_symbol": "XAGUSD=X", "label": "Silver Spot (XAG/USD)"},
    "HG": {"yf_symbol": "HG=F", "label": "Copper Futures (COMEX)"},
    "COPPER": {"yf_symbol": "HG=F", "label": "Copper Futures (COMEX)"},
    "XPT": {"yf_symbol": "PL=F", "label": "Platinum Futures (NYMEX)"},
    "PLATINUM": {"yf_symbol": "PL=F", "label": "Platinum Futures (NYMEX)"},
    "XPD": {"yf_symbol": "PA=F", "label": "Palladium Futures (NYMEX)"},
    "PALLADIUM": {"yf_symbol": "PA=F", "label": "Palladium Futures (NYMEX)"},
}

# Commodities dentro del alcance pedido sin fuente libre fiable hoy.
UNAVAILABLE_METALS = {"NICKEL", "NI", "LITHIUM", "LI", "ALUMINUM", "ALUMINIUM", "AL", "URANIUM", "U3O8", "REE", "RARE_EARTHS"}

# Catálogo curado para search_entity (sin depender de un buscador externo poco fiable).
ENTITY_CATALOG: list[dict[str, str]] = [
    {"id": "XAU", "name": "Gold Spot", "type": "metal"},
    {"id": "XAG", "name": "Silver Spot", "type": "metal"},
    {"id": "HG", "name": "Copper Futures", "type": "metal"},
    {"id": "XPT", "name": "Platinum Futures", "type": "metal"},
    {"id": "XPD", "name": "Palladium Futures", "type": "metal"},
    {"id": "NEM", "name": "Newmont Corporation", "type": "equity"},
    {"id": "FCX", "name": "Freeport-McMoRan Inc.", "type": "equity"},
    {"id": "BHP", "name": "BHP Group Limited", "type": "equity"},
    {"id": "RIO", "name": "Rio Tinto Group", "type": "equity"},
    {"id": "VALE", "name": "Vale S.A.", "type": "equity"},
    {"id": "GLEN.L", "name": "Glencore plc", "type": "equity"},
    {"id": "AAL.L", "name": "Anglo American plc", "type": "equity"},
    {"id": "^GSPC", "name": "S&P 500 Index", "type": "index"},
    {"id": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "etf"},
    {"id": "XLB", "name": "Materials Select Sector SPDR Fund", "type": "etf"},
    {"id": "GDX", "name": "VanEck Gold Miners ETF", "type": "etf"},
    {"id": "COPX", "name": "Global X Copper Miners ETF", "type": "etf"},
]

DEFAULT_CACHE_TTL = 30.0


class OpenDataConnector(BaseConnector):
    """Fallback gratuito basado en Yahoo Finance (yfinance)."""

    def __init__(
        self,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL,
        rate_limit_per_second: float = 5.0,
        retry_max_attempts: int = 3,
    ) -> None:
        self._cache_ttl = cache_ttl_seconds
        self._rate_limiter = RateLimiter(rate_limit_per_second)
        retryable = with_retry(retry_max_attempts)
        self.get_quote = cached(cache_ttl_seconds)(retryable(self._get_quote_uncached))  # type: ignore[method-assign]
        self.get_timeseries = cached(cache_ttl_seconds)(retryable(self._get_timeseries_uncached))  # type: ignore[method-assign]
        self.get_fundamentals = cached(cache_ttl_seconds)(retryable(self._get_fundamentals_uncached))  # type: ignore[method-assign]

    @property
    def name(self) -> str:
        return "open"

    def _resolve_yf_symbol(self, symbol: str) -> tuple[str, str]:
        """Devuelve (ticker_yfinance, symbol_mostrado_al_usuario)."""
        key = symbol.strip().upper()
        if key in UNAVAILABLE_METALS:
            raise SymbolNotFoundError(
                self.name,
                f"'{symbol}' no tiene fuente abierta/gratuita fiable (requiere LME u otro "
                "proveedor especializado). Configura un conector premium (LSEG, FactSet, "
                "S&P Global) para este commodity.",
            )
        if key in METAL_TICKER_MAP:
            return METAL_TICKER_MAP[key]["yf_symbol"], key
        return symbol, symbol

    def _get_quote_uncached(self, symbol: str) -> Quote:
        yf_symbol, display_symbol = self._resolve_yf_symbol(symbol)
        self._rate_limiter.acquire()
        try:
            ticker = yf.Ticker(yf_symbol)
            fast_info = ticker.fast_info
            price = fast_info.get("lastPrice") if isinstance(fast_info, dict) else fast_info.last_price
            prev_close = (
                fast_info.get("previousClose") if isinstance(fast_info, dict) else fast_info.previous_close
            )
            currency = (fast_info.get("currency") if isinstance(fast_info, dict) else fast_info.currency) or "USD"
        except Exception as exc:  # yfinance no expone excepciones tipadas
            raise ConnectorAPIError(self.name, f"fallo consultando '{yf_symbol}' en Yahoo Finance: {exc}") from exc

        if price is None or (isinstance(price, float) and math.isnan(price)):
            raise SymbolNotFoundError(self.name, f"símbolo '{symbol}' no encontrado en Yahoo Finance")

        change = None
        change_percent = None
        if prev_close:
            change = price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else None

        return Quote(
            symbol=display_symbol,
            price=float(price),
            currency=str(currency),
            change=change,
            change_percent=change_percent,
            as_of=datetime.now(timezone.utc),
            source=self.name,
            is_delayed=True,
            extra={"yfinance_symbol": yf_symbol},
        )

    def _get_timeseries_uncached(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> TimeseriesResult:
        yf_symbol, display_symbol = self._resolve_yf_symbol(symbol)
        self._rate_limiter.acquire()
        try:
            ticker = yf.Ticker(yf_symbol)
            history = ticker.history(start=start, end=end, interval=interval)
        except Exception as exc:
            raise ConnectorAPIError(self.name, f"fallo consultando histórico de '{yf_symbol}': {exc}") from exc

        if history.empty:
            raise SymbolNotFoundError(self.name, f"sin datos históricos para '{symbol}' en el rango pedido")

        points = [
            TimeseriesPoint(
                timestamp=ts.to_pydatetime(),
                open=float(row["Open"]) if "Open" in row and not math.isnan(row["Open"]) else None,
                high=float(row["High"]) if "High" in row and not math.isnan(row["High"]) else None,
                low=float(row["Low"]) if "Low" in row and not math.isnan(row["Low"]) else None,
                close=float(row["Close"]),
                volume=float(row["Volume"]) if "Volume" in row and not math.isnan(row["Volume"]) else None,
            )
            for ts, row in history.iterrows()
        ]

        return TimeseriesResult(
            symbol=display_symbol,
            interval=interval,
            points=points,
            source=self.name,
            as_of=datetime.now(timezone.utc),
            is_delayed=True,
        )

    def _get_fundamentals_uncached(self, ticker: str) -> FundamentalsResult:
        key = ticker.strip().upper()
        if key in METAL_TICKER_MAP or key in UNAVAILABLE_METALS:
            raise SymbolNotFoundError(self.name, f"'{ticker}' es un commodity, no tiene fundamentales de equity")
        self._rate_limiter.acquire()
        try:
            info = yf.Ticker(ticker).get_info()
        except Exception as exc:
            raise ConnectorAPIError(self.name, f"fallo consultando fundamentales de '{ticker}': {exc}") from exc

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            raise SymbolNotFoundError(self.name, f"'{ticker}' no encontrado en Yahoo Finance")

        wanted_keys = (
            "marketCap",
            "trailingPE",
            "forwardPE",
            "priceToBook",
            "dividendYield",
            "returnOnEquity",
            "debtToEquity",
            "profitMargins",
            "revenueGrowth",
            "freeCashflow",
            "totalDebt",
            "totalCash",
            "beta",
            "fiftyTwoWeekHigh",
            "fiftyTwoWeekLow",
            "sector",
            "industry",
        )
        metrics = {k: info[k] for k in wanted_keys if info.get(k) is not None}

        return FundamentalsResult(
            ticker=key,
            metrics=metrics,
            source=self.name,
            as_of=datetime.now(timezone.utc),
            is_delayed=True,
        )

    def search_entity(self, query: str) -> list[EntityMatch]:
        q = query.strip().lower()
        matches = [
            EntityMatch(id=e["id"], name=e["name"], type=e["type"], source=self.name)
            for e in ENTITY_CATALOG
            if q in e["id"].lower() or q in e["name"].lower()
        ]
        return matches

    def health_check(self) -> HealthStatus:
        return HealthStatus(
            connector=self.name,
            status="ok",
            message=(
                "Fuente abierta/gratuita (Yahoo Finance vía yfinance). Datos delayed "
                "(~15-20 min), no aptos para trading institucional. Cobertura de metales "
                "limitada a oro, plata, cobre, platino y paladio; níquel/litio/aluminio/"
                "uranio/tierras raras requieren un conector premium."
            ),
            missing_env_vars=[],
            docs_url="https://github.com/ranaroussi/yfinance",
        )
