from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy.sql.functions import FunctionElement

from timescaledb.hyperfunctions import time_bucket, time_bucket_gapfill


def test_time_bucket_basic():
    """Test basic time_bucket functionality with timestamp."""
    ts = datetime.now(timezone.utc)
    bucket = time_bucket("5 minutes", ts)

    # Check the compiled SQL expression
    assert isinstance(bucket.compile().string, str)
    assert "time_bucket" in bucket.compile().string
    assert "interval" in bucket.compile().string.lower()


def test_time_bucket_with_integer():
    """Test time_bucket with integer bucket width and integer timestamp."""
    ts = 1_700_000_000
    bucket = time_bucket(300, ts)  # 5 minutes in seconds

    compiled = bucket.compile().string
    assert "interval" not in compiled.lower()
    params = bucket.compile().params
    assert 300 in params.values()
    assert ts in params.values()


def test_time_bucket_with_uuidv7():
    """Test time_bucket with a UUIDv7 timestamp value."""
    ts = UUID("0194214e-cd00-7000-a9a7-63f1416dab45")
    bucket = time_bucket("1 hour", ts)

    assert isinstance(bucket, FunctionElement)
    assert any(ts == value for value in bucket.compile().params.values())


def test_time_bucket_with_timezone():
    """Test time_bucket with timezone parameter."""
    ts = datetime.now(timezone.utc)
    bucket = time_bucket("1 hour", ts, timezone="UTC")

    # Check that the bucket is a SQL Function
    assert isinstance(bucket, FunctionElement)
    # Check parameters instead of compiled string
    params = bucket.compile().params
    assert any("UTC" in str(value) for value in params.values())


def test_time_bucket_with_origin():
    """Test time_bucket with origin parameter."""
    ts = datetime.now(timezone.utc)
    origin = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bucket = time_bucket("1 day", ts, origin=origin)

    # Check that the bucket is a SQL Function
    assert isinstance(bucket, FunctionElement)
    # Check parameters instead of compiled string
    params = bucket.compile().params
    assert any("2024-01-01" in str(value) for value in params.values())


def test_time_bucket_gapfill_basic():
    """Test basic time_bucket_gapfill functionality."""
    ts = datetime.now(timezone.utc)
    bucket = time_bucket_gapfill("1 hour", ts)

    compiled = bucket.compile().string
    assert "time_bucket_gapfill" in compiled
    assert "interval" in compiled.lower()


def test_time_bucket_gapfill_with_range():
    """Test time_bucket_gapfill with start and finish times."""
    ts = datetime.now(timezone.utc)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    finish = datetime(2024, 1, 2, tzinfo=timezone.utc)

    bucket = time_bucket_gapfill("1 hour", ts, start=start, finish=finish)

    compiled = bucket.compile().string
    assert "time_bucket_gapfill" in compiled
    assert "2024-01-01" in compiled
    assert "2024-01-02" in compiled


def test_time_bucket_gapfill_with_timezone():
    """Test time_bucket_gapfill with timezone parameter."""
    ts = datetime.now(timezone.utc)
    bucket = time_bucket_gapfill("1 hour", ts, timezone="UTC")

    compiled = bucket.compile().string
    assert "time_bucket_gapfill" in compiled
    assert "UTC" in compiled


def test_time_bucket_gapfill_with_integer():
    """Test time_bucket_gapfill with integer bucket width and integer range."""
    bucket = time_bucket_gapfill(300, 1_700_000_000, start=1, finish=900)

    compiled = bucket.compile()
    assert "interval" not in compiled.string.lower()
    assert 300 in compiled.params.values()
    assert 1 in compiled.params.values()
    assert 900 in compiled.params.values()


def test_integer_bucket_rejects_timezone():
    with pytest.raises(ValueError, match="timezone is not supported"):
        time_bucket(300, 1_700_000_000, timezone="UTC")

    with pytest.raises(ValueError, match="timezone is not supported"):
        time_bucket_gapfill(300, 1_700_000_000, timezone="UTC")
