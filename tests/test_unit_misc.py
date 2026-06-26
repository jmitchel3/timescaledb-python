"""Pure-unit tests for defaults, retention, hypertable, hyperfunction, and
query edge cases that close the remaining coverage gaps."""

from datetime import datetime
from typing import Optional

import pytest
import sqlmodel
from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field

from timescaledb.defaults import get_defaults
from timescaledb.exceptions import InvalidChunkTimeInterval
from timescaledb.hyperfunctions.main import time_bucket
from timescaledb.hypertables import sync as sync_module
from timescaledb.hypertables.create import create_hypertable
from timescaledb.hypertables.create_table import (
    create_table_with_hypertable,
    format_create_table_with_hypertable_sql,
)
from timescaledb.hypertables.schemas import HypertableCreateSchema
from timescaledb.hypertables.sync import sync_all_hypertables
from timescaledb.hypertables.validators import validate_chunk_time_interval
from timescaledb.queries import time_bucket_gapfill_query
from timescaledb.retention import sql as retention_sql
from timescaledb.retention.add import add_retention_policy
from timescaledb.retention.list import list_retention_policies
from timescaledb.retention.sync import sync_retention_policies

from .conftest import Metric, RetentionModel


class QueryRecorder:
    def __init__(self):
        self.queries = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query):
        self.queries.append(str(query))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FailingSession(QueryRecorder):
    def execute(self, query):
        raise SQLAlchemyError("boom")


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Begin:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class RetentionSession(QueryRecorder):
    """Fake session that supports begin() and list/add retention flows."""

    def __init__(self, existing_rows):
        super().__init__()
        self._existing_rows = existing_rows

    def begin(self):
        return _Begin()

    def execute(self, query):
        self.queries.append(str(query))
        return _Result(self._existing_rows)


class IsolatedSQLModel(sqlmodel.SQLModel):
    metadata = MetaData()


class PlainTimeModel(IsolatedSQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime)
    value: int


