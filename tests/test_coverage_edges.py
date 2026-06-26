from datetime import datetime, timedelta
from types import SimpleNamespace

import importlib
import pytest
import sqlmodel
from sqlalchemy import Column, JSON, MetaData, PickleType
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, SQLModel

from timescaledb.compression.add import add_compression_policy
from timescaledb.compression.enable import enable_table_compression
from timescaledb.compression.extractors import extract_model_compression_params
from timescaledb.compression.sql import (
    format_alter_compression_policy_sql,
    format_compression_policy_sql_query,
)
from timescaledb.compression.validators import (
    validate_compress_orderby_field,
    validate_compress_segmentby_field,
    validate_unique_segmentby_and_orderby_fields,
)
from timescaledb.continuous_aggregates import (
    add_continuous_aggregate_policy,
    add_generated_aggregate_column,
    create_continuous_aggregate,
    refresh_continuous_aggregate,
    remove_continuous_aggregate_policy,
)
from timescaledb.continuous_aggregates.sql import (
    _clean_interval,
    _compile_sql,
    _format_option_value,
    _quote_qualified_identifier,
    format_add_continuous_aggregate_policy_sql_query,
    format_add_generated_aggregate_column_sql,
    format_create_continuous_aggregate_sql,
    format_refresh_continuous_aggregate_sql_query,
)
from timescaledb.defaults import get_defaults
from timescaledb.exceptions import (
    InvalidChunkTimeInterval,
    InvalidCompressionFields,
    InvalidOrderByField,
    InvalidSegmentByField,
)
from timescaledb.hypercore import (
    add_columnstore_policy,
    convert_to_columnstore,
    convert_to_rowstore,
    enable_columnstore,
    list_columnstore_policies,
    remove_columnstore_policy,
    sync_columnstore_policies,
)
from timescaledb.hypercore.extractors import (
    extract_model_columnstore_params,
    extract_model_columnstore_policy_params,
)
from timescaledb.hypercore.sql import (
    _clean_interval_value,
    _compile_sql as _compile_columnstore_sql,
    format_add_columnstore_policy_sql_query,
    format_enable_columnstore_sql,
    quote_qualified_identifier,
)
from timescaledb.hyperfunctions import time_bucket
from timescaledb.hypertables.create import create_hypertable
from timescaledb.hypertables.create_table import (
    create_table_with_hypertable,
    format_create_table_with_hypertable_sql,
)
from timescaledb.hypertables.schemas import HypertableCreateSchema
from timescaledb.hypertables.validators import validate_chunk_time_interval
from timescaledb.queries import time_bucket_gapfill_query
from timescaledb.retention.add import add_retention_policy
from timescaledb.retention.list import list_retention_policies
from timescaledb.retention.sql import (
    format_retention_policy_sql_query,
    get_retention_policy_sql_query,
)


compression_enable_module = importlib.import_module("timescaledb.compression.enable")
compression_sql_module = importlib.import_module("timescaledb.compression.sql")
compression_sync_module = importlib.import_module("timescaledb.compression.sync")
hypertables_sync_module = importlib.import_module("timescaledb.hypertables.sync")
retention_sync_module = importlib.import_module("timescaledb.retention.sync")
columnstore_sync_module = importlib.import_module("timescaledb.hypercore.sync")


class IsolatedSQLModel(SQLModel):
    metadata = MetaData()


class QueryRecorder:
    def __init__(self, rows=None):
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.rows = [] if rows is None else rows

    def execute(self, query):
        self.queries.append(str(query))
        return self

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _NoneFetchallSession(QueryRecorder):
    def fetchall(self):
        return None


class _FakeMappingResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _CapturingExecSession:
    def __init__(self):
        self.last_query = None

    def exec(self, query):
        self.last_query = query
        return _FakeMappingResult()


class CompressionPolicyModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    category: str
    value: int

    __tablename__ = "edge_compression_policy"
    __enable_compression__ = True
    __compress_orderby__ = "time DESC"
    __compress_segmentby__ = "category"
    __compress_after__ = "7 days"
    __compress_created_before__ = "30 days"


class CompressionDisabledModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    value: int

    __tablename__ = "edge_compression_disabled"
    __enable_compression__ = False


class CompressionValidationModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    name: str
    value: int
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    blob: bytes | None = Field(default=None, sa_column=Column(PickleType))

    __tablename__ = "edge_compression_validation"


class ColumnstorePolicyModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    device_id: int
    value: float

    __tablename__ = "edge_columnstore_policy"
    __enable_columnstore__ = True
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "device_id"
    __columnstore_created_before__ = "14 days"
    __columnstore_schedule_interval__ = "1 day"
    __columnstore_timezone__ = "UTC"
    __columnstore_if_not_exists__ = False


class ColumnstoreNoOptionsModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    value: float

    __tablename__ = "edge_columnstore_no_options"
    __enable_columnstore__ = True


class ColumnstoreDisabledModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int = Field(primary_key=True)
    value: float

    __tablename__ = "edge_columnstore_disabled"
    __enable_columnstore__ = False


class EdgeHypertableModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    value: int

    __tablename__ = "edge_hypertable"
    __time_column__ = "time"
    __chunk_time_interval__ = "INTERVAL 1 day"
    __if_not_exists__ = False
    __migrate_data__ = False


class EdgeIntegerTimeModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: int
    value: int

    __tablename__ = "edge_integer_time"


class EdgeRetentionModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    value: int

    __tablename__ = "edge_retention"
    __drop_after__ = "INTERVAL 2 days"


class EdgeDirectHypertableModel(IsolatedSQLModel, table=True):
    id: int = Field(primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime(timezone=True))
    value: int

    __tablename__ = "edge_direct_hypertable"


class NotATableModel(IsolatedSQLModel):
    id: int


def test_defaults_are_exposed_as_dict():
    defaults = get_defaults()

    assert defaults["TIME_COLUMN"] == "time"
    assert defaults["DROP_AFTER"] == "INTERVAL 3 months"


def test_compression_validator_edge_cases():
    assert validate_compress_segmentby_field(CompressionValidationModel) is True
    assert validate_compress_orderby_field(CompressionValidationModel) is True
    assert (
        validate_unique_segmentby_and_orderby_fields(
            CompressionValidationModel,
            segmentby_field="name",
            orderby_field="time DESC",
        )
        is True
    )

    with pytest.raises(InvalidSegmentByField, match="invalid type JSON"):
        validate_compress_segmentby_field(CompressionValidationModel, "payload")

    with pytest.raises(InvalidSegmentByField, match="not found"):
        validate_compress_segmentby_field(CompressionValidationModel, "missing")

    assert (
        validate_compress_orderby_field(CompressionValidationModel, "time") is True
    )
    assert (
        validate_compress_orderby_field(
            CompressionValidationModel,
            "time DESC NULLS LAST",
        )
        is True
    )

    with pytest.raises(InvalidOrderByField, match="not found"):
        validate_compress_orderby_field(CompressionValidationModel, "missing")

    with pytest.raises(InvalidOrderByField, match="Empty orderby"):
        validate_compress_orderby_field(CompressionValidationModel, ",")

    with pytest.raises(InvalidOrderByField, match="invalid type JSON"):
        validate_compress_orderby_field(CompressionValidationModel, "payload")

    with pytest.raises(InvalidOrderByField, match="Invalid direction"):
        validate_compress_orderby_field(CompressionValidationModel, "time SIDEWAYS")

    with pytest.raises(InvalidOrderByField, match="Invalid NULLS specification"):
        validate_compress_orderby_field(CompressionValidationModel, "time ASC NULLS")

    with pytest.raises(InvalidOrderByField, match="Invalid NULLS specification"):
        validate_compress_orderby_field(CompressionValidationModel, "time ASC NOPE LAST")

    with pytest.raises(InvalidCompressionFields, match="must be different"):
        validate_unique_segmentby_and_orderby_fields(
            CompressionValidationModel,
            segmentby_field="time",
            orderby_field="time DESC",
        )


