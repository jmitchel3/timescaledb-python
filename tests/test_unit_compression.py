"""Pure-unit tests for the compression subpackage.

These exercise the SQL builders, extractors, validators, and the
enable/add/sync helpers using lightweight fake sessions so no live database
is required.
"""

from datetime import datetime
from typing import Optional

import pytest
import sqlmodel
from sqlalchemy import JSON, Column, MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field

from timescaledb.compression import enable, extractors, sql, validators
from timescaledb.compression.add import add_compression_policy
from timescaledb.compression.enable import enable_table_compression
from timescaledb.compression.sync import sync_compression_policies
from timescaledb.exceptions import (
    InvalidCompressionFields,
    InvalidOrderByField,
    InvalidSegmentByField,
)

from .conftest import Metric, SimpleCompression, VideoView


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


# ---------------------------------------------------------------------------
# Isolated model with a JSON column for validator type checks
# ---------------------------------------------------------------------------


class _CompBase(sqlmodel.SQLModel):
    metadata = MetaData()


class ValidatorModel(_CompBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    time: datetime = Field(sa_type=sqlmodel.DateTime)
    value: int
    name: str
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))


# ---------------------------------------------------------------------------
# add_compression_policy
# ---------------------------------------------------------------------------


def test_add_compression_policy_requires_model_or_table_name():
    with pytest.raises(ValueError, match="model or table_name is required"):
        add_compression_policy(QueryRecorder(), model=None, table_name=None)


def test_add_compression_policy_skips_disabled_model():
    session = QueryRecorder()
    add_compression_policy(session, model=Metric)
    assert session.queries == []
    assert session.commits == 0


def test_add_compression_policy_with_model_and_compress_after():
    session = QueryRecorder()
    add_compression_policy(session, model=SimpleCompression, compress_after="7 days")
    assert session.commits == 1
    assert "add_compression_policy" in session.queries[0]
    assert "compress_after" in session.queries[0]


def test_add_compression_policy_with_model_and_created_before():
    session = QueryRecorder()
    add_compression_policy(
        session,
        model=SimpleCompression,
        compress_created_before="INTERVAL 7 days",
    )
    assert session.commits == 1
    assert "compress_created_before" in session.queries[0]


# ---------------------------------------------------------------------------
# enable_table_compression
# ---------------------------------------------------------------------------


def test_enable_table_compression_requires_model_or_table_name():
    with pytest.raises(ValueError, match="model or table_name is required"):
        enable_table_compression(QueryRecorder(), model=None, table_name=None)


def test_enable_table_compression_disabled_model_is_noop():
    session = QueryRecorder()
    enable_table_compression(session, model=Metric)
    assert session.queries == []
    assert session.commits == 0


def test_enable_table_compression_returns_when_params_not_enabled(monkeypatch):
    """Defensive branch: params present but compression disabled."""
    monkeypatch.setattr(
        enable.extractors,
        "extract_model_compression_params",
        lambda model: {"compress_enabled": False},
    )
    session = QueryRecorder()
    enable_table_compression(session, model=SimpleCompression)
    assert session.queries == []


def test_enable_table_compression_model_without_orderby_segmentby():
    session = QueryRecorder()
    enable_table_compression(session, model=SimpleCompression)
    assert session.commits == 1
    assert "timescaledb.compress" in session.queries[0]


def test_enable_table_compression_model_with_orderby_and_segmentby():
    session = QueryRecorder()
    enable_table_compression(session, model=VideoView)
    assert session.commits == 1
    assert "compress_orderby" in session.queries[0]
    assert "compress_segmentby" in session.queries[0]


def test_enable_table_compression_explicit_orderby_and_segmentby():
    """Explicit args are not overwritten by model metadata."""
    session = QueryRecorder()
    enable_table_compression(
        session,
        model=SimpleCompression,
        compress_orderby="value ASC",
        compress_segmentby="value",
    )
    assert session.commits == 1
    assert "value ASC" in session.queries[0]


# ---------------------------------------------------------------------------
# sql.format_compression_policy_sql_query
# ---------------------------------------------------------------------------


def test_format_compression_policy_returns_none_when_no_age():
    assert sql.format_compression_policy_sql_query("metrics") is None


