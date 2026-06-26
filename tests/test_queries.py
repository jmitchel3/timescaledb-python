"""Pure-unit tests for timescaledb.queries SQL builders.

These tests do NOT require a live database. They use a lightweight capturing
fake session that records the SQLAlchemy ``select`` construct passed to
``session.exec`` and returns an empty result, so the generated SQL can be
compiled and asserted on directly.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from timescaledb.queries import time_bucket_gapfill_query, time_bucket_query

from .conftest import Metric


class _FakeResult:
    """Mimics the object returned by ``session.exec``."""

    def mappings(self):
        return self

    def all(self):
        return []


class _CapturingSession:
    """Captures the query handed to ``exec`` without touching a database."""

    def __init__(self):
        self.last_query = None

    def exec(self, query):
        self.last_query = query
        return _FakeResult()


def _compile(query) -> str:
    """Compile a query to a PostgreSQL SQL string."""
    return str(query.compile(dialect=postgresql.dialect()))


# ---------------------------------------------------------------------------
# time_bucket_query
# ---------------------------------------------------------------------------


def test_time_bucket_query_returns_list():
    session = _CapturingSession()
    result = time_bucket_query(session, Metric, metric_field="value")
    assert result == []


def test_time_bucket_query_builds_time_bucket_sql():
    session = _CapturingSession()
    time_bucket_query(session, Metric, interval="1 hour", metric_field="value")
    sql = _compile(session.last_query)

    assert "time_bucket(INTERVAL '1 hour', metric.time)" in sql
    assert "AS bucket" in sql
    assert "GROUP BY" in sql
    # Default ordering is descending on the bucket
    assert "ORDER BY" in sql
    assert "DESC" in sql


def test_time_bucket_query_rounds_average_by_default():
    """round_to_nearest=True wraps avg in round()/cast()."""
    session = _CapturingSession()
    time_bucket_query(session, Metric, metric_field="value")
    sql = _compile(session.last_query)

    assert "avg(metric.value)" in sql
    assert "round(" in sql
    assert "NUMERIC" in sql
    assert "AS avg" in sql


def test_time_bucket_query_without_rounding():
    """round_to_nearest=False produces a plain avg()."""
    session = _CapturingSession()
    time_bucket_query(
        session, Metric, metric_field="value", round_to_nearest=False
    )
    sql = _compile(session.last_query)

    assert "avg(metric.value)" in sql
    assert "round(" not in sql


def test_time_bucket_query_accepts_instrumented_attributes():
    """time_field / metric_field may be passed as model attributes."""
    session = _CapturingSession()
    time_bucket_query(
        session, Metric, time_field=Metric.time, metric_field=Metric.value
    )
    sql = _compile(session.last_query)

    assert "time_bucket(INTERVAL '1 hour', metric.time)" in sql
    assert "avg(metric.value)" in sql


def test_time_bucket_query_applies_filters():
    session = _CapturingSession()
    time_bucket_query(
        session,
        Metric,
        metric_field="value",
        filters=[Metric.value > 10],
    )
    sql = _compile(session.last_query)

    assert "WHERE" in sql
    assert "metric.value >" in sql


def test_time_bucket_query_missing_metric_field_raises():
    session = _CapturingSession()
    with pytest.raises(ValueError, match="not found in model Metric"):
        time_bucket_query(session, Metric, metric_field="does_not_exist")


def test_time_bucket_query_missing_time_field_raises():
    session = _CapturingSession()
    with pytest.raises(ValueError, match="not found in model Metric"):
        time_bucket_query(
            session, Metric, time_field="nope", metric_field="value"
        )


# ---------------------------------------------------------------------------
# time_bucket_gapfill_query
# ---------------------------------------------------------------------------


def test_time_bucket_gapfill_query_returns_list():
    session = _CapturingSession()
    result = time_bucket_gapfill_query(session, Metric, metric_field="value")
    assert result == []


def test_time_bucket_gapfill_query_basic_sql():
    session = _CapturingSession()
    time_bucket_gapfill_query(
        session, Metric, interval="1 hour", metric_field="value"
    )
    sql = _compile(session.last_query)

    assert "time_bucket_gapfill(INTERVAL '1 hour', metric.time" in sql
    assert "avg(metric.value)" in sql
    assert "AS bucket" in sql
    assert "AS avg" in sql
    # Gapfill orders ascending on the bucket label
    assert "ORDER BY bucket ASC" in sql


def test_time_bucket_gapfill_query_with_locf():
    session = _CapturingSession()
    time_bucket_gapfill_query(
        session, Metric, metric_field="value", use_locf=True
    )
    sql = _compile(session.last_query)

    assert "locf(avg(metric.value))" in sql
    assert "interpolate(" not in sql


def test_time_bucket_gapfill_query_with_interpolate():
    session = _CapturingSession()
    time_bucket_gapfill_query(
        session, Metric, metric_field="value", use_interpolate=True
    )
    sql = _compile(session.last_query)

    assert "interpolate(avg(metric.value))" in sql
    assert "locf(" not in sql


def test_time_bucket_gapfill_query_without_strategy_is_plain_avg():
    session = _CapturingSession()
    time_bucket_gapfill_query(session, Metric, metric_field="value")
    sql = _compile(session.last_query)

    assert "avg(metric.value)" in sql
    assert "locf(" not in sql
    assert "interpolate(" not in sql


def test_time_bucket_gapfill_query_with_range_adds_filters():
    session = _CapturingSession()
    start = datetime(2024, 1, 1)
    finish = datetime(2024, 1, 2)
    time_bucket_gapfill_query(
        session,
        Metric,
        metric_field="value",
        start=start,
        finish=finish,
    )
    sql = _compile(session.last_query)

    assert "WHERE" in sql
    assert "metric.time >=" in sql
    assert "metric.time <=" in sql
    # start/finish are embedded into the gapfill call as literals
    assert "2024-01-01 00:00:00" in sql
    assert "2024-01-02 00:00:00" in sql


def test_time_bucket_gapfill_query_strips_timezone_from_bounds():
    """Aware datetimes should be coerced to naive ones in the SQL literals."""
    session = _CapturingSession()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    finish = datetime(2024, 1, 2, tzinfo=timezone.utc)
    time_bucket_gapfill_query(
        session,
        Metric,
        metric_field="value",
        start=start,
        finish=finish,
    )
    sql = _compile(session.last_query)

    # No timezone offset should remain in the embedded literals
    assert "2024-01-01 00:00:00" in sql
    assert "+00:00" not in sql


def test_time_bucket_gapfill_query_custom_labels():
    session = _CapturingSession()
    time_bucket_gapfill_query(
        session,
        Metric,
        metric_field="value",
        bucket_label="ts",
        value_label="mean",
    )
    sql = _compile(session.last_query)

    assert "AS ts" in sql
    assert "AS mean" in sql
    assert "ORDER BY ts ASC" in sql


def test_time_bucket_gapfill_query_finish_before_start_raises():
    session = _CapturingSession()
    start = datetime(2024, 1, 2)
    finish = datetime(2024, 1, 1)
    with pytest.raises(ValueError, match="Finish time must be after start time"):
        time_bucket_gapfill_query(
            session,
            Metric,
            metric_field="value",
            start=start,
            finish=finish,
        )


def test_time_bucket_gapfill_query_missing_metric_field_raises():
    session = _CapturingSession()
    with pytest.raises(ValueError, match="not found in model Metric"):
        time_bucket_gapfill_query(
            session, Metric, metric_field="does_not_exist"
        )


def test_time_bucket_gapfill_query_missing_time_field_raises():
    session = _CapturingSession()
    with pytest.raises(ValueError, match="not found in model Metric"):
        time_bucket_gapfill_query(
            session, Metric, time_field="nope", metric_field="value"
        )
