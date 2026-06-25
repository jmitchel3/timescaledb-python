"""End-to-end lifecycle for a production weather-telemetry hypertable.

``init_db`` wires up every package feature at once:

* hypertable creation                      (create_hypertable)
* Hypercore columnstore + policy           (enable_columnstore / add_columnstore_policy)
* retention policy                         (add_retention_policy)
* a continuous aggregate                   (raw DDL + refresh_continuous_aggregate)

Then we ingest, refresh the aggregate, gap-fill reads, and move cold chunks into
the columnstore -- the same operations you'd schedule in production.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session

import timescaledb
from samples._shared.db import create_tables
from samples.weather_lifecycle_full.models import StationReading
from timescaledb.hypertables.list import is_hypertable

TABLE = "station_readings"
HOURLY_VIEW = "station_hourly"

_CREATE_HOURLY = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {HOURLY_VIEW}
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    station_id,
    avg(temp_c) AS avg_temp,
    max(wind_kph) AS max_wind
FROM {TABLE}
GROUP BY bucket, station_id
WITH NO DATA;
"""


def init_db(engine: Engine) -> None:
    create_tables(engine, StationReading)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=StationReading, commit=True)
        # Columnstore (modern compression) from the model's class vars.
        timescaledb.enable_columnstore(session, model=StationReading, commit=True)
        timescaledb.add_columnstore_policy(session, model=StationReading, commit=True)
        # Retention policy from the model's __drop_after__.
        timescaledb.add_retention_policy(session, model=StationReading)
        session.commit()
    # Continuous aggregate must be created outside a transaction block.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(sqlalchemy.text(_CREATE_HOURLY))


def generate_readings(
    stations: int = 3,
    days: int = 14,
    every_minutes: int = 30,
    end: datetime | None = None,
) -> list[StationReading]:
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    step = timedelta(minutes=every_minutes)

    rows: list[StationReading] = []
    for station_id in range(1, stations + 1):
        ts = start
        while ts < end:
            hour = ts.hour + ts.minute / 60.0
            temp = 12 + station_id + 9 * math.sin((hour / 24.0) * 2 * math.pi)
            wind = 8 + 6 * abs(math.sin(hour / 6.0))
            rows.append(
                StationReading(
                    time=ts,
                    station_id=station_id,
                    temp_c=round(temp, 2),
                    wind_kph=round(wind, 2),
                )
            )
            ts += step
    return rows


def insert_readings(session: Session, rows: list[StationReading]) -> int:
    session.add_all(rows)
    session.commit()
    return len(rows)


def refresh_hourly(engine: Engine) -> None:
    with Session(engine.connect().execution_options(isolation_level="AUTOCOMMIT")) as s:
        timescaledb.refresh_continuous_aggregate(s, HOURLY_VIEW, None, None, force=True)


def hourly_rollup(session: Session, station_id: int) -> list[dict]:
    rows = session.execute(
        sqlalchemy.text(
            f"SELECT bucket, avg_temp, max_wind FROM {HOURLY_VIEW} "
            "WHERE station_id = :sid ORDER BY bucket"
        ),
        {"sid": station_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def temp_gapfilled(
    session: Session,
    station_id: int,
    start: datetime,
    finish: datetime,
    interval: str = "1 hour",
) -> list[dict]:
    """Evenly-spaced, interpolated temperature series straight from raw data."""
    return timescaledb.time_bucket_gapfill_query(
        session,
        model=StationReading,
        interval=interval,
        time_field="time",
        metric_field="temp_c",
        start=start,
        finish=finish,
        use_interpolate=True,
        filters=[StationReading.station_id == station_id],
    )


def convert_cold_chunks(session: Session) -> int:
    """Move every chunk into the columnstore now; returns the count converted."""
    names = [
        row[0]
        for row in session.execute(
            sqlalchemy.text("SELECT show_chunks(:t)::text"), {"t": TABLE}
        ).fetchall()
    ]
    for name in names:
        timescaledb.convert_to_columnstore(session, name, commit=False)
    session.commit()
    return len(names)


def lifecycle_summary(session: Session) -> dict:
    """A single snapshot proving every lifecycle feature is in place."""
    columnstore_chunks = session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name = :t AND is_compressed"
        ),
        {"t": TABLE},
    ).scalar_one()
    retention_jobs = session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM timescaledb_information.jobs "
            "WHERE hypertable_name = :t AND proc_name = 'policy_retention'"
        ),
        {"t": TABLE},
    ).scalar_one()
    return {
        "is_hypertable": is_hypertable(session, TABLE),
        "columnstore_policies": timescaledb.list_columnstore_policies(session),
        "retention_jobs": int(retention_jobs),
        "columnstore_chunks": int(columnstore_chunks),
    }
