from datetime import datetime

import pytest
import sqlmodel
from sqlalchemy import MetaData
from sqlmodel import Field

from timescaledb.hypertables import (
    create_table_with_hypertable,
    format_create_table_with_hypertable_sql,
)


class IsolatedSQLModel(sqlmodel.SQLModel):
    metadata = MetaData()


class DirectHypertableMetric(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(
        sa_type=sqlmodel.DateTime(timezone=True),
        primary_key=True,
    )
    device_id: int = Field(index=True)
    value: float

    __tablename__ = "direct_hypertable_metrics"
    __chunk_time_interval__ = "INTERVAL 7 days"
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "device_id"


class IntegerTimeHypertable(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    value: float

    __tablename__ = "integer_time_hypertable"


class QueryRecorder:
    def __init__(self):
        self.queries = []
        self.commits = 0

    def execute(self, query):
        self.queries.append(str(query))

    def commit(self):
        self.commits += 1


def test_format_create_table_with_hypertable_sql_from_model_defaults():
    query = format_create_table_with_hypertable_sql(DirectHypertableMetric)

    assert "CREATE TABLE IF NOT EXISTS direct_hypertable_metrics" in query
    assert "WITH (tsdb.hypertable" in query
    assert "tsdb.partition_column = 'time'" in query
    assert "tsdb.chunk_interval = '7 days'" in query
    assert "tsdb.segmentby = 'device_id'" in query
    assert "tsdb.orderby = 'time DESC'" in query


def test_format_create_table_with_hypertable_sql_with_integer_chunk_interval():
    query = format_create_table_with_hypertable_sql(
        IntegerTimeHypertable,
        chunk_interval=1000,
        create_default_indexes=False,
    )

    assert "tsdb.chunk_interval = 1000" in query
    assert "tsdb.create_default_indexes = false" in query


def test_create_table_with_hypertable_executes_generated_sql():
    session = QueryRecorder()

    create_table_with_hypertable(
        session,
        DirectHypertableMetric,
        chunk_interval="1 day",
    )

    assert session.commits == 1
    assert "CREATE TABLE IF NOT EXISTS direct_hypertable_metrics" in session.queries[0]
    assert "WITH (tsdb.hypertable" in session.queries[0]


def test_format_create_table_with_hypertable_validates_partition_column():
    with pytest.raises(ValueError, match="partition column missing_time"):
        format_create_table_with_hypertable_sql(
            DirectHypertableMetric,
            time_column="missing_time",
        )
