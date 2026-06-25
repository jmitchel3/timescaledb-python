"""Tests for the full-lifecycle capstone sample."""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from samples.weather_lifecycle_full.pipeline import (
    convert_cold_chunks,
    generate_readings,
    hourly_rollup,
    init_db,
    insert_readings,
    lifecycle_summary,
    refresh_hourly,
    temp_gapfilled,
)

END = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _seed(engine):
    init_db(engine)
    readings = generate_readings(stations=3, days=14, end=END)
    start = readings[0].time  # capture before commit expires the ORM objects
    with Session(engine) as session:
        insert_readings(session, readings)
    refresh_hourly(engine)
    return start


def test_every_lifecycle_feature_is_configured(engine):
    _seed(engine)
    with Session(engine) as session:
        converted = convert_cold_chunks(session)
        summary = lifecycle_summary(session)

    assert summary["is_hypertable"] is True
    assert "station_readings" in summary["columnstore_policies"]
    assert summary["retention_jobs"] == 1
    assert converted > 0
    assert summary["columnstore_chunks"] == converted


def test_continuous_aggregate_populated(engine):
    _seed(engine)
    with Session(engine) as session:
        rollup = hourly_rollup(session, station_id=1)
    assert rollup
    # 14 days hourly -> ~336 buckets for one station.
    assert 320 <= len(rollup) <= 340
    for row in rollup:
        assert row["max_wind"] >= 0


def test_gapfilled_series_is_evenly_spaced(engine):
    start = _seed(engine)
    finish = start + timedelta(days=1)
    with Session(engine) as session:
        filled = temp_gapfilled(session, 1, start, finish, interval="1 hour")
    # One point per hour across a full day (inclusive) -> 25 points, all filled.
    assert len(filled) == 25
    assert all(row["avg"] is not None for row in filled)
