"""Track a vehicle fleet and downsample high-frequency GPS pings.

Shows the manual hypertable workflow: create a normal table, then call
``create_hypertable`` with an explicit ``hypertable_options`` dict. Querying then
uses ``time_bucket`` to downsample second-by-second pings into a chart-friendly
per-minute series.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

import timescaledb
from samples._shared.db import create_tables
from samples.fleet_gps_tracking.models import HYPERTABLE_OPTIONS, GpsPing
from timescaledb.hypertables.list import is_hypertable as _is_hypertable
from timescaledb.hyperfunctions import time_bucket

TABLE = "fleet_gps_pings"


def init_db(engine: Engine) -> None:
    create_tables(engine, GpsPing)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        # Manual path: convert the existing table into a hypertable.
        timescaledb.create_hypertable(
            session,
            table_name=TABLE,
            hypertable_options=HYPERTABLE_OPTIONS,
            commit=True,
        )


def generate_pings(
    vehicles: int = 3,
    minutes: int = 60,
    every_seconds: int = 10,
    start: datetime | None = None,
    seed: int = 3,
) -> list[GpsPing]:
    """Simulate vehicles driving a smooth route with varying speed."""
    rng = random.Random(seed)
    start = start or (datetime.now(timezone.utc) - timedelta(minutes=minutes))
    step = timedelta(seconds=every_seconds)

    rows: list[GpsPing] = []
    for vehicle_id in range(1, vehicles + 1):
        lat, lon = 37.0 + vehicle_id, -122.0 - vehicle_id
        ts = start
        t = 0
        while ts < start + timedelta(minutes=minutes):
            speed = 40 + 20 * math.sin(t / 30.0) + rng.uniform(-3, 3)
            lat += 0.0005
            lon += 0.0004
            rows.append(
                GpsPing(
                    time=ts,
                    vehicle_id=vehicle_id,
                    lat=round(lat, 6),
                    lon=round(lon, 6),
                    speed_kph=round(max(0.0, speed), 2),
                )
            )
            ts += step
            t += 1
    return rows


def insert_pings(session: Session, pings: list[GpsPing]) -> int:
    session.add_all(pings)
    session.commit()
    return len(pings)


def downsample_speed(
    session: Session, vehicle_id: int, interval: str = "1 minute"
) -> list[dict]:
    """Average and peak speed per bucket for one vehicle."""
    b = time_bucket(interval, GpsPing.time)
    query = (
        select(
            b.label("bucket"),
            func.avg(GpsPing.speed_kph).label("avg_speed"),
            func.max(GpsPing.speed_kph).label("max_speed"),
        )
        .where(GpsPing.vehicle_id == vehicle_id)
        .group_by(b)
        .order_by(b)
    )
    return list(session.exec(query).mappings().all())


def chunk_count(session: Session) -> int:
    return session.execute(
        sqlalchemy.text("SELECT count(*) FROM show_chunks(:t)"), {"t": TABLE}
    ).scalar_one()


def is_hypertable(session: Session) -> bool:
    return _is_hypertable(session, TABLE)
