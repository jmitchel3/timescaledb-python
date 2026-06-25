"""Build hierarchical continuous aggregates and refresh them with the package.

Continuous aggregates are TimescaleDB's incrementally-maintained materialized
views. This sample creates two tiers:

    weather_conditions (raw)  ->  conditions_hourly  ->  conditions_daily

The daily aggregate rolls up the *hourly* aggregate (a hierarchical cagg), and
both are refreshed via :func:`timescaledb.refresh_continuous_aggregate`.

Note: ``CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)`` and
``CALL refresh_continuous_aggregate(...)`` cannot run inside a transaction
block, so those statements are executed on an AUTOCOMMIT connection.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session

import timescaledb
from samples._shared.db import create_tables
from samples.continuous_aggregates_rollups.models import WeatherCondition

HOURLY_VIEW = "conditions_hourly"
DAILY_VIEW = "conditions_daily"

_CREATE_HOURLY = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {HOURLY_VIEW}
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    location,
    avg(temperature) AS avg_temp,
    max(temperature) AS max_temp,
    min(temperature) AS min_temp
FROM weather_conditions
GROUP BY bucket, location
WITH NO DATA;
"""

_CREATE_DAILY = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {DAILY_VIEW}
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS bucket,
    location,
    avg(avg_temp) AS avg_temp,
    max(max_temp) AS max_temp,
    min(min_temp) AS min_temp
FROM {HOURLY_VIEW}
GROUP BY time_bucket('1 day', bucket), location
WITH NO DATA;
"""


def _run_autocommit(engine: Engine, *statements: str) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for stmt in statements:
            conn.execute(sqlalchemy.text(stmt))


def init_db(engine: Engine) -> None:
    """Create the raw hypertable plus the hourly and daily continuous aggregates."""
    create_tables(engine, WeatherCondition)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=WeatherCondition, commit=True)
    # Hierarchical caggs: hourly first, then daily on top of it.
    _run_autocommit(engine, _CREATE_HOURLY, _CREATE_DAILY)


def generate_conditions(
    locations: tuple[str, ...] = ("nyc", "sf", "london"),
    days: int = 5,
    every_minutes: int = 30,
    end: datetime | None = None,
) -> list[WeatherCondition]:
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    step = timedelta(minutes=every_minutes)

    rows: list[WeatherCondition] = []
    for i, location in enumerate(locations):
        baseline = 10 + 5 * i
        ts = start
        while ts < end:
            hour = ts.hour + ts.minute / 60.0
            temp = baseline + 8 * math.sin((hour / 24.0) * 2 * math.pi)
            rows.append(
                WeatherCondition(time=ts, location=location, temperature=round(temp, 2))
            )
            ts += step
    return rows


def insert_conditions(session: Session, rows: list[WeatherCondition]) -> int:
    session.add_all(rows)
    session.commit()
    return len(rows)


def refresh_all(engine: Engine) -> None:
    """Refresh both tiers (hourly first so daily sees materialized hourly data)."""
    with Session(engine.connect().execution_options(isolation_level="AUTOCOMMIT")) as s:
        timescaledb.refresh_continuous_aggregate(s, HOURLY_VIEW, None, None, force=True)
        timescaledb.refresh_continuous_aggregate(s, DAILY_VIEW, None, None, force=True)


def _select_view(engine: Engine, view: str, location: str | None = None) -> list[dict]:
    sql = f"SELECT bucket, location, avg_temp, max_temp, min_temp FROM {view}"
    params: dict = {}
    if location is not None:
        sql += " WHERE location = :loc"
        params["loc"] = location
    sql += " ORDER BY bucket, location"
    with engine.connect() as conn:
        rows = conn.execute(sqlalchemy.text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def hourly_rollup(engine: Engine, location: str | None = None) -> list[dict]:
    return _select_view(engine, HOURLY_VIEW, location)


def daily_rollup(engine: Engine, location: str | None = None) -> list[dict]:
    return _select_view(engine, DAILY_VIEW, location)
