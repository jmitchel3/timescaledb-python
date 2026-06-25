# 09 · FastAPI Time-Series API

A small but complete **FastAPI** REST API backed by a TimescaleDB hypertable —
the pattern from this package's main README, fleshed out and tested.

## What it shows

- An application factory `create_app(engine)` so the same app runs against the
  compose database **and** against a throwaway test container.
- Endpoints:
  - `GET /health` — lists hypertables.
  - `POST /readings` — ingest a reading.
  - `GET /readings?sensor_id=&limit=` — list readings (newest first).
  - `GET /sensors/{id}/latest` — last point (404 when none).
  - `GET /sensors/{id}/hourly` — `time_bucket_query` rollup.
- Testing HTTP endpoints end-to-end with `fastapi.testclient.TestClient`.

## Key files

- `models.py` — `Reading(TimescaleModel)` + request/response schemas.
- `app.py` — `create_app(engine)` and `init_db`.

## Run the tests

```bash
python -m pytest samples/fastapi_timeseries_api -v
```

## Serve the API (Docker compose)

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
uvicorn samples.fastapi_timeseries_api.main:app --reload
# open http://127.0.0.1:8000/docs
```
