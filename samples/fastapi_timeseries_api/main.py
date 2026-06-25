"""Run the time-series API against the Docker-compose TimescaleDB.

    docker compose -f samples/compose.yaml up -d
    uvicorn samples.fastapi_timeseries_api.main:app --reload

Then visit http://127.0.0.1:8000/docs to try the endpoints interactively.
"""

from __future__ import annotations

from samples.fastapi_timeseries_api.app import create_app

# Module-level ASGI app for `uvicorn samples.fastapi_timeseries_api.main:app`.
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