def test_compression_extractors_and_wrappers_cover_optional_paths(monkeypatch):
    assert extract_model_compression_params(CompressionDisabledModel) is None

    session = QueryRecorder()
    add_compression_policy(session, model=CompressionDisabledModel)
    assert session.queries == []
    assert session.commits == 0

    with pytest.raises(ValueError, match="model or table_name"):
        add_compression_policy(session)

    add_compression_policy(session, table_name="metrics")
    assert session.commits == 0

    add_compression_policy(session, model=CompressionPolicyModel, commit=False)
    assert len(session.queries) == 2
    assert "compress_after" in session.queries[0]
    assert "compress_created_before" in session.queries[1]
    assert session.commits == 0

    with pytest.raises(ValueError, match="model or table_name"):
        enable_table_compression(session)

    enable_table_compression(session, model=CompressionDisabledModel)
    assert len(session.queries) == 2

    enable_table_compression(
        session,
        model=CompressionPolicyModel,
        compress_orderby="value DESC",
        compress_segmentby="category",
        commit=False,
    )
    assert "value DESC" in session.queries[-1]

    monkeypatch.setattr(
        compression_enable_module.extractors,
        "extract_model_compression_params",
        lambda model: {"compress_enabled": False},
    )
    enable_table_compression(session, model=CompressionPolicyModel)
    assert len(session.queries) == 3


def test_compression_sql_defensive_branches(monkeypatch):
    assert format_compression_policy_sql_query("metrics") is None

    with pytest.raises(ValueError, match="You must use a timedelta"):
        format_compression_policy_sql_query(
            "metrics",
            compress_created_before=timedelta(days=1),
        )

    original_mapping = compression_sql_module.COMPRESSION_POLICY_SQL_TEMPLATE_MAPPING
    monkeypatch.setattr(
        compression_sql_module,
        "COMPRESSION_POLICY_SQL_TEMPLATE_MAPPING",
        {"BEFORE_INTERVAL": original_mapping["BEFORE_INTERVAL"]},
    )
    with pytest.raises(ValueError, match="Invalid interval type"):
        format_compression_policy_sql_query("metrics", compress_after="1 day")

    monkeypatch.setattr(
        compression_sql_module,
        "COMPRESSION_POLICY_SQL_TEMPLATE_MAPPING",
        {"AFTER_INTERVAL": original_mapping["AFTER_INTERVAL"]},
    )
    with pytest.raises(ValueError, match="Invalid interval type"):
        format_compression_policy_sql_query(
            "metrics",
            compress_created_before="1 day",
        )

    query = format_alter_compression_policy_sql(
        "metrics",
        with_orderby=False,
        with_segmentby=False,
    )
    assert "timescaledb.compress," not in query


def test_sync_compression_policies_handles_skips_and_errors(monkeypatch):
    session = QueryRecorder()
    compression_sync_module.sync_compression_policies(
        session,
        CompressionDisabledModel,
        CompressionPolicyModel,
    )
    assert session.commits == 1
    assert len(session.queries) == 3

    def raise_sqlalchemy_error(*args, **kwargs):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(
        compression_sync_module,
        "enable_table_compression",
        raise_sqlalchemy_error,
    )
    failing_session = QueryRecorder()
    with pytest.raises(SQLAlchemyError, match="boom"):
        compression_sync_module.sync_compression_policies(
            failing_session,
            CompressionPolicyModel,
        )
    assert failing_session.rollbacks == 1


def test_continuous_aggregate_sql_helpers_and_validation():
    assert _compile_sql("SELECT 1") == "SELECT 1"
    assert _clean_interval(timedelta(milliseconds=1500)) == "1.5 seconds"
    assert _format_option_value(4) == "4"
    assert _format_option_value(timedelta(seconds=2)) == "'2 seconds'"
    assert _format_option_value("Bob's") == "'Bob''s'"

    with pytest.raises(ValueError, match="identifier is required"):
        _quote_qualified_identifier(" ")

    minimal = format_create_continuous_aggregate_sql(
        "conditions_hourly",
        "SELECT 1",
    )
    assert "WITH DATA" in minimal
    assert "timescaledb.chunk_interval" not in minimal

    with pytest.raises(ValueError, match="select_query is required"):
        format_create_continuous_aggregate_sql("conditions_hourly", " ")

    with pytest.raises(ValueError, match="data_type is required"):
        format_add_generated_aggregate_column_sql(
            "conditions_hourly",
            "max_temp",
            " ",
            "max(temp)",
        )

    with pytest.raises(ValueError, match="aggregate_expression is required"):
        format_add_generated_aggregate_column_sql(
            "conditions_hourly",
            "max_temp",
            "DOUBLE PRECISION",
            "",
        )