class IntTimeModel(IsolatedSQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    time: int = Field(primary_key=True)
    value: int


class NotATableModel(sqlmodel.SQLModel):
    foo: int


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------


def test_get_defaults_returns_mapping():
    defaults = get_defaults()
    assert defaults["TIME_COLUMN"] == "time"
    assert "CHUNK_TIME_INTERVAL" in defaults


# ---------------------------------------------------------------------------
# retention/sql
# ---------------------------------------------------------------------------


def test_format_retention_policy_requires_drop_after():
    with pytest.raises(ValueError, match="drop_after is required"):
        retention_sql.format_retention_policy_sql_query("t", drop_after=None)


def test_format_retention_policy_invalid_interval_type():
    with pytest.raises(ValueError, match="Invalid interval type"):
        retention_sql.format_retention_policy_sql_query("t", drop_after=1.5)


def test_get_retention_policy_sql_query():
    out = retention_sql.get_retention_policy_sql_query("metrics")
    assert "policy_retention" in out
    assert "metrics" in out


# ---------------------------------------------------------------------------
# retention add / list
# ---------------------------------------------------------------------------


def test_add_retention_policy_with_table_name():
    session = QueryRecorder()
    add_retention_policy(session, table_name="metrics", drop_after="1 year")
    assert "add_retention_policy" in session.queries[0]


def test_list_retention_policies_returns_none_when_no_rows():
    class NoneSession:
        def execute(self, query):
            return self

        def fetchall(self):
            return None

    assert list_retention_policies(NoneSession()) is None


# ---------------------------------------------------------------------------
# retention sync
# ---------------------------------------------------------------------------


def test_sync_retention_policies_skips_existing():
    table = RetentionModel.__tablename__
    session = RetentionSession(existing_rows=[(table,)])
    sync_retention_policies(session, RetentionModel)
    # policy already exists -> no add_retention_policy executed beyond the list query
    assert all("add_retention_policy" not in q for q in session.queries)


def test_sync_retention_policies_adds_when_missing():
    session = RetentionSession(existing_rows=None)
    sync_retention_policies(session, RetentionModel, drop_after="1 year")
    assert any("add_retention_policy" in q for q in session.queries)


# ---------------------------------------------------------------------------
# hypertables/create
# ---------------------------------------------------------------------------


def test_create_hypertable_requires_model_or_table_name():
    with pytest.raises(ValueError, match="model or table_name is required"):
        create_hypertable(QueryRecorder(), model=None, table_name=None)


def test_create_hypertable_overwrite_model_params():
    session = QueryRecorder()
    create_hypertable(
        session,
        model=Metric,
        hypertable_options={"if_not_exists": True, "migrate_data": True},
        overwrite_model_params=True,
    )
    assert session.commits == 1
    assert "create_hypertable" in session.queries[0]


# ---------------------------------------------------------------------------
# hypertables/create_table
# ---------------------------------------------------------------------------


def test_format_create_table_requires_table_model():
    with pytest.raises(ValueError, match="table=True"):
        format_create_table_with_hypertable_sql(NotATableModel)


def test_format_create_table_invalid_chunk_interval():
    with pytest.raises(ValueError, match="Invalid chunk interval"):
        format_create_table_with_hypertable_sql(Metric, chunk_interval=1.5)


def test_format_create_table_minimal_options():
    out = format_create_table_with_hypertable_sql(PlainTimeModel)
    assert "tsdb.hypertable" in out
    assert "tsdb.partition_column = 'time'" in out


def test_create_table_with_hypertable_without_commit():
    session = QueryRecorder()
    create_table_with_hypertable(session, model=PlainTimeModel, commit=False)
    assert session.commits == 0
    assert len(session.queries) == 1


# ---------------------------------------------------------------------------
# hypertables/schemas
# ---------------------------------------------------------------------------


def test_hypertable_schema_invalid_interval_type_raises():
    schema = HypertableCreateSchema(
        table_name="t", time_column="time", chunk_time_interval=1.5
    )
    with pytest.raises(ValueError, match="Invalid interval type"):
        schema.to_sql_query()


# ---------------------------------------------------------------------------
# hypertables/sync
# ---------------------------------------------------------------------------


def test_sync_all_hypertables_creates_missing(monkeypatch):
    monkeypatch.setattr(sync_module, "list_hypertables", lambda session: [])
    session = QueryRecorder()
    sync_all_hypertables(session, Metric)
    assert session.commits == 1
    assert any("create_hypertable" in q for q in session.queries)


def test_sync_all_hypertables_skips_existing(monkeypatch):
    existing = type("HT", (), {"hypertable_name": Metric.__tablename__})()
    monkeypatch.setattr(sync_module, "list_hypertables", lambda session: [existing])
    session = QueryRecorder()
    sync_all_hypertables(session, Metric)
    assert all("create_hypertable" not in q for q in session.queries)


def test_sync_all_hypertables_rolls_back_on_error(monkeypatch):
    monkeypatch.setattr(sync_module, "list_hypertables", lambda session: [])
    session = FailingSession()
    with pytest.raises(SQLAlchemyError):
        sync_all_hypertables(session, Metric)
    assert session.rollbacks == 1


# ---------------------------------------------------------------------------
# hypertables/validators
# ---------------------------------------------------------------------------


def test_validate_chunk_time_interval_integer_column_valid():
    validate_chunk_time_interval(IntTimeModel, "time", 1000)


def test_validate_chunk_time_interval_integer_column_invalid():
    with pytest.raises(InvalidChunkTimeInterval, match="must be an integer"):
        validate_chunk_time_interval(IntTimeModel, "time", "not-an-int")


def test_validate_chunk_time_interval_datetime_integer_invalid():
    class BadInt(int):
        def __int__(self):
            raise OverflowError("too big")

    with pytest.raises(InvalidChunkTimeInterval, match="must be an integer"):
        validate_chunk_time_interval(Metric, "time", BadInt(5))


def test_validate_chunk_time_interval_datetime_unhandled_type_is_noop():
    # A float is neither timedelta/int/str -> falls through without raising.
    assert validate_chunk_time_interval(Metric, "time", 1.5) is None


# ---------------------------------------------------------------------------
# hyperfunctions
# ---------------------------------------------------------------------------


def test_time_bucket_with_integer_offset():
    expr = time_bucket("5 minutes", Metric.time, offset=5)
    assert expr is not None


def test_time_bucket_with_interval_offset():
    expr = time_bucket("5 minutes", Metric.time, offset="1 hour")
    assert expr is not None


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------


class _FakeResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _CapturingSession:
    def exec(self, query):
        return _FakeResult()


def test_time_bucket_gapfill_query_accepts_instrumented_attributes():
    session = _CapturingSession()
    result = time_bucket_gapfill_query(
        session, Metric, time_field=Metric.time, metric_field=Metric.value
    )
    assert result == []