def test_format_compression_policy_created_before_requires_timedelta():
    with pytest.raises(ValueError, match="timedelta"):
        sql.format_compression_policy_sql_query("metrics", compress_created_before=5)


def test_format_compression_policy_after_invalid_template(monkeypatch):
    monkeypatch.setattr(sql, "COMPRESSION_POLICY_SQL_TEMPLATE_MAPPING", {})
    with pytest.raises(ValueError, match="Invalid interval type"):
        sql.format_compression_policy_sql_query("metrics", compress_after="7 days")


def test_format_compression_policy_before_invalid_template(monkeypatch):
    monkeypatch.setattr(sql, "COMPRESSION_POLICY_SQL_TEMPLATE_MAPPING", {})
    with pytest.raises(ValueError, match="Invalid interval type"):
        sql.format_compression_policy_sql_query(
            "metrics", compress_created_before="7 days"
        )


# ---------------------------------------------------------------------------
# sync_compression_policies
# ---------------------------------------------------------------------------


def test_sync_compression_policies_with_explicit_models():
    session = QueryRecorder()
    sync_compression_policies(session, SimpleCompression)
    assert session.commits == 1
    assert any("timescaledb.compress" in q for q in session.queries)


def test_sync_compression_policies_rolls_back_on_error():
    session = FailingSession()
    with pytest.raises(SQLAlchemyError):
        sync_compression_policies(session, SimpleCompression)
    assert session.rollbacks == 1


# ---------------------------------------------------------------------------
# extractors
# ---------------------------------------------------------------------------


def test_extract_model_compression_params_returns_none_when_disabled():
    assert extractors.extract_model_compression_params(Metric) is None


# ---------------------------------------------------------------------------
# validators
# ---------------------------------------------------------------------------


def test_validate_segmentby_missing_field():
    with pytest.raises(InvalidSegmentByField, match="not found"):
        validators.validate_compress_segmentby_field(ValidatorModel, "missing")


def test_validate_segmentby_invalid_type():
    with pytest.raises(InvalidSegmentByField, match="invalid type"):
        validators.validate_compress_segmentby_field(ValidatorModel, "payload")


def test_validate_segmentby_none_is_valid():
    assert validators.validate_compress_segmentby_field(ValidatorModel, None) is True


def test_validate_orderby_empty_spec():
    with pytest.raises(InvalidOrderByField, match="Empty orderby"):
        validators.validate_compress_orderby_field(ValidatorModel, ",")


def test_validate_orderby_missing_field():
    with pytest.raises(InvalidOrderByField, match="not found"):
        validators.validate_compress_orderby_field(ValidatorModel, "missing")


def test_validate_orderby_invalid_type():
    with pytest.raises(InvalidOrderByField, match="invalid type"):
        validators.validate_compress_orderby_field(ValidatorModel, "payload")


def test_validate_orderby_multiple_fields_without_direction():
    assert (
        validators.validate_compress_orderby_field(ValidatorModel, "value, name")
        is True
    )


def test_validate_orderby_invalid_direction():
    with pytest.raises(InvalidOrderByField, match="Invalid direction"):
        validators.validate_compress_orderby_field(ValidatorModel, "value SIDEWAYS")


def test_validate_orderby_incomplete_nulls_spec():
    with pytest.raises(InvalidOrderByField, match="NULLS"):
        validators.validate_compress_orderby_field(ValidatorModel, "value ASC NULLS")


def test_validate_orderby_invalid_nulls_keyword():
    with pytest.raises(InvalidOrderByField, match="NULLS"):
        validators.validate_compress_orderby_field(
            ValidatorModel, "value ASC FOO BAR"
        )


def test_validate_orderby_valid_nulls_spec():
    assert (
        validators.validate_compress_orderby_field(ValidatorModel, "value ASC NULLS FIRST")
        is True
    )


def test_validate_unique_segmentby_and_orderby_conflict():
    with pytest.raises(InvalidCompressionFields, match="must be different"):
        validators.validate_unique_segmentby_and_orderby_fields(
            ValidatorModel, segmentby_field="value", orderby_field="value"
        )
