# agente.md — Contexto de la sesión

> Archivo de traspaso (handoff) para retomar el trabajo en otra sesión.
> Fecha de la sesión original: **2026-07-20**.
> Fecha de esta actualización: **2026-07-20** (sesión nueva).

## ⚠️ Estado real de esta carpeta (leer primero)

Esta carpeta (`Agente IA Cripto`) **solo contiene archivos de contexto en
Markdown** (`agente.md`, `analisis-tecnico.md`, `compartir-analisis-tecnico.md`).
**Ninguno de los archivos de código descritos más abajo existe aquí**:
`dashboard.py`, `indicators.py`, `rank_sma20.py`, `backtest_estrategia.py`,
`CLAUDE.md`, `README.md`, `.claude/agents/analisis-tecnico.md`, ni los HTML de
salida (`crypto_dashboard.html`, `backtest_rebote_btc.html`).

El resto de este documento describe el trabajo hecho **en otra sesión/ubicación**
que generó esos archivos. Es historial de referencia, no el estado actual de esta
carpeta. **No reconstruir nada a partir de este archivo salvo que el usuario lo
pida explícitamente.**

## De qué va el proyecto

Dashboard técnico de criptoactivos + un subagente de Claude Code que lo opera e
interpreta. Todo se ejecuta a demanda y produce archivos HTML estáticos. Ver
`CLAUDE.md` para las preferencias y los límites de diseño (solo apoyo a la
decisión, sin exchanges ni órdenes, señal transparente, etc.).

## Qué se hizo en esta sesión (orden cronológico)

1. **Se creó el subagente `analisis-tecnico`** (`.claude/agents/analisis-tecnico.md`)
   y el **`CLAUDE.md`** con las preferencias del proyecto, a partir del README y el
   código existente.
2. **Se probó el pipeline base:** dependencias ya instaladas (Python 3.13), se
   corrió `python dashboard.py` → generó `crypto_dashboard.html` (BTC/ETH/XRP, los
   tres dieron "Señales mixtas").
3. **Screener de reversión (diario):** se creó `rank_sma20.py`, que rankea monedas
   por su distancia porcentual bajo la SMA20 (reutiliza `indicators.py`). Sobre 10
   monedas de CoinGecko; **se topó con el rate-limit de CoinGecko (HTTP 429)** con
   pausas de 3 s → para universos grandes hay que subir la pausa (~15 s) o reducir
   el universo.
4. **Estrategia del usuario (bot):** disparador = BTC cae ≥2% bajo su SMA20 (horario);
   se compra la candidata más caída respecto a su propia SMA20; se vende en el rebote
   de +2%.
5. **Decisión de datos:** CoinGecko gratis no da datos horarios de un año. El usuario
   **autorizó usar la API pública de Binance** (`/api/v3/klines`, sin key, solo lectura)
   solo para backtests horarios. Registrado como excepción en `CLAUDE.md` (límite 4).
6. **Backtest completo:** se creó `backtest_estrategia.py` (horario, 1 año, Binance) →
   genera `backtest_rebote_btc.html`. Código verificado sin look-ahead bias.

## Mapa de archivos (estado actual)

| Archivo | Qué es | Datos |
|---------|--------|-------|
| `dashboard.py` | CLI del dashboard técnico (SMA/EMA/RSI/MACD) | CoinGecko, diario |
| `indicators.py` | Indicadores puros (numpy) | — |
| `rank_sma20.py` | Screener: distancia bajo SMA20, rankea candidatas | CoinGecko, diario |
| `backtest_estrategia.py` | Backtest de la estrategia disparada por BTC | Binance, horario, 1 año |
| `.claude/agents/analisis-tecnico.md` | Subagente analista técnico | — |
| `CLAUDE.md` | Preferencias y límites del proyecto | — |
| `README.md` | Instrucciones para el usuario final | — |
| `crypto_dashboard.html` | Salida del dashboard técnico | — |
| `backtest_rebote_btc.html` | Salida del backtest de la estrategia | — |
| `compartir-analisis-tecnico.md` | Copia distribuible del subagente | — |

## Hallazgos clave del backtest (2026-07-20)

- 112 disparos → 54 trades. **Win-rate 81.5 %, pero retorno compuesto −33.5 %** y
  máx. drawdown −52 %. Es el caso de manual del **payoff asimétrico**: ganadoras
  topadas en +2 %, y los 10 timeouts sin stop-loss realizan pérdidas grandes que se
  comen las ganancias chicas. **Un win-rate alto ≠ rentabilidad.**
- Mejores candidatas por perfil (n≥3, retorno medio positivo): **BCH, DOGE, SUI**
  (y LINK apenas). ZEC/SOL/ETH/ADA/XLM: acierto decente pero retorno medio negativo.
- Todo ignora **fees y slippage** → con costos reales, hasta las "buenas" podrían
  volverse negativas. Es un solo año (un régimen de mercado).
- Símbolos saltados: HYPEUSDT (no listado), XMRUSDT (Monero delistado del par USDT).

## Preferencias / decisiones registradas

- Fuente de datos: **CoinGecko** para el dashboard normal; **Binance** autorizado
  solo para backtests horarios (excepción acordada, ver `CLAUDE.md`).
- Sin alertas automáticas (push/correo/Telegram) salvo pedido explícito.
- El subagente y las salidas nunca recomiendan comprar/vender: solo describen datos.

## Próximos pasos / ideas pendientes

- **Atacar la asimetría del backtest:** probar variante con **stop-loss** (p. ej. −3 %)
  y/o **filtro de tendencia (SMA200)**; comparar si el retorno compuesto se vuelve
  positivo. (Es el siguiente paso sugerido, aún no ejecutado.)
- Incluir **fees/slippage** en el backtest para un resultado realista.
- Recordatorio operativo: al crear nuevos subagentes, **reiniciar Claude Code** para
  que los descubra (los `.claude/agents/*.md` se cargan al iniciar sesión).

## Cómo retomar

Estos comandos solo funcionan si los scripts existen en la carpeta de trabajo
(ver aviso al inicio de este documento — en `Agente IA Cripto` actualmente no
existen):

```bash
python dashboard.py                 # dashboard técnico (CoinGecko)
python rank_sma20.py                # screener de distancia bajo SMA20
python backtest_estrategia.py       # backtest de la estrategia (Binance, horario)
```

Para pedirle al subagente que trabaje: en el chat, *"usa el agente analisis-tecnico
para…"*.

---
*Nota: esto no es asesoría financiera. Las salidas describen datos pasados; la
decisión es siempre del usuario.*