def test_continuous_aggregate_policy_and_refresh_edge_cases():
    refresh = format_refresh_continuous_aggregate_sql_query("conditions")
    assert "NULL, NULL" in refresh

    policy = format_add_continuous_aggregate_policy_sql_query(
        "conditions_hourly",
        start_offset=None,
        end_offset=None,
        schedule_interval=60,
        initial_start=datetime(2024, 1, 1),
    )
    assert "start_offset => NULL" in policy
    assert "end_offset => NULL" in policy
    assert "schedule_interval => 60" in policy
    assert "initial_start => '2024-01-01" in policy
    assert "if_not_exists" not in policy

    with pytest.raises(ValueError, match="schedule_interval is required"):
        format_add_continuous_aggregate_policy_sql_query(
            "conditions_hourly",
            start_offset=None,
            end_offset=None,
            schedule_interval=None,
        )


def test_continuous_aggregate_wrappers_allow_commit_false():
    session = QueryRecorder()

    create_continuous_aggregate(
        session,
        "conditions_hourly",
        "SELECT 1",
        commit=False,
    )
    add_generated_aggregate_column(
        session,
        "conditions_hourly",
        "max_temp",
        "DOUBLE PRECISION",
        "max(temp)",
        commit=False,
    )
    refresh_continuous_aggregate(session, "conditions_hourly", commit=False)
    add_continuous_aggregate_policy(
        session,
        "conditions_hourly",
        start_offset=None,
        end_offset=None,
        schedule_interval="1 hour",
        commit=False,
    )
    remove_continuous_aggregate_policy(
        session,
        "conditions_hourly",
        commit=False,
    )

    assert len(session.queries) == 5
    assert session.commits == 0


def test_hypercore_sql_helpers_and_formatters():
    assert _compile_columnstore_sql("SELECT 1") == "SELECT 1"
    assert _clean_interval_value(timedelta(milliseconds=1500)) == (
        "1.5 seconds",
        "INTERVAL",
    )
    assert _clean_interval_value(object())[1] == "INVALID"

    with pytest.raises(ValueError, match="identifier is required"):
        quote_qualified_identifier("")

    minimal = format_enable_columnstore_sql("metrics")
    assert "timescaledb.enable_columnstore = true" in minimal
    assert "timescaledb.orderby" not in minimal

    created_before = format_add_columnstore_policy_sql_query(
        "metrics",
        created_before="3 days",
        schedule_interval=timedelta(hours=1),
        initial_start=datetime(2024, 1, 1),
        timezone="UTC",
    )
    assert "created_before => CAST('3 days' AS INTERVAL)" in created_before
    assert "schedule_interval => CAST('3600 seconds' AS INTERVAL)" in created_before
    assert "initial_start => '2024-01-01" in created_before
    assert "timezone => 'UTC'" in created_before

    with pytest.raises(ValueError, match="Invalid interval type"):
        format_add_columnstore_policy_sql_query("metrics", created_before=123)


