"""Tests for the manual-hypertable GPS sample."""

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from samples.fleet_gps_tracking.models import GpsPing
from samples.fleet_gps_tracking.pipeline import (
    downsample_speed,
    generate_pings,
    init_db,
    insert_pings,
    is_hypertable,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_manual_create_hypertable(engine):
    init_db(engine)
    with Session(engine) as session:
        assert is_hypertable(session) is True


def test_downsampling_collapses_rows(engine):
    init_db(engine)
    with Session(engine) as session:
        # 60 minutes @ 10s = 360 pings per vehicle.
        insert_pings(session, generate_pings(vehicles=3, minutes=60, start=START))
        raw_for_v1 = session.exec(
            select(func.count()).select_from(GpsPing).where(GpsPing.vehicle_id == 1)
        ).one()
        buckets = downsample_speed(session, vehicle_id=1, interval="1 minute")

    assert raw_for_v1 == 360
    # Downsampled to one row per minute -> ~60 buckets, far fewer than raw.
    assert len(buckets) == 60
    for row in buckets:
        assert row["max_speed"] >= row["avg_speed"]
        assert row["avg_speed"] >= 0
