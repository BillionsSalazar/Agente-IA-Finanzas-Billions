"""Tabla en vivo de consola (rich.Live) — precio, %cambio, RSI y señal activa.

Se usa `rich.Live` en vez de Textual: para una tabla que solo se refresca cada
ciclo de polling y no necesita interacción del usuario (scroll, filtros,
teclado), `rich.Live` es la opción más simple. Si más adelante se quiere
interacción (filtrar por clase de activo, ordenar columnas), Textual es la
evolución natural.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.table import Table

from mineral_markets_mcp.signals.rules import Signal


@dataclass
class AssetRow:
    symbol: str
    display_name: str
    asset_class: str
    price: float | None
    currency: str
    change_percent: float | None
    rsi_14: float | None
    is_delayed: bool
    error: str | None = None
    signals: list[Signal] = field(default_factory=list)


def _change_style(change_percent: float | None) -> str:
    if change_percent is None:
        return "dim"
    if change_percent > 0:
        return "green"
    if change_percent < 0:
        return "red"
    return "white"


def _rsi_style(rsi_value: float | None) -> str:
    if rsi_value is None:
        return "dim"
    if rsi_value < 30:
        return "green"
    if rsi_value > 70:
        return "red"
    return "white"


def _signal_cell(signals: list[Signal]) -> tuple[str, str]:
    if not signals:
        return "", "dim"
    directions = {s.direction for s in signals}
    style = "red" if "bearish" in directions else "green" if "bullish" in directions else "yellow"
    return ", ".join(s.rule_name for s in signals), style


def build_table(rows: list[AssetRow], as_of: str) -> Table:
    table = Table(title=f"Monitor de mercados — {as_of}", expand=True)
    table.add_column("Símbolo")
    table.add_column("Clase")
    table.add_column("Precio", justify="right")
    table.add_column("%Chg", justify="right")
    table.add_column("RSI(14)", justify="right")
    table.add_column("Señal activa")

    for row in rows:
        if row.error:
            table.add_row(row.symbol, row.asset_class, "[dim]—[/dim]", "[dim]—[/dim]", "[dim]—[/dim]", f"[red]error: {row.error}[/red]")
            continue

        price_str = f"{row.price:,.2f} {row.currency}" if row.price is not None else "—"
        chg_str = f"{row.change_percent:+.2f}%" if row.change_percent is not None else "—"
        rsi_str = f"{row.rsi_14:.1f}" if row.rsi_14 is not None else "—"
        signal_text, signal_style = _signal_cell(row.signals)

        table.add_row(
            row.display_name,
            row.asset_class,
            f"[{_change_style(row.change_percent)}]{price_str}[/]",
            f"[{_change_style(row.change_percent)}]{chg_str}[/]",
            f"[{_rsi_style(row.rsi_14)}]{rsi_str}[/]",
            f"[{signal_style}]{signal_text}[/]" if signal_text else "",
        )
    return table


class Dashboard:
    """Envuelve `rich.Live` para refrescar la tabla en cada ciclo del loop."""

    def __init__(self) -> None:
        self._console = Console()
        self._live = Live(console=self._console, refresh_per_second=1, screen=False)

    def __enter__(self) -> "Dashboard":
        self._live.__enter__()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._live.__exit__(*exc_info)

    def update(self, rows: list[AssetRow], as_of: str) -> None:
        self._live.update(build_table(rows, as_of))
