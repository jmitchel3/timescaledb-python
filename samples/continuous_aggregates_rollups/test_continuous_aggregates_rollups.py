"""Tests for the continuous aggregates sample."""

from datetime import datetime, timezone

from sqlmodel import Session

from samples.continuous_aggregates_rollups.pipeline import (
    daily_rollup,
    generate_conditions,
    hourly_rollup,
    init_db,
    insert_conditions,
    refresh_all,
)

END = datetime(2026, 1, 6, tzinfo=timezone.utc)


def _seed(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_conditions(session, generate_conditions(days=5, end=END))
    refresh_all(engine)


def test_hourly_aggregate_materializes(engine):
    _seed(engine)
    rows = hourly_rollup(engine, location="nyc")
    assert rows
    # 5 days of hourly buckets for one location -> ~120 buckets.
    assert 110 <= len(rows) <= 122
    for row in rows:
        assert row["min_temp"] <= row["avg_temp"] <= row["max_temp"]


def test_daily_rolls_up_hourly(engine):
    _seed(engine)
    hourly = hourly_rollup(engine, location="nyc")
    daily = daily_rollup(engine, location="nyc")
    assert daily
    # Daily must be far coarser than hourly.
    assert len(daily) < len(hourly)
    assert len(daily) <= 6
    for row in daily:
        assert row["min_temp"] <= row["avg_temp"] <= row["max_temp"]


def test_all_locations_present(engine):
    _seed(engine)
    rows = daily_rollup(engine)
    locations = {r["location"] for r in rows}
    assert locations == {"nyc", "sf", "london"}
