# mineral-markets-mcp

Dos entregables comparten la misma capa de datos (`connectors/`, `core/`):

- **`server.py`** — servidor MCP: expone tools (`get_market_snapshot`, etc.) para que un
  agente/LLM las llame bajo demanda.
- **`monitor.py`** — agente de monitoreo de consola: loop continuo que ingesta precios,
  calcula indicadores técnicos, evalúa señales, persiste todo en SQLite y muestra una
  tabla en vivo. Es el foco de este README.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env      # Windows; en macOS/Linux: cp .env.example .env
```

No hace falta ninguna API key para el monitor en su modo por defecto (usa yfinance, sin
credenciales). El `.env` solo importa si más adelante configuras alguno de los 11
conectores premium (ver `.env.example`) o quieres ajustar `LOG_LEVEL`, `CACHE_TTL_SECONDS`,
`RATE_LIMIT_PER_SECOND` o `RETRY_MAX_ATTEMPTS`.

## Correr el agente de monitoreo

```bash
# un solo ciclo (fetch + persist + indicadores + señales + tabla), para probar
python -m mineral_markets_mcp.monitor --once

# loop continuo según config.yaml (polling.interval_minutes)
python -m mineral_markets_mcp.monitor

# sin dashboard interactivo (solo logs JSON por stderr) — útil en CI o headless
python -m mineral_markets_mcp.monitor --no-dashboard

# config o base de datos alternativos
python -m mineral_markets_mcp.monitor --config otro_config.yaml --db otro.db
```

El estado persiste en `market_monitor.db` (SQLite) en el directorio desde donde corras
el comando. Tablas: `assets` (catálogo, poblado desde `config.yaml`), `prices` (OHLCV
diario), `snapshots` (precio + indicadores por ciclo) y `signals` (log de disparos, una
fila por regla/símbolo/día). Para inspeccionar:

```bash
sqlite3 market_monitor.db "select symbol, rule_name, message from signals order by triggered_at desc limit 20;"
```

## `config.yaml`

Define el universo de activos (metales, mineras, tus tickers personalizados en
`custom_tickers`, índices, macro), la frecuencia de polling y los umbrales de señales.
Edítalo directamente — no requiere tocar código para agregar/quitar un ticker. Ver el
archivo en la raíz del proyecto para el formato completo.

## Señales del MVP

- **RSI(14) sobreventa/sobrecompra** (`rsi.oversold` / `rsi.overbought`)
- **Ruptura de SMA** configurable (`sma_breakout.period`, por defecto 50)
- **Movimiento intradía** > `intraday_move_pct`

Cada regla dispara **una vez por símbolo por día** (se loguea y persiste en `signals`),
pero el dashboard en vivo sigue mostrando la señal mientras la condición esté vigente.
MACD y el cambio del Gold/Silver Ratio ya se calculan y persisten en `snapshots.macd*`,
pero todavía no disparan señales — quedan para la siguiente iteración, junto con el
reporte diario en markdown.

## Limitaciones de las fuentes gratuitas (léelo antes de operar con esto)

**yfinance no es tick real-time.** Es la única fuente 100% gratuita y sin API key hoy
(`connectors/open_data.py`), pero:

- Delay típico de **~15-20 minutos** en muchas plazas de equities; en FX/futuros de
  metales suele ser menor pero tampoco es tick-by-tick garantizado.
- Cobertura de metales limitada a **oro, plata, cobre, platino y paladio** (vía pares FX
  spot y futuros COMEX). Níquel, litio, aluminio (LME), uranio y tierras raras **no
  tienen fuente libre fiable** — el conector lanza `SymbolNotFoundError` explicando que
  requieren un conector premium (LSEG, FactSet, S&P Global).
- Cada `Quote`/`TimeseriesResult` declara `is_delayed=True` y `source` explícitamente —
  el sistema nunca finge que un dato es real-time cuando no lo es.
- Sin SLA: Yahoo puede cambiar/romper el endpoint sin aviso (riesgo inherente a
  `yfinance`, no a este código).

**Si necesitas real-time verdadero**, opciones y costo aproximado:

| Proveedor | Cobertura | Desde | Notas |
|---|---|---|---|
| **OANDA API** | FX spot + metales (XAU/XAG como CFD) | Gratis (cuenta demo) | La opción más barata para real-time de oro/plata; no cubre equities/mineras |
| **Twelve Data** | Equities, forex, metales, índices | ~US$29/mes (plan "Grow") | WebSocket real-time, buena cobertura combinada |
| **Polygon.io** | Equities/índices real-time | ~US$29/mes stocks; ~US$199/mes real-time SIP completo | Forex/metales en plan aparte |
| **Finnhub** | Equities real-time (US) | Planes pagos desde ~US$50/mes | Websocket real-time solo en plan pago |
| **Metals-API** | Solo metales preciosos/industriales | ~US$10-50/mes según refresco | Especializado, no cubre equities |
| **Alpha Vantage Premium** | Equities/forex/commodities | Desde ~US$50/mes | Rate limits más altos, no siempre tick-level |

Cualquiera de estos se integraría como un nuevo `Connector` (implementando
`connectors/base.py::BaseConnector`) sin tocar `monitor.py`, `analysis/` ni `signals/` —
esa es la razón de tener la interfaz `DataProvider` separada de la lógica de negocio.

## Horario de mercado

`config.yaml: polling.market_hours_only` restringe el polling a 09:30-16:00 hora de
`polling.timezone` (por defecto `America/New_York`), lunes a viernes. **No** conoce
feriados bursátiles en esta versión — un feriado se trata como día hábil normal.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Roadmap (próximas iteraciones, no incluidas aún)

1. Señales de cruce MACD y cambio del Gold/Silver Ratio.
2. Reporte diario en markdown (top movers, señales del día, snapshot macro).
3. Calendario de feriados bursátiles para el gate de horario de mercado.
4. Hook de notificaciones real (Slack/email/Telegram) y conector real-time
   (OANDA/Twelve Data) detrás de la misma interfaz `BaseConnector`.
