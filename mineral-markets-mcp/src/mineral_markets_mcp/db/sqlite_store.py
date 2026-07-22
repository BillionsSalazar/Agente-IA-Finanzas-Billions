"""Persistencia SQLite: catálogo de activos, precios OHLCV, snapshots y señales.

Un `SQLiteStore` por proceso; usa `sqlite3` de la librería estándar (sin ORM)
con las tablas de `schema.sql`. No es thread-safe entre hilos concurrentes —
el `monitor.py` corre en un único loop secuencial.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from mineral_markets_mcp.config.loader import AssetSpec


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, db_path: str | Path = "market_monitor.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        schema_sql = resources.files("mineral_markets_mcp.db").joinpath("schema.sql").read_text(encoding="utf-8")
        self._conn.executescript(schema_sql)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- assets ----------------------------------------------------------

    def sync_assets(self, specs: list[AssetSpec]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO assets (symbol, display_name, asset_class, yf_symbol, is_custom, active)
                VALUES (:symbol, :display_name, :asset_class, :yf_symbol, :is_custom, 1)
                ON CONFLICT(symbol) DO UPDATE SET
                    display_name = excluded.display_name,
                    asset_class  = excluded.asset_class,
                    yf_symbol    = excluded.yf_symbol,
                    is_custom    = excluded.is_custom,
                    active       = 1
                """,
                [
                    {
                        "symbol": s.symbol,
                        "display_name": s.display_name,
                        "asset_class": s.asset_class,
                        "yf_symbol": s.yf_symbol,
                        "is_custom": int(s.is_custom),
                    }
                    for s in specs
                ],
            )

    # -- prices ------------------------------------------------------------

    def insert_price(
        self,
        symbol: str,
        ts: datetime,
        interval: str,
        close: float,
        open_: float | None = None,
        high: float | None = None,
        low: float | None = None,
        volume: float | None = None,
        source: str = "open",
        is_delayed: bool = True,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO prices (symbol, ts, interval, open, high, low, close, volume, source, is_delayed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, ts, interval) DO UPDATE SET
                    open = excluded.open, high = excluded.high, low = excluded.low,
                    close = excluded.close, volume = excluded.volume,
                    source = excluded.source, is_delayed = excluded.is_delayed
                """,
                (symbol, ts.isoformat(), interval, open_, high, low, close, volume, source, int(is_delayed)),
            )

    # -- snapshots -----------------------------------------------------------

    def insert_snapshot(self, symbol: str, indicators: dict[str, Any], source: str, is_delayed: bool = True) -> int:
        captured_at = _utcnow_iso()
        cur = self._conn.execute(
            """
            INSERT INTO snapshots (
                captured_at, symbol, price, change_percent, rsi_14, macd, macd_signal,
                macd_hist, sma_20, sma_50, ema_20, vwap, bb_upper, bb_lower, source, is_delayed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                captured_at,
                symbol,
                indicators.get("price"),
                indicators.get("change_percent"),
                indicators.get("rsi_14"),
                indicators.get("macd"),
                indicators.get("macd_signal"),
                indicators.get("macd_hist"),
                indicators.get("sma_20"),
                indicators.get("sma_50"),
                indicators.get("ema_20"),
                indicators.get("vwap"),
                indicators.get("bb_upper"),
                indicators.get("bb_lower"),
                source,
                int(is_delayed),
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_latest_snapshot(self, symbol: str) -> sqlite3.Row | None:
        cur = self._conn.execute(
            "SELECT * FROM snapshots WHERE symbol = ? ORDER BY captured_at DESC LIMIT 1",
            (symbol,),
        )
        return cur.fetchone()

    def get_today_snapshots(self) -> list[sqlite3.Row]:
        today = datetime.now(timezone.utc).date().isoformat()
        cur = self._conn.execute(
            "SELECT * FROM snapshots WHERE captured_at >= ? ORDER BY captured_at ASC",
            (today,),
        )
        return cur.fetchall()

    # -- signals -----------------------------------------------------------

    def insert_signal(
        self,
        symbol: str,
        rule_name: str,
        direction: str,
        value: float | None,
        threshold: float | None,
        message: str,
        snapshot_id: int | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO signals (triggered_at, symbol, rule_name, direction, value, threshold, message, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_utcnow_iso(), symbol, rule_name, direction, value, threshold, message, snapshot_id),
            )

    def has_fired_today(self, symbol: str, rule_name: str) -> bool:
        today = datetime.now(timezone.utc).date().isoformat()
        cur = self._conn.execute(
            "SELECT 1 FROM signals WHERE symbol = ? AND rule_name = ? AND triggered_at >= ? LIMIT 1",
            (symbol, rule_name, today),
        )
        return cur.fetchone() is not None

    def get_today_signals(self) -> list[sqlite3.Row]:
        today = datetime.now(timezone.utc).date().isoformat()
        cur = self._conn.execute(
            "SELECT * FROM signals WHERE triggered_at >= ? ORDER BY triggered_at ASC",
            (today,),
        )
        return cur.fetchall()
