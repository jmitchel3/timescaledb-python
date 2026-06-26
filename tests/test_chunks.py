from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session

from timescaledb import drop_chunks, show_chunks
from timescaledb.chunks import sql
from timescaledb.chunks.utils import resolve_table_name
from timescaledb.utils import get_utc_now

from .conftest import Metric


def _seed_chunks(session: Session) -> None:
    """Insert rows spaced well apart so the default 7-day chunk interval
    produces several distinct chunks."""
    now = get_utc_now()
    for days in (0, 30, 60, 90):
        session.add(
            Metric(
                sensor_id=1,
                value=float(days),
                time=now - timedelta(days=days),
            )
        )
    session.commit()


# ---------------------------------------------------------------------------
# Integration tests (require the TimescaleDB container)
# ---------------------------------------------------------------------------


def test_show_chunks_empty(session: Session):
    """A hypertable with no data has no chunks."""
    assert show_chunks(session, Metric.__tablename__) == []


def test_show_chunks_returns_all_chunks(session: Session):
    _seed_chunks(session)
    chunks = show_chunks(session, Metric.__tablename__)
    assert len(chunks) == 4
    assert all(isinstance(name, str) for name in chunks)
    assert all("_hyper_" in name for name in chunks)


def test_show_chunks_with_model(session: Session):
    _seed_chunks(session)
    by_name = show_chunks(session, table_name=Metric.__tablename__)
    by_model = show_chunks(session, model=Metric)
    assert by_model == by_name
    assert len(by_model) == 4


def test_show_chunks_older_than_interval(session: Session):
    _seed_chunks(session)
    # Chunks holding the -60d and -90d rows are fully older than 45 days.
    older = show_chunks(session, Metric.__tablename__, older_than="45 days")
    assert len(older) == 2
    assert set(older).issubset(set(show_chunks(session, Metric.__tablename__)))


def test_show_chunks_newer_than_interval(session: Session):
    _seed_chunks(session)
    newer = show_chunks(session, Metric.__tablename__, newer_than="45 days")
    assert len(newer) == 2


def test_show_chunks_older_than_datetime(session: Session):
    _seed_chunks(session)
    cutoff = get_utc_now() - timedelta(days=45)
    older = show_chunks(session, Metric.__tablename__, older_than=cutoff)
    assert len(older) == 2


def test_show_chunks_older_than_timedelta(session: Session):
    _seed_chunks(session)
    older = show_chunks(
        session, Metric.__tablename__, older_than=timedelta(days=45)
    )
    assert len(older) == 2


def test_show_chunks_created_after_and_before(session: Session):
    _seed_chunks(session)
    # All chunks were just created, so everything is "created after 1 hour ago"
    # and nothing is "created before 1 hour ago".
    assert len(show_chunks(session, Metric.__tablename__, created_after="1 hour")) == 4
    assert show_chunks(session, Metric.__tablename__, created_before="1 hour") == []


def test_drop_chunks_older_than_interval(session: Session):
    _seed_chunks(session)
    assert len(show_chunks(session, Metric.__tablename__)) == 4

    dropped = drop_chunks(session, Metric.__tablename__, older_than="45 days")
    session.commit()
    assert len(dropped) == 2
    assert all("_hyper_" in name for name in dropped)

    remaining = show_chunks(session, Metric.__tablename__)
    assert len(remaining) == 2
    assert not set(dropped).intersection(set(remaining))


def test_drop_chunks_with_model_and_timedelta(session: Session):
    _seed_chunks(session)
    dropped = drop_chunks(session, model=Metric, older_than=timedelta(days=45))
    session.commit()
    assert len(dropped) == 2


def test_drop_chunks_requires_a_range_bound(session: Session):
    _seed_chunks(session)
    with pytest.raises(ValueError):
        drop_chunks(session, Metric.__tablename__)
    # Nothing should have been dropped.
    assert len(show_chunks(session, Metric.__tablename__)) == 4


# ---------------------------------------------------------------------------
# Unit tests for the SQL builders (no database required)
# ---------------------------------------------------------------------------


def test_render_chunk_arg_datetime():
    fragment, params = sql._render_chunk_arg("older_than", datetime(2024, 1, 1))
    assert "CAST(:older_than AS timestamptz)" in fragment
    assert params["older_than"] == "2024-01-01T00:00:00"


def test_render_chunk_arg_date():
    fragment, params = sql._render_chunk_arg("newer_than", date(2024, 1, 1))
    assert "CAST(:newer_than AS timestamptz)" in fragment
    assert params["newer_than"] == "2024-01-01"


def test_render_chunk_arg_timedelta():
    fragment, params = sql._render_chunk_arg("older_than", timedelta(days=1))
    assert "make_interval(secs => :older_than)" in fragment
    assert params["older_than"] == 86400.0


def test_render_chunk_arg_int():
    fragment, params = sql._render_chunk_arg("older_than", 100)
    assert fragment == "older_than => :older_than"
    assert params["older_than"] == 100


def test_render_chunk_arg_int_rejected_for_created_bounds():
    with pytest.raises(ValueError, match="created_after does not support integer"):
        sql._render_chunk_arg("created_after", 100)


def test_render_chunk_arg_str_strips_interval_keyword_and_quotes():
    fragment, params = sql._render_chunk_arg("older_than", "INTERVAL '3 days'")
    assert fragment == "older_than => INTERVAL :older_than"
    assert params["older_than"] == "3 days"


def test_render_chunk_arg_bool_raises():
    with pytest.raises(ValueError):
        sql._render_chunk_arg("older_than", True)


def test_render_chunk_arg_unsupported_type_raises():
    with pytest.raises(ValueError):
        sql._render_chunk_arg("older_than", [1, 2, 3])


def test_format_show_chunks_sql_no_args():
    query = sql.format_show_chunks_sql("metrics")
    assert query == "SELECT show_chunks('metrics');"


def test_format_show_chunks_sql_with_all_range_args():
    query = sql.format_show_chunks_sql(
        "metrics",
        older_than="30 days",
        newer_than="90 days",
        created_before=datetime(2024, 1, 1),
        created_after="1 hour",
    )
    assert query.startswith("SELECT show_chunks('metrics'")
    assert "older_than => INTERVAL '30 days'" in query
    assert "newer_than => INTERVAL '90 days'" in query
    assert "created_before => CAST('2024-01-01T00:00:00' AS timestamptz)" in query
    assert "created_after => INTERVAL '1 hour'" in query


def test_format_chunks_sql_requires_table_name():
    with pytest.raises(ValueError):
        sql.format_show_chunks_sql("")


def test_format_drop_chunks_sql_requires_range():
    with pytest.raises(ValueError):
        sql.format_drop_chunks_sql("metrics")


def test_format_drop_chunks_sql_with_range():
    query = sql.format_drop_chunks_sql("metrics", older_than="30 days")
    assert query == "SELECT drop_chunks('metrics', older_than => INTERVAL '30 days');"


def test_resolve_table_name_from_model():
    assert resolve_table_name(model=Metric) == Metric.__tablename__


def test_resolve_table_name_from_table_name():
    assert resolve_table_name(table_name="metrics") == "metrics"


def test_resolve_table_name_requires_one():
    with pytest.raises(ValueError):
        resolve_table_name()
