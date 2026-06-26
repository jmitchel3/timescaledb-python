"""Pure-unit tests covering continuous_aggregates edge cases and helpers."""

from datetime import timedelta

import pytest

from timescaledb.continuous_aggregates import sql
from timescaledb.continuous_aggregates.alter import add_generated_aggregate_column
from timescaledb.continuous_aggregates.create import create_continuous_aggregate
from timescaledb.continuous_aggregates.policies import (
    add_continuous_aggregate_policy,
    remove_continuous_aggregate_policy,
)
from timescaledb.continuous_aggregates.refresh import refresh_continuous_aggregate


class QueryRecorder:
    def __init__(self):
        self.queries = []
        self.commits = 0

    def execute(self, query):
        self.queries.append(str(query))

    def commit(self):
        self.commits += 1


# ---------------------------------------------------------------------------
# commit=False branches on the executing helpers
# ---------------------------------------------------------------------------


def test_create_continuous_aggregate_without_commit():
    session = QueryRecorder()
    create_continuous_aggregate(
        session,
        "v",
        "SELECT 1 AS bucket",
        with_data=False,
        commit=False,
    )
    assert session.commits == 0
    assert len(session.queries) == 1


def test_refresh_continuous_aggregate_without_commit():
    session = QueryRecorder()
    refresh_continuous_aggregate(session, "v", commit=False)
    assert session.commits == 0
    assert len(session.queries) == 1


def test_add_continuous_aggregate_policy_without_commit():
    session = QueryRecorder()
    add_continuous_aggregate_policy(
        session,
        "v",
        start_offset="1 month",
        end_offset="1 hour",
        schedule_interval="1 hour",
        commit=False,
    )
    assert session.commits == 0


def test_remove_continuous_aggregate_policy_without_commit():
    session = QueryRecorder()
    remove_continuous_aggregate_policy(session, "v", commit=False)
    assert session.commits == 0


def test_add_generated_aggregate_column_without_commit():
    session = QueryRecorder()
    add_generated_aggregate_column(
        session, "v", "max_temp", "DOUBLE PRECISION", "max(temp)", commit=False
    )
    assert session.commits == 0


# ---------------------------------------------------------------------------
# sql private helpers
# ---------------------------------------------------------------------------


def test_compile_sql_without_params():
    assert "SELECT 1" in sql._compile_sql("SELECT 1")


def test_clean_interval_fractional_timedelta():
    assert sql._clean_interval(timedelta(milliseconds=1500)) == "1.5 seconds"


def test_quote_qualified_identifier_requires_value():
    with pytest.raises(ValueError, match="identifier is required"):
        sql._quote_qualified_identifier("")


def test_format_option_value_integer():
    assert sql._format_option_value(5) == "5"


def test_format_option_value_timedelta():
    assert sql._format_option_value(timedelta(hours=1)) == "'3600 seconds'"


# ---------------------------------------------------------------------------
# sql public builders edge cases
# ---------------------------------------------------------------------------


def test_format_refresh_with_null_window():
    out = sql.format_refresh_continuous_aggregate_sql_query("conditions")
    assert "NULL, NULL" in out


def test_format_create_continuous_aggregate_requires_select_query():
    with pytest.raises(ValueError, match="select_query is required"):
        sql.format_create_continuous_aggregate_sql("v", "")


def test_format_add_generated_aggregate_column_requires_data_type():
    with pytest.raises(ValueError, match="data_type is required"):
        sql.format_add_generated_aggregate_column_sql("v", "c", "", "max(x)")


def test_format_add_generated_aggregate_column_requires_expression():
    with pytest.raises(ValueError, match="aggregate_expression is required"):
        sql.format_add_generated_aggregate_column_sql("v", "c", "INT", "")


def test_format_add_policy_requires_schedule_interval():
    with pytest.raises(ValueError, match="schedule_interval is required"):
        sql.format_add_continuous_aggregate_policy_sql_query(
            "v",
            start_offset="1 month",
            end_offset="1 hour",
            schedule_interval=None,
        )


def test_format_add_policy_with_null_offsets():
    out = sql.format_add_continuous_aggregate_policy_sql_query(
        "v",
        start_offset=None,
        end_offset=None,
        schedule_interval="1 hour",
    )
    assert "start_offset => NULL" in out
    assert "end_offset => NULL" in out
