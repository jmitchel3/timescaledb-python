# 03 · Crypto Ticks → OHLCV Candles

Aggregate a raw trade-tick stream into **OHLCV candlesticks** — the canonical
financial time-series query.

## What it shows

- TimescaleDB hyperfunctions `first(price, time)` and `last(price, time)` for the
  candle **open** and **close**.
- `min` / `max` / `sum` for **low** / **high** / **volume**.
- The package's `time_bucket(...)` expression composed into a normal SQLModel
  `select(...)`.
- Wider buckets (`1 minute` → `5 minutes`) produce fewer candles.

## Key files

- `models.py` — `Trade(TimescaleModel)`.
- `pipeline.py` — `generate_trades` (deterministic random walk), `ohlcv`.

## Run the tests

```bash
python -m pytest samples/crypto_ohlcv_candles -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.crypto_ohlcv_candles.main
```
