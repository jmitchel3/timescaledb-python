# 10 · Capstone — The Full TimescaleDB Lifecycle

Everything in one project: a production-style weather-telemetry hypertable that
combines a hypertable, the Hypercore **columnstore**, a **retention policy**, a
**continuous aggregate**, and **gapfilled** reads.

## What it shows

`init_db` wires up every package feature at once:

- `create_hypertable(...)` — the hypertable.
- `enable_columnstore(...)` + `add_columnstore_policy(...)` — modern compression.
- `add_retention_policy(...)` — automatic chunk expiry.
- `CREATE MATERIALIZED VIEW … WITH (timescaledb.continuous)` +
  `refresh_continuous_aggregate(...)` — an hourly rollup.

Then it ingests data, refreshes the aggregate, `convert_to_columnstore(...)`s the
chunks, runs an interpolated `time_bucket_gapfill_query(...)`, and prints a
`lifecycle_summary(...)` proving each feature is in place.

## Key files

- `models.py` — `StationReading(TimescaleModel)` with the full config.
- `pipeline.py` — `init_db`, `refresh_hourly`, `convert_cold_chunks`,
  `temp_gapfilled`, `lifecycle_summary`.

## Run the tests

```bash
python -m pytest samples/weather_lifecycle_full -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.weather_lifecycle_full.main
```
