"""Tests for the clickstream + retention sample."""

from datetime import datetime, timezone

from sqlmodel import Session

from samples.ecommerce_clickstream_retention.pipeline import (
    EVENT_TYPES,
    events_per_bucket,
    funnel_totals,
    generate_events,
    init_db,
    insert_events,
    retention_policy_count,
)

END = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_retention_policy_is_registered(engine):
    init_db(engine, drop_after="30 days")
    with Session(engine) as session:
        assert retention_policy_count(session) == 1


def test_funnel_narrows_toward_purchase(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_events(session, generate_events(count=3000, hours=12, end=END))
        totals = funnel_totals(session)

    assert sum(totals.values()) == 3000
    assert set(totals) <= set(EVENT_TYPES)
    # Weighted generation => far more views than purchases.
    assert totals["view"] > totals["purchase"]


def test_events_per_bucket_split_by_type(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_events(session, generate_events(count=1000, hours=6, end=END))
        rows = events_per_bucket(session, interval="1 hour")

    assert rows
    assert {"bucket", "event_type", "events"} <= set(rows[0].keys())
    # Every row is one event_type's count in one bucket; totals reconcile.
    assert sum(r["events"] for r in rows) == 1000
