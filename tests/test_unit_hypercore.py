"""Pure-unit tests for the hypercore (columnstore) subpackage."""

from datetime import datetime, timedelta

import pytest
import sqlmodel
from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field

from timescaledb.hypercore import extractors, sql
from timescaledb.hypercore.add import add_columnstore_policy
from timescaledb.hypercore.convert import (
    convert_to_columnstore,
    convert_to_rowstore,
)
from timescaledb.hypercore.enable import enable_columnstore
from timescaledb.hypercore.list import list_columnstore_policies
from timescaledb.hypercore.remove import remove_columnstore_policy
from timescaledb.hypercore.sync import sync_columnstore_policies

from .conftest import Metric


class IsolatedSQLModel(sqlmodel.SQLModel):
    metadata = MetaData()


class ColumnstoreMetric(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    device_id: int = Field(index=True)
    value: float

    __enable_columnstore__ = True
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "device_id"
    __columnstore_after__ = "7 days"
    __columnstore_if_not_exists__ = True


class ColumnstoreNoAge(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    value: float

    __enable_columnstore__ = True


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


class FetchSession:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query):
        return self

    def fetchall(self):
        return self._rows


# ---------------------------------------------------------------------------
# add_columnstore_policy
# ---------------------------------------------------------------------------


def test_add_columnstore_policy_requires_model_or_table_name():
    with pytest.raises(ValueError, match="model or table_name is required"):
        add_columnstore_policy(QueryRecorder(), model=None, table_name=None)


def test_add_columnstore_policy_disabled_model_is_noop():
    session = QueryRecorder()
    add_columnstore_policy(session, model=Metric)
    assert session.queries == []


def test_add_columnstore_policy_enabled_model_without_age_is_noop():
    session = QueryRecorder()
    add_columnstore_policy(session, model=ColumnstoreNoAge)
    assert session.queries == []


def test_add_columnstore_policy_with_table_name():
    session = QueryRecorder()
    add_columnstore_policy(session, table_name="metrics", after="7 days")
    assert session.commits == 1
    assert "add_columnstore_policy" in session.queries[0]


# ---------------------------------------------------------------------------
# enable_columnstore
# ---------------------------------------------------------------------------


def test_enable_columnstore_requires_model_or_table_name():
    with pytest.raises(ValueError, match="model or table_name is required"):
        enable_columnstore(QueryRecorder(), model=None, table_name=None)


def test_enable_columnstore_disabled_model_is_noop():
    session = QueryRecorder()
    enable_columnstore(session, model=Metric)
    assert session.queries == []


def test_enable_columnstore_model_fills_orderby_segmentby():
    session = QueryRecorder()
    enable_columnstore(session, model=ColumnstoreMetric)
    assert session.commits == 1
    assert "timescaledb.orderby" in session.queries[0]
    assert "timescaledb.segmentby" in session.queries[0]


def test_enable_columnstore_model_with_explicit_orderby_segmentby():
    session = QueryRecorder()
    enable_columnstore(
        session, model=ColumnstoreMetric, orderby="value DESC", segmentby="value"
    )
    assert session.commits == 1
    assert "value DESC" in session.queries[0]


def test_enable_columnstore_with_table_name():
    session = QueryRecorder()
    enable_columnstore(
        session, table_name="metrics", orderby="time DESC", segmentby="device_id"
    )
    assert session.commits == 1
    assert "timescaledb.enable_columnstore = true" in session.queries[0]


# ---------------------------------------------------------------------------
# convert helpers
# ---------------------------------------------------------------------------


def test_convert_to_columnstore_commits():
    session = QueryRecorder()
    convert_to_columnstore(session, "_chunk")
    assert session.commits == 1
    assert "convert_to_columnstore" in session.queries[0]


def test_convert_to_columnstore_without_commit():
    session = QueryRecorder()
    convert_to_columnstore(session, "_chunk", commit=False)
    assert session.commits == 0
    assert len(session.queries) == 1


def test_convert_to_rowstore_commits():
    session = QueryRecorder()
    convert_to_rowstore(session, "_chunk")
    assert session.commits == 1
    assert "convert_to_rowstore" in session.queries[0]


def test_convert_to_rowstore_without_commit():
    session = QueryRecorder()
    convert_to_rowstore(session, "_chunk", commit=False)
    assert session.commits == 0
    assert len(session.queries) == 1


# ---------------------------------------------------------------------------
# list / remove
# ---------------------------------------------------------------------------


def test_list_columnstore_policies():
    session = FetchSession([("metrics",), ("views",)])
    assert list_columnstore_policies(session) == ["metrics", "views"]


def test_remove_columnstore_policy_commits():
    session = QueryRecorder()
    remove_columnstore_policy(session, "metrics")
    assert session.commits == 1
    assert "remove_columnstore_policy" in session.queries[0]


def test_remove_columnstore_policy_without_commit():
    session = QueryRecorder()
    remove_columnstore_policy(session, "metrics", commit=False)
    assert session.commits == 0


# ---------------------------------------------------------------------------
# sync_columnstore_policies
# ---------------------------------------------------------------------------


def test_sync_columnstore_policies_rolls_back_on_error():
    session = FailingSession()
    with pytest.raises(SQLAlchemyError):
        sync_columnstore_policies(session, ColumnstoreMetric)
    assert session.rollbacks == 1


# ---------------------------------------------------------------------------
# extractors
# ---------------------------------------------------------------------------


def test_extract_columnstore_params_returns_none_when_disabled():
    assert extractors.extract_model_columnstore_params(Metric) is None


def test_extract_columnstore_policy_params_returns_none_when_disabled():
    assert extractors.extract_model_columnstore_policy_params(Metric) is None


def test_extract_columnstore_params_without_orderby_segmentby():
    params = extractors.extract_model_columnstore_params(ColumnstoreNoAge)
    assert params["columnstore_enabled"] is True
    assert "orderby" not in params
    assert "segmentby" not in params


# ---------------------------------------------------------------------------
# sql helpers
# ---------------------------------------------------------------------------


def test_quote_qualified_identifier_requires_value():
    with pytest.raises(ValueError, match="identifier is required"):
        sql.quote_qualified_identifier("")


def test_clean_interval_value_invalid_type():
    assert sql._clean_interval_value(1.5) == (1.5, "INVALID")


def test_clean_interval_value_fractional_timedelta():
    assert sql._clean_interval_value(timedelta(milliseconds=1500)) == (
        "1.5 seconds",
        "INTERVAL",
    )


def test_policy_interval_sql_invalid_type_raises():
    with pytest.raises(ValueError, match="Invalid interval type"):
        sql._policy_interval_sql("after", 1.5, allow_integer=True)


def test_policy_interval_sql_integer_not_allowed_raises():
    with pytest.raises(ValueError, match="Invalid interval type"):
        sql._policy_interval_sql("created_before", 5, allow_integer=False)


def test_compile_sql_without_params():
    out = sql._compile_sql("SELECT 1")
    assert "SELECT 1" in out


def test_format_enable_columnstore_sql_without_orderby_segmentby():
    out = sql.format_enable_columnstore_sql("metrics")
    assert "timescaledb.enable_columnstore = true" in out
    assert "timescaledb.orderby" not in out
    assert "timescaledb.segmentby" not in out


def test_format_add_columnstore_policy_with_all_options():
    out = sql.format_add_columnstore_policy_sql_query(
        "metrics",
        created_before="3 months",
        schedule_interval="1 hour",
        initial_start=datetime(2024, 1, 1),
        timezone="UTC",
        if_not_exists=True,
    )
    assert "created_before => CAST('3 months' AS INTERVAL)" in out
    assert "schedule_interval => CAST('1 hour' AS INTERVAL)" in out
    assert "initial_start =>" in out
    assert "timezone => 'UTC'" in out
