# 01 · IoT Sensor Network

The foundations: turn a `TimescaleModel` into a hypertable, bulk-ingest sensor
readings, and roll them up with `time_bucket`.

## What it shows

- Defining a hypertable by subclassing `timescaledb.TimescaleModel`
  (`__chunk_time_interval__`, `__drop_after__`).
- `create_hypertable(...)` and `list_hypertables(...)`.
- Hourly averages via the package helper `time_bucket_query(...)`.
- A classic "last point per sensor" query.

## Key files

- `models.py` — `SensorReading(TimescaleModel)`.
- `pipeline.py` — `init_db`, `generate_readings`, `hourly_average_temperature`,
  `latest_per_sensor`.

## Run the tests (Docker, automatic)

```bash
python -m pytest samples/iot_sensor_network -v
```

## Run the demo (Docker compose)

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.iot_sensor_network.main
```
