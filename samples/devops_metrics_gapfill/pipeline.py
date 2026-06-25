"""Ingest sparse metrics and reconstruct an even time series with gapfill.

Real monitoring agents miss scrapes (restarts, network blips). Charting raw
buckets leaves holes; ``time_bucket_gapfill`` plus ``locf`` / ``interpolate``
produce the smooth, evenly-spaced series a dashboard expects.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import Engine
from sqlmodel import Session

import timescaledb
from samples._shared.db import create_tables
from samples.devops_metrics_gapfill.models import ServerMetric


def init_db(engine: Engine) -> None:
    create_tables(engine, ServerMetric)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=ServerMetric, commit=True)


def generate_sparse_metrics(
    host: str,
    start: datetime,
    minutes: int = 120,
    sample_every: int = 15,
    skip_buckets: tuple[int, ...] = (3, 4),
    bucket_minutes: int = 5,
) -> list[ServerMetric]:
    """Emit a reading every ``sample_every`` minutes, but punch a hole in it.

    ``skip_buckets`` lists 5-minute bucket indexes (relative to ``start``) that
    receive *no* data at all, simulating a monitoring outage. Bucketing at
    ``bucket_minutes`` then leaves visible gaps to fill.
    """
    rows: list[ServerMetric] = []
    offset = 0
    while offset <= minutes:
        bucket_index = offset // bucket_minutes
        if offset % sample_every == 0 and bucket_index not in skip_buckets:
            ts = start + timedelta(minutes=offset)
            cpu = 40 + 25 * math.sin(offset / 20.0)
            rows.append(
                ServerMetric(
                    time=ts,
                    host=host,
                    cpu_pct=round(cpu, 2),
                    mem_pct=round(55 + offset * 0.05, 2),
                )
            )
        offset += 1
    return rows


def insert_metrics(session: Session, metrics: list[ServerMetric]) -> int:
    session.add_all(metrics)
    session.commit()
    return len(metrics)


def cpu_series(
    session: Session,
    host: str,
    start: datetime,
    finish: datetime,
    interval: str = "5 minutes",
    use_locf: bool = False,
    use_interpolate: bool = False,
) -> list[dict]:
    """Bucketed CPU series, optionally gap-filled.

    * ``use_locf`` -> carry the last reading forward across the gap.
    * ``use_interpolate`` -> linearly interpolate across the gap.
    * neither -> empty buckets come back with ``avg = None``.
    """
    return timescaledb.time_bucket_gapfill_query(
        session,
        model=ServerMetric,
        interval=interval,
        time_field="time",
        metric_field="cpu_pct",
        start=start,
        finish=finish,
        use_locf=use_locf,
        use_interpolate=use_interpolate,
        filters=[ServerMetric.host == host],
    )


def utc(year, month, day, hour=0, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
