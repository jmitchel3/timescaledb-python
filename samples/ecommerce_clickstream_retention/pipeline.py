"""Ingest clickstream events, roll them up by type, and manage retention.

Highlights:

* ``add_retention_policy`` registers an automatic drop-old-chunks job so the
  raw, high-volume event table never grows unbounded.
* ``events_per_bucket`` groups by ``time_bucket`` *and* ``event_type`` to build
  the kind of funnel chart an analytics dashboard needs.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

import timescaledb
from samples._shared.db import create_tables
from samples.ecommerce_clickstream_retention.models import ClickEvent
from timescaledb.hyperfunctions import time_bucket

TABLE = "ecommerce_click_events"
EVENT_TYPES = ("view", "add_to_cart", "checkout", "purchase")
PATHS = ("/", "/products", "/products/42", "/cart", "/checkout")


def init_db(engine: Engine, drop_after: str = "30 days") -> None:
    create_tables(engine, ClickEvent)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=ClickEvent, commit=True)
        timescaledb.add_retention_policy(session, table_name=TABLE, drop_after=drop_after)
        session.commit()


def generate_events(
    count: int = 2000,
    hours: int = 12,
    end: datetime | None = None,
    seed: int = 5,
) -> list[ClickEvent]:
    """Generate a realistic funnel: lots of views, fewer purchases."""
    rng = random.Random(seed)
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    span = (end - start).total_seconds()
    # Weighted so the funnel narrows toward purchase.
    weights = [0.6, 0.2, 0.12, 0.08]

    rows: list[ClickEvent] = []
    for _ in range(count):
        ts = start + timedelta(seconds=rng.uniform(0, span))
        event_type = rng.choices(EVENT_TYPES, weights=weights)[0]
        rows.append(
            ClickEvent(
                time=ts,
                event_type=event_type,
                user_id=rng.randint(1, 250),
                path=rng.choice(PATHS),
            )
        )
    return rows


def insert_events(session: Session, events: list[ClickEvent]) -> int:
    session.add_all(events)
    session.commit()
    return len(events)


def events_per_bucket(session: Session, interval: str = "1 hour") -> list[dict]:
    """Count events per (bucket, event_type)."""
    bucket = time_bucket(interval, ClickEvent.time)
    query = (
        select(
            bucket.label("bucket"),
            ClickEvent.event_type,
            func.count().label("events"),
        )
        .group_by(bucket, ClickEvent.event_type)
        .order_by(bucket, ClickEvent.event_type)
    )
    return list(session.exec(query).mappings().all())


def funnel_totals(session: Session) -> dict[str, int]:
    """Total events per type (the overall funnel)."""
    rows = session.exec(
        select(ClickEvent.event_type, func.count())
        .group_by(ClickEvent.event_type)
    ).all()
    return {event_type: count for event_type, count in rows}


def retention_policy_count(session: Session) -> int:
    return session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM timescaledb_information.jobs "
            "WHERE hypertable_name = :t AND proc_name = 'policy_retention'"
        ),
        {"t": TABLE},
    ).scalar_one()
