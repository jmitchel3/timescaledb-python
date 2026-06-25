# 08 · Continuous Aggregates — Hierarchical Rollups

Build TimescaleDB **continuous aggregates** (incrementally-maintained
materialized views) and refresh them with the package helper.

```
weather_conditions (raw)  →  conditions_hourly  →  conditions_daily
```

## What it shows

- Creating continuous aggregates with `CREATE MATERIALIZED VIEW … WITH
  (timescaledb.continuous)`.
- A **hierarchical** cagg: the daily aggregate rolls up the hourly one.
- `timescaledb.refresh_continuous_aggregate(...)` to materialize each tier.
- The required AUTOCOMMIT handling (cagg DDL and `CALL refresh_…` can't run
  inside a transaction block) — see `_run_autocommit` / `refresh_all`.

## Key files

- `models.py` — `WeatherCondition(TimescaleModel)`.
- `pipeline.py` — `init_db` (creates both caggs), `refresh_all`, `hourly_rollup`,
  `daily_rollup`.

## Run the tests

```bash
python -m pytest samples/continuous_aggregates_rollups -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.continuous_aggregates_rollups.main
```
