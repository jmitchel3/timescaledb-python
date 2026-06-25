from datetime import timedelta

import pytest
import sqlmodel
from sqlalchemy import MetaData
from sqlmodel import Field

from timescaledb.hypercore import (
    add_columnstore_policy,
    enable_columnstore,
    sync_columnstore_policies,
)
from timescaledb.hypercore.extractors import (
    extract_model_columnstore_params,
    extract_model_columnstore_policy_params,
)
from timescaledb.hypercore.sql import (
    format_add_columnstore_policy_sql_query,
    format_convert_to_columnstore_sql_query,
    format_convert_to_rowstore_sql_query,
    format_enable_columnstore_sql,
    format_remove_columnstore_policy_sql_query,
    list_columnstore_policies_sql_query,
)


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


class QueryRecorder:
    def __init__(self):
        self.queries = []
        self.commits = 0

    def execute(self, query):
        self.queries.append(str(query))

    def commit(self):
        self.commits += 1


def test_format_enable_columnstore_sql():
    query = format_enable_columnstore_sql(
        "public.metrics",
        orderby="time DESC",
        segmentby="device_id",
    )

    assert 'ALTER TABLE "public"."metrics" SET' in query
    assert "timescaledb.enable_columnstore = true" in query
    assert "timescaledb.orderby = 'time DESC'" in query
    assert "timescaledb.segmentby = 'device_id'" in query


def test_format_add_columnstore_policy_sql_with_interval():
    query = format_add_columnstore_policy_sql_query(
        "metrics",
        after="60 days",
        if_not_exists=True,
    )

    assert "CALL add_columnstore_policy" in query
    assert "'metrics'" in query
    assert "after => CAST('60 days' AS INTERVAL)" in query
    assert "if_not_exists => true" in query


def test_format_add_columnstore_policy_sql_with_timedelta():
    query = format_add_columnstore_policy_sql_query(
        "metrics",
        after=timedelta(days=1),
    )

    assert "after => CAST('86400 seconds' AS INTERVAL)" in query


def test_format_add_columnstore_policy_sql_with_integer_time():
    query = format_add_columnstore_policy_sql_query("metrics", after=600000)

    assert "after => CAST(600000 AS BIGINT)" in query


def test_format_add_columnstore_policy_requires_one_age_selector():
    with pytest.raises(ValueError, match="exactly one"):
        format_add_columnstore_policy_sql_query("metrics")

    with pytest.raises(ValueError, match="exactly one"):
        format_add_columnstore_policy_sql_query(
            "metrics",
            after="60 days",
            created_before="3 months",
        )


def test_format_columnstore_management_sql():
    assert "CALL remove_columnstore_policy" in format_remove_columnstore_policy_sql_query(
        "metrics"
    )
    assert "CALL convert_to_columnstore" in format_convert_to_columnstore_sql_query(
        "_timescaledb_internal._hyper_1_2_chunk"
    )
    assert "CALL convert_to_rowstore" in format_convert_to_rowstore_sql_query(
        "_timescaledb_internal._hyper_1_2_chunk"
    )
    assert "application_name LIKE 'Columnstore%'" in list_columnstore_policies_sql_query()


def test_extract_model_columnstore_params():
    params = extract_model_columnstore_params(ColumnstoreMetric)

    assert params["table_name"] == ColumnstoreMetric.__tablename__
    assert params["columnstore_enabled"] is True
    assert params["orderby"] == "time DESC"
    assert params["segmentby"] == "device_id"


def test_extract_model_columnstore_policy_params():
    params = extract_model_columnstore_policy_params(ColumnstoreMetric)

    assert params["after"] == "7 days"
    assert params["if_not_exists"] is True


def test_enable_columnstore_executes_generated_sql():
    session = QueryRecorder()

    enable_columnstore(session, model=ColumnstoreMetric)

    assert session.commits == 1
    assert "timescaledb.enable_columnstore = true" in session.queries[0]


def test_add_columnstore_policy_executes_generated_sql():
    session = QueryRecorder()

    add_columnstore_policy(session, model=ColumnstoreMetric)

    assert session.commits == 1
    assert "CALL add_columnstore_policy" in session.queries[0]
    assert "after => CAST('7 days' AS INTERVAL)" in session.queries[0]


def test_sync_columnstore_policies_uses_opted_in_models():
    session = QueryRecorder()

    sync_columnstore_policies(session, ColumnstoreMetric)

    assert session.commits == 1
    assert len(session.queries) == 2
    assert "timescaledb.enable_columnstore = true" in session.queries[0]
    assert "CALL add_columnstore_policy" in session.queries[1]
