CREATE TABLE IF NOT EXISTS assets (
    symbol       TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    asset_class  TEXT NOT NULL CHECK (asset_class IN ('metal','equity','index','macro')),
    yf_symbol    TEXT NOT NULL,
    is_custom    INTEGER NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prices (
    symbol     TEXT NOT NULL REFERENCES assets(symbol),
    ts         TEXT NOT NULL,
    interval   TEXT NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL NOT NULL,
    volume     REAL,
    source     TEXT NOT NULL,
    is_delayed INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (symbol, ts, interval)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_ts ON prices(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at    TEXT NOT NULL,
    symbol         TEXT NOT NULL REFERENCES assets(symbol),
    price          REAL NOT NULL,
    change_percent REAL,
    rsi_14         REAL,
    macd           REAL,
    macd_signal    REAL,
    macd_hist      REAL,
    sma_20         REAL,
    sma_50         REAL,
    ema_20         REAL,
    vwap           REAL,
    bb_upper       REAL,
    bb_lower       REAL,
    source         TEXT NOT NULL,
    is_delayed     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time ON snapshots(symbol, captured_at DESC);

CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_at TEXT NOT NULL,
    symbol       TEXT NOT NULL REFERENCES assets(symbol),
    rule_name    TEXT NOT NULL,
    direction    TEXT NOT NULL CHECK (direction IN ('bullish','bearish','neutral')),
    value        REAL,
    threshold    REAL,
    message      TEXT NOT NULL,
    snapshot_id  INTEGER REFERENCES snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, triggered_at DESC);
