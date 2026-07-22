"""Entrypoint del agente de monitoreo (loop de consola, no MCP).

Uso:
    python -m mineral_markets_mcp.monitor                 # loop continuo
    python -m mineral_markets_mcp.monitor --once           # un solo ciclo (para probar)
    python -m mineral_markets_mcp.monitor --config otro.yaml --db otro.db

Comparte `connectors/` y `core/` con el servidor MCP (`server.py`) — este
entrypoint añade persistencia SQLite, indicadores, señales y un dashboard de
consola en vivo sobre la misma capa de datos.
"""

from __future__ import annotations

import argparse
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from mineral_markets_mcp.analysis.indicators import compute_indicators
from mineral_markets_mcp.config.loader import (
    AssetSpec,
    MonitorConfig,
    PollingConfig,
    SignalsConfig,
    flatten_universe,
    load_config,
)
from mineral_markets_mcp.connectors.open_data import OpenDataConnector
from mineral_markets_mcp.core.exceptions import ConnectorError
from mineral_markets_mcp.core.logging_config import configure_logging, get_logger
from mineral_markets_mcp.db.sqlite_store import SQLiteStore
from mineral_markets_mcp.settings import get_settings
from mineral_markets_mcp.signals.engine import SignalEngine
from mineral_markets_mcp.ui.dashboard import AssetRow, Dashboard

logger = get_logger(__name__)

# ~130 velas diarias de mercado en 200 días de calendario — margen suficiente
# sobre SMA(50)/MACD(26,9), incluso descontando fines de semana y feriados.
HISTORY_LOOKBACK_DAYS = 200


def _is_market_hours(polling: PollingConfig, now_utc: datetime) -> bool:
    if not polling.market_hours_only:
        return True
    local = now_utc.astimezone(ZoneInfo(polling.timezone))
    if local.weekday() >= 5:
        return False
    open_time = local.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = local.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= local <= close_time


def _empty_indicators() -> dict:
    return {
        "rsi_14": None, "macd": None, "macd_signal": None, "macd_hist": None,
        "sma_20": None, "sma_50": None, "ema_20": None, "vwap": None,
        "bb_upper": None, "bb_lower": None, "sma_breakout_series": None,
    }


def process_asset(
    connector: OpenDataConnector,
    store: SQLiteStore,
    engine: SignalEngine,
    spec: AssetSpec,
    signals_config: SignalsConfig,
) -> AssetRow:
    try:
        quote = connector.get_quote(spec.symbol)
    except ConnectorError as exc:
        logger.warning("cotización falló", extra={"symbol": spec.symbol})
        return AssetRow(
            symbol=spec.symbol, display_name=spec.display_name, asset_class=spec.asset_class,
            price=None, currency="USD", change_percent=None, rsi_14=None, is_delayed=True,
            error=exc.message,
        )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=HISTORY_LOOKBACK_DAYS)
    try:
        history = connector.get_timeseries(spec.symbol, start=start, end=end, interval="1d")
    except ConnectorError as exc:
        logger.warning("histórico falló", extra={"symbol": spec.symbol})
        history = None

    store.insert_price(
        symbol=spec.symbol, ts=quote.as_of, interval="1d", close=quote.price,
        source=quote.source, is_delayed=quote.is_delayed,
    )

    closes = pd.Series(dtype=float)
    indicators = _empty_indicators()
    if history is not None:
        for point in history.points:
            store.insert_price(
                symbol=spec.symbol, ts=point.timestamp, interval="1d", close=point.close,
                open_=point.open, high=point.high, low=point.low, volume=point.volume,
                source=history.source, is_delayed=history.is_delayed,
            )
        closes = pd.Series([p.close for p in history.points], dtype=float)
        indicators = compute_indicators(history, signals_config)

    snapshot_payload = {**indicators, "price": quote.price, "change_percent": quote.change_percent}
    snapshot_id = store.insert_snapshot(
        symbol=spec.symbol, indicators=snapshot_payload, source=quote.source, is_delayed=quote.is_delayed
    )

    active_signals = engine.evaluate(
        symbol=spec.symbol,
        price=quote.price,
        change_percent=quote.change_percent,
        indicators=snapshot_payload,
        closes=closes,
        snapshot_id=snapshot_id,
    )

    return AssetRow(
        symbol=spec.symbol,
        display_name=spec.display_name,
        asset_class=spec.asset_class,
        price=quote.price,
        currency=quote.currency,
        change_percent=quote.change_percent,
        rsi_14=indicators.get("rsi_14"),
        is_delayed=quote.is_delayed,
        signals=active_signals,
    )


def run_cycle(
    config: MonitorConfig,
    connector: OpenDataConnector,
    store: SQLiteStore,
    engine: SignalEngine,
    specs: list[AssetSpec],
    dashboard: Dashboard | None,
) -> None:
    rows = [process_asset(connector, store, engine, spec, config.signals) for spec in specs]
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if dashboard is not None:
        dashboard.update(rows, as_of)
    else:
        for row in rows:
            logger.info(
                "snapshot", extra={"symbol": row.symbol, "source": "open"}
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de monitoreo de mercados (metales, mineras, índices, macro)")
    parser.add_argument("--config", default="config.yaml", help="Ruta a config.yaml")
    parser.add_argument("--db", default="market_monitor.db", help="Ruta al archivo SQLite")
    parser.add_argument("--once", action="store_true", help="Corre un solo ciclo y sale (no entra al loop)")
    parser.add_argument("--no-dashboard", action="store_true", help="Desactiva la tabla en vivo (solo logs)")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    config = load_config(args.config)
    specs = flatten_universe(config.universe)

    store = SQLiteStore(args.db)
    store.sync_assets(specs)

    connector = OpenDataConnector(
        cache_ttl_seconds=settings.cache_ttl_seconds,
        rate_limit_per_second=settings.rate_limit_per_second,
        retry_max_attempts=settings.retry_max_attempts,
    )
    engine = SignalEngine(config.signals, store)

    logger.info("agente de monitoreo iniciado", extra={"operation": "startup"})

    dashboard_ctx = nullcontext(None) if args.no_dashboard else Dashboard()
    try:
        with dashboard_ctx as dashboard:
            if args.once:
                run_cycle(config, connector, store, engine, specs, dashboard)
                return
            while True:
                now = datetime.now(timezone.utc)
                if _is_market_hours(config.polling, now):
                    run_cycle(config, connector, store, engine, specs, dashboard)
                else:
                    logger.info("fuera de horario de mercado, ciclo omitido", extra={"operation": "market_hours_gate"})
                time.sleep(config.polling.interval_minutes * 60)
    finally:
        store.close()


if __name__ == "__main__":
    main()
