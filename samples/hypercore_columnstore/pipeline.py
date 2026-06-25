"""Enable the Hypercore columnstore, move chunks into it, and read the stats.

Modern columnstore workflow (all via the ``timescaledb`` package):

1. ``enable_columnstore`` + ``add_columnstore_policy`` from the model's class vars.
2. ``convert_to_columnstore`` to move existing chunks into the columnstore now.
3. ``list_columnstore_policies`` to confirm the policy is registered.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session

import timescaledb
from samples._shared.db import create_tables
from samples.hypercore_columnstore.models import DeviceMetric

TABLE = "hypercore_device_metrics"


def init_db(engine: Engine) -> None:
    create_tables(engine, DeviceMetric)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=DeviceMetric, commit=True)
        timescaledb.enable_columnstore(session, model=DeviceMetric, commit=True)
        timescaledb.add_columnstore_policy(session, model=DeviceMetric, commit=True)


def generate_metrics(
    devices: int = 4,
    days: int = 10,
    every_minutes: int = 10,
    end: datetime | None = None,
) -> list[DeviceMetric]:
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    step = timedelta(minutes=every_minutes)

    rows: list[DeviceMetric] = []
    for device_id in range(1, devices + 1):
        ts = start
        base = 100.0 * device_id
        while ts < end:
            rows.append(DeviceMetric(time=ts, device_id=device_id, value=base))
            ts += step
    return rows


def insert_metrics(session: Session, metrics: list[DeviceMetric]) -> int:
    session.add_all(metrics)
    session.commit()
    return len(metrics)


def chunk_names(session: Session) -> list[str]:
    rows = session.execute(
        sqlalchemy.text("SELECT show_chunks(:t)::text"), {"t": TABLE}
    ).fetchall()
    return [row[0] for row in rows]


def convert_all_to_columnstore(session: Session) -> int:
    """Move every chunk into the columnstore; returns the number converted."""
    names = chunk_names(session)
    for name in names:
        timescaledb.convert_to_columnstore(session, name, commit=False)
    session.commit()
    return len(names)


def columnstore_chunk_count(session: Session) -> int:
    return session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name = :t AND is_compressed"
        ),
        {"t": TABLE},
    ).scalar_one()


def policies(session: Session) -> list[str]:
    return timescaledb.list_columnstore_policies(session)
