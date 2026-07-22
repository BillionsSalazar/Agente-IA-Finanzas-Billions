"""Evalúa las reglas de `signals/rules.py` por activo y persiste los disparos.

Cada regla dispara como máximo una vez por (símbolo, rule_name) por día — sin
esto, una regla que se sigue cumpliendo (ej. RSI bajo el umbral) dispararía en
cada ciclo de polling, inundando el log y el reporte diario de duplicados.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mineral_markets_mcp.config.loader import SignalsConfig
from mineral_markets_mcp.core.logging_config import get_logger
from mineral_markets_mcp.db.sqlite_store import SQLiteStore
from mineral_markets_mcp.signals.rules import RULES, RuleContext, Signal

logger = get_logger(__name__)


class SignalEngine:
    def __init__(self, config: SignalsConfig, store: SQLiteStore) -> None:
        self._config = config
        self._store = store

    def evaluate(
        self,
        symbol: str,
        price: float,
        change_percent: float | None,
        indicators: dict[str, Any],
        closes: pd.Series,
        snapshot_id: int | None,
    ) -> list[Signal]:
        """Devuelve TODAS las señales actualmente activas (para el dashboard),
        pero solo persiste + loggea las que no se hayan disparado hoy — el
        dashboard debe seguir mostrando una condición vigente (ej. RSI bajo el
        umbral) aunque ya no se vuelva a escribir en `signals`.
        """
        ctx = RuleContext(
            symbol=symbol,
            price=price,
            change_percent=change_percent,
            indicators=indicators,
            closes=closes,
            config=self._config,
        )

        active: list[Signal] = []
        for rule in RULES:
            signal = rule(ctx)
            if signal is None:
                continue
            active.append(signal)
            if self._store.has_fired_today(signal.symbol, signal.rule_name):
                continue
            self._store.insert_signal(
                symbol=signal.symbol,
                rule_name=signal.rule_name,
                direction=signal.direction,
                value=signal.value,
                threshold=signal.threshold,
                message=signal.message,
                snapshot_id=snapshot_id,
            )
            logger.warning(signal.message, extra={"symbol": signal.symbol, "operation": signal.rule_name})
        return active
