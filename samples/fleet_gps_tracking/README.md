# 07 · Fleet GPS Tracking — Manual Hypertable

Not every table inherits from `TimescaleModel`. This sample uses a **plain
`SQLModel`** and the **manual** `create_hypertable(...)` path, then downsamples
high-frequency GPS pings.

## What it shows

- `create_hypertable(session, table_name=..., hypertable_options={...})` on an
  ordinary SQLModel table (the alternative to class-var configuration).
- `is_hypertable(...)` to confirm the conversion.
- Downsampling 10-second pings into a per-minute avg/peak speed series with
  `time_bucket`.

## Key files

- `models.py` — `GpsPing(SQLModel)` + `HYPERTABLE_OPTIONS`.
- `pipeline.py` — `init_db` (manual path), `downsample_speed`, `chunk_count`.

## Run the tests

```bash
python -m pytest samples/fleet_gps_tracking -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.fleet_gps_tracking.main
```
