# TimescaleDB Python — Sample Projects

Ten self-contained, **fully testable** sample projects that show what you can do
with **TimescaleDB**, **time-series data**, and the
[`timescaledb`](https://github.com/jmitchel3/timescaledb) Python package.

Every sample:

- is pure **Python** and uses the `timescaledb` package (`TimescaleModel`,
  `create_hypertable`, `time_bucket_query`, compression, columnstore, retention,
  continuous aggregates, …),
- runs against **TimescaleDB in Docker**,
- ships with a `pytest` suite that spins up a throwaway TimescaleDB container
  automatically (via [`testcontainers`](https://testcontainers.com/)), and
- includes a `main.py` you can run against a long-lived Docker-compose database.

## The catalog

| # | Project | TimescaleDB / package features highlighted |
|---|---------|--------------------------------------------|
| 01 | [`iot_sensor_network`](iot_sensor_network/) | `TimescaleModel`, `create_hypertable`, `time_bucket_query`, `list_hypertables`, last-point query |
| 02 | [`devops_metrics_gapfill`](devops_metrics_gapfill/) | `time_bucket_gapfill_query` with **gapfill**, **LOCF**, and **interpolation** |
| 03 | [`crypto_ohlcv_candles`](crypto_ohlcv_candles/) | `first()`/`last()` hyperfunctions + `time_bucket` → **OHLCV candlesticks** |
| 04 | [`energy_metering_compression`](energy_metering_compression/) | native **compression**: `enable_table_compression`, `add_compression_policy`, measuring the ratio |
| 05 | [`hypercore_columnstore`](hypercore_columnstore/) | **Hypercore columnstore** (TimescaleDB 2.18+): `enable_columnstore`, `add_columnstore_policy`, `convert_to_columnstore` |
| 06 | [`ecommerce_clickstream_retention`](ecommerce_clickstream_retention/) | **retention policy** + funnel rollups grouped by `time_bucket` and event type |
| 07 | [`fleet_gps_tracking`](fleet_gps_tracking/) | the **manual** `create_hypertable(table_name=..., hypertable_options=...)` path + downsampling |
| 08 | [`continuous_aggregates_rollups`](continuous_aggregates_rollups/) | **hierarchical continuous aggregates** (hourly → daily) + `refresh_continuous_aggregate` |
| 09 | [`fastapi_timeseries_api`](fastapi_timeseries_api/) | a **FastAPI** REST API over a hypertable, tested with `TestClient` |
| 10 | [`weather_lifecycle_full`](weather_lifecycle_full/) | **capstone**: hypertable + columnstore + retention + continuous aggregate + gapfill together |

## Prerequisites

- **Docker** running locally (Docker Desktop, Colima, OrbStack, …).
- **Python 3.11+**.

## Setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

pip install -e .                       # install this package (timescaledb)
pip install -r samples/requirements.txt
```

## Running the test suites (Docker, automatic)

The tests need **no manual database setup** — `testcontainers` starts a
TimescaleDB container for you and tears it down afterwards. A single container is
shared across every sample, and each test runs against a freshly reset schema.

```bash
# all samples
python -m pytest samples

# one sample
python -m pytest samples/iot_sensor_network -v
```

## Running a demo "for real" (Docker compose)

Each sample has a `main.py` that ingests data and prints results against a
long-lived database defined in [`compose.yaml`](compose.yaml):

```bash
docker compose -f samples/compose.yaml up -d

export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.iot_sensor_network.main

docker compose -f samples/compose.yaml down -v   # stop + wipe when finished
```

`main.py` calls `reset_database()` on startup, so each run starts from a clean
slate. The FastAPI sample (09) is instead served with uvicorn — see its README.

## How the samples are organized

```
samples/
├── compose.yaml          # long-lived TimescaleDB for the main.py demos
├── conftest.py           # shared pytest fixtures (testcontainers + per-test reset)
├── requirements.txt      # deps for running & testing the samples
├── _shared/db.py         # tiny engine/session/reset helpers used by every sample
└── <sample>/
    ├── models.py             # SQLModel / TimescaleModel table(s)
    ├── pipeline.py           # ingest + query logic (imported by both main and tests)
    ├── main.py               # runnable demo against compose
    ├── test_<sample>.py      # pytest suite against Docker
    └── README.md             # what it shows + how to run it
```

The `pipeline.py` ↔ `main.py` ↔ `test_*.py` split means the **exact** code you
read in the demo is the code under test.

## Troubleshooting

- **`docker.errors.DockerException: Error while fetching server API version …
  127.0.0.1:<port>`** — `testcontainers` can't reach the Docker daemon. This
  usually means a stale `tc.host` / `docker.host` line in
  `~/.testcontainers.properties` (Docker Desktop changes its API port between
  restarts). Point it at your Docker socket, e.g.
  `tc.host = unix:///Users/<you>/.docker/run/docker.sock`, or delete the line and
  let `DOCKER_HOST` / the default socket be used.
- **First test run is slow** — Docker is pulling `timescale/timescaledb:latest-pg17`.
  Subsequent runs reuse the cached image.
- **Port 5432 already in use** when starting compose — stop the other Postgres,
  or edit the published port in `compose.yaml` and your `DATABASE_URL`.
