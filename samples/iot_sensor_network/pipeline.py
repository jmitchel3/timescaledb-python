"""Ingest + query logic for the IoT sensor network sample.

Everything here is plain functions so the exact same code path is exercised by
``main.py`` (against Docker compose) and by the test suite (against a throwaway
testcontainers database).
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

import timescaledb
from samples._shared.db import create_tables
from samples.iot_sensor_network.models import SensorReading


def init_db(engine: Engine) -> None:
    """Create the table and promote it to a TimescaleDB hypertable."""
    create_tables(engine, SensorReading)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=SensorReading, commit=True)


def generate_readings(
    sensors: int = 4,
    hours: int = 24,
    every_minutes: int = 5,
    end: datetime | None = None,
    seed: int = 7,
) -> list[SensorReading]:
    """Deterministically generate a fleet of sensor readings.

    Temperature follows a daily sine wave per sensor with a little noise so the
    aggregates are realistic but reproducible (fixed ``seed``).
    """
    rng = random.Random(seed)
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    step = timedelta(minutes=every_minutes)

    readings: list[SensorReading] = []
    for sensor_id in range(1, sensors + 1):
        baseline = 18.0 + sensor_id  # each sensor sits at a slightly different temp
        ts = start
        while ts <= end:
            hour_of_day = ts.hour + ts.minute / 60.0
            daily = 5.0 * math.sin((hour_of_day / 24.0) * 2 * math.pi)
            readings.append(
                SensorReading(
                    time=ts,
                    sensor_id=sensor_id,
                    temperature_c=round(baseline + daily + rng.uniform(-0.5, 0.5), 3),
                    humidity_pct=round(50 + 10 * rng.random(), 2),
                )
            )
            ts += step
    return readings


def insert_readings(session: Session, readings: Iterable[SensorReading]) -> int:
    """Bulk insert readings, returning how many rows were written."""
    rows = list(readings)
    session.add_all(rows)
    session.commit()
    return len(rows)


def hourly_average_temperature(
    session: Session, sensor_id: int, interval: str = "1 hour"
) -> list[dict]:
    """Average temperature per time bucket for a single sensor.

    Uses the package helper :func:`timescaledb.time_bucket_query`, which builds a
    ``time_bucket(...)`` GROUP BY for us.
    """
    return timescaledb.time_bucket_query(
        session,
        model=SensorReading,
        interval=interval,
        time_field="time",
        metric_field="temperature_c",
        filters=[SensorReading.sensor_id == sensor_id],
    )


def latest_per_sensor(session: Session) -> dict[int, float]:
    """Most-recent temperature for every sensor (classic 'last point' query)."""
    subq = (
        select(
            SensorReading.sensor_id,
            func.max(SensorReading.time).label("latest"),
        )
        .group_by(SensorReading.sensor_id)
        .subquery()
    )
    rows = session.exec(
        select(SensorReading.sensor_id, SensorReading.temperature_c)
        .join(
            subq,
            (SensorReading.sensor_id == subq.c.sensor_id)
            & (SensorReading.time == subq.c.latest),
        )
        .order_by(SensorReading.sensor_id)
    ).all()
    return {sensor_id: temp for sensor_id, temp in rows}


def list_sample_hypertables(session: Session) -> list[str]:
    """Return the names of hypertables visible to this sample."""
    return [h.hypertable_name for h in timescaledb.list_hypertables(session)]