def test_hypercore_extractors_and_wrappers_cover_optional_paths():
    assert extract_model_columnstore_params(ColumnstoreDisabledModel) is None
    assert extract_model_columnstore_policy_params(ColumnstoreDisabledModel) is None

    params = extract_model_columnstore_params(ColumnstoreNoOptionsModel)
    assert params == {
        "table_name": "edge_columnstore_no_options",
        "columnstore_enabled": True,
    }

    session = QueryRecorder()

    with pytest.raises(ValueError, match="model or table_name"):
        enable_columnstore(session)

    enable_columnstore(session, model=ColumnstoreDisabledModel)
    assert session.queries == []

    enable_columnstore(session, table_name="metrics", commit=False)
    enable_columnstore(
        session,
        model=ColumnstorePolicyModel,
        orderby="value DESC",
        segmentby="device_id",
        commit=False,
    )
    assert "value DESC" in session.queries[-1]

    add_columnstore_policy(session, model=ColumnstoreDisabledModel)
    assert len(session.queries) == 2

    add_columnstore_policy(session, model=ColumnstoreNoOptionsModel)
    assert len(session.queries) == 2
    assert session.commits == 0

    with pytest.raises(ValueError, match="model or table_name"):
        add_columnstore_policy(session)

    add_columnstore_policy(session, model=ColumnstorePolicyModel, commit=False)
    assert "created_before => CAST('14 days' AS INTERVAL)" in session.queries[-1]
    assert "timezone => 'UTC'" in session.queries[-1]

    add_columnstore_policy(
        session,
        table_name="metrics",
        commit=False,
        after="90 days",
    )
    assert "after => CAST('90 days' AS INTERVAL)" in session.queries[-1]

    convert_to_columnstore(session, "_hyper_1_1_chunk", commit=False)
    convert_to_rowstore(session, "_hyper_1_1_chunk", commit=False)
    remove_columnstore_policy(session, "metrics", commit=False)
    assert session.commits == 0

    commit_session = QueryRecorder()
    convert_to_columnstore(commit_session, "_hyper_1_1_chunk")
    convert_to_rowstore(commit_session, "_hyper_1_1_chunk")
    remove_columnstore_policy(commit_session, "metrics")
    assert commit_session.commits == 3


def test_hypercore_list_and_sync_error_path(monkeypatch):
    session = QueryRecorder(rows=[("metrics",), ("events",)])
    assert list_columnstore_policies(session) == ["metrics", "events"]

    def raise_sqlalchemy_error(*args, **kwargs):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(
        columnstore_sync_module,
        "enable_columnstore",
        raise_sqlalchemy_error,
    )
    failing_session = QueryRecorder()
    with pytest.raises(SQLAlchemyError, match="boom"):
        sync_columnstore_policies(failing_session, ColumnstorePolicyModel)
    assert failing_session.rollbacks == 1


def test_hyperfunctions_time_bucket_offsets():
    interval_bucket = time_bucket("1 hour", datetime(2024, 1, 1), offset="5 minutes")
    integer_bucket = time_bucket(300, 1_700_000_000, offset=30)

    assert "INTERVAL '5 minutes'" in interval_bucket.compile().string
    assert 30 in integer_bucket.compile().params.values()


def test_hypertable_create_and_schema_edges():
    session = QueryRecorder()

    with pytest.raises(ValueError, match="model or table_name is required"):
        create_hypertable(session)

    create_hypertable(
        session,
        model=EdgeHypertableModel,
        hypertable_options={"chunk_time_interval": "INTERVAL 2 days"},
        overwrite_model_params=True,
        commit=False,
    )
    assert "2 days" in session.queries[0]
    assert session.commits == 0

    schema = HypertableCreateSchema(
        table_name="metrics",
        time_column="time",
        chunk_time_interval=object(),
    )
    with pytest.raises(ValueError, match="Invalid interval type"):
        schema.to_sql_query()


def test_create_table_with_hypertable_edges():
    with pytest.raises(ValueError, match="table=True SQLModel"):
        format_create_table_with_hypertable_sql(NotATableModel)

    with pytest.raises(ValueError, match="Invalid chunk interval"):
        format_create_table_with_hypertable_sql(
            EdgeDirectHypertableModel,
            chunk_interval=object(),
        )

    query = format_create_table_with_hypertable_sql(
        EdgeDirectHypertableModel,
        chunk_interval=None,
        segmentby="owner's id",
        create_default_indexes=True,
        if_not_exists=False,
    )
    assert "CREATE TABLE edge_direct_hypertable" in query
    assert "owner''s id" in query
    assert "tsdb.create_default_indexes = true" in query

    session = QueryRecorder()
    create_table_with_hypertable(
        session,
        EdgeDirectHypertableModel,
        commit=False,
    )
    assert session.queries
    assert session.commits == 0


def test_hypertable_validator_integer_interval_edges():
    validate_chunk_time_interval(
        EdgeHypertableModel,
        "time",
        "INTERVAL 3 days",
    )
    assert validate_chunk_time_interval(EdgeHypertableModel, "time", object()) is None
    validate_chunk_time_interval(EdgeIntegerTimeModel, "time", "1000")

    with pytest.raises(InvalidChunkTimeInterval, match="must be an integer"):
        validate_chunk_time_interval(EdgeIntegerTimeModel, "time", "not an integer")

    class BadInt(int):
        def __int__(self):
            raise OverflowError("bad int")

    with pytest.raises(InvalidChunkTimeInterval, match="must be an integer"):
        validate_chunk_time_interval(EdgeHypertableModel, "time", BadInt(1))


def test_sync_all_hypertables_skips_and_handles_errors(monkeypatch):
    session = QueryRecorder()
    monkeypatch.setattr(
        hypertables_sync_module,
        "list_hypertables",
        lambda session: [SimpleNamespace(hypertable_name="edge_hypertable")],
    )
    hypertables_sync_module.sync_all_hypertables(session, EdgeHypertableModel)
    assert session.queries == []
    assert session.commits == 1

    monkeypatch.setattr(hypertables_sync_module, "list_hypertables", lambda session: [])

    def raise_sqlalchemy_error(*args, **kwargs):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(
        hypertables_sync_module,
        "create_hypertable",
        raise_sqlalchemy_error,
    )
    failing_session = QueryRecorder()
    with pytest.raises(SQLAlchemyError, match="boom"):
        hypertables_sync_module.sync_all_hypertables(
            failing_session,
            EdgeHypertableModel,
        )
    assert failing_session.rollbacks == 1


def test_queries_gapfill_accepts_instrumented_attributes():
    session = _CapturingExecSession()
    time_bucket_gapfill_query(
        session,
        EdgeHypertableModel,
        time_field=EdgeHypertableModel.time,
        metric_field=EdgeHypertableModel.value,
    )
    sql = str(session.last_query.compile(dialect=postgresql.dialect()))

    assert "time_bucket_gapfill(INTERVAL '1 hour', edge_hypertable.time" in sql
    assert "avg(edge_hypertable.value)" in sql


def test_retention_sql_and_wrappers_edge_cases():
    session = QueryRecorder()

    add_retention_policy(session, table_name="metrics", drop_after=10)
    assert "BIGINT 10" in session.queries[0]

    with pytest.raises(ValueError, match="drop_after is required"):
        format_retention_policy_sql_query("metrics")

    with pytest.raises(ValueError, match="Invalid interval type"):
        format_retention_policy_sql_query("metrics", drop_after=object())

    assert "policy_retention" in get_retention_policy_sql_query("metrics")
    assert "'metrics'" in get_retention_policy_sql_query("metrics")

    none_session = _NoneFetchallSession()
    assert list_retention_policies(none_session) is None


def test_sync_retention_policies_none_and_existing_policies(monkeypatch):
    added = []

    monkeypatch.setattr(
        retention_sync_module,
        "list_retention_policies",
        lambda session: None,
    )
    monkeypatch.setattr(
        retention_sync_module,
        "add_retention_policy",
        lambda session, model, drop_after=None: added.append(
            (model.__tablename__, drop_after)
        ),
    )

    session = QueryRecorder()
    retention_sync_module.sync_retention_policies(
        session,
        EdgeRetentionModel,
        drop_after="INTERVAL 5 days",
    )
    assert added == [("edge_retention", "INTERVAL 5 days")]

    monkeypatch.setattr(
        retention_sync_module,
        "list_retention_policies",
        lambda session: ["edge_retention"],
    )
    retention_sync_module.sync_retention_policies(session, EdgeRetentionModel)
    assert added == [("edge_retention", "INTERVAL 5 days")]
