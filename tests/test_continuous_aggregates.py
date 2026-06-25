from datetime import datetime, timedelta, timezone

from timescaledb.continuous_aggregates import (
    add_continuous_aggregate_policy,
    add_generated_aggregate_column,
    create_continuous_aggregate,
    refresh_continuous_aggregate,
    remove_continuous_aggregate_policy,
)
from timescaledb.continuous_aggregates.sql import (
    format_add_generated_aggregate_column_sql,
    format_add_continuous_aggregate_policy_sql_query,
    format_create_continuous_aggregate_sql,
    format_refresh_continuous_aggregate_sql_query,
    format_remove_continuous_aggregate_policy_sql_query,
)


class QueryRecorder:
    def __init__(self):
        self.queries = []
        self.commits = 0

    def execute(self, query):
        self.queries.append(str(query))

    def commit(self):
        self.commits += 1


def test_format_refresh_continuous_aggregate_with_timestamp_window():
    query = format_refresh_continuous_aggregate_sql_query(
        "conditions",
        window_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2020, 2, 1, tzinfo=timezone.utc),
    )

    assert "CALL refresh_continuous_aggregate" in query
    assert "'conditions'" in query
    assert "2020-01-01" in query
    assert "2020-02-01" in query


def test_format_create_continuous_aggregate_sql():
    query = format_create_continuous_aggregate_sql(
        "analytics.conditions_hourly",
        """
        SELECT time_bucket('1 hour', time) AS bucket, avg(temp) AS avg_temp
        FROM conditions
        GROUP BY bucket
        """,
        column_names=["bucket", "avg_temp"],
        chunk_interval="INTERVAL 1 day",
        create_group_indexes=False,
        finalized=True,
        materialized_only=False,
        invalidate_using="wal",
        with_data=False,
    )

    assert 'CREATE MATERIALIZED VIEW "analytics"."conditions_hourly"' in query
    assert '("bucket", "avg_temp")' in query
    assert "WITH (timescaledb.continuous" in query
    assert "timescaledb.chunk_interval = '1 day'" in query
    assert "timescaledb.create_group_indexes = false" in query
    assert "timescaledb.finalized = true" in query
    assert "timescaledb.materialized_only = false" in query
    assert "timescaledb.invalidate_using = 'wal'" in query
    assert "WITH NO DATA" in query


def test_create_continuous_aggregate_executes_generated_sql():
    session = QueryRecorder()

    create_continuous_aggregate(
        session,
        "conditions_hourly",
        "SELECT time_bucket('1 hour', time) AS bucket FROM conditions GROUP BY bucket",
        with_data=False,
    )

    assert session.commits == 1
    assert "CREATE MATERIALIZED VIEW" in session.queries[0]
    assert "timescaledb.continuous" in session.queries[0]


def test_format_add_generated_aggregate_column_sql():
    query = format_add_generated_aggregate_column_sql(
        "analytics.conditions_hourly",
        "max_temp",
        "DOUBLE PRECISION",
        "max(temp)",
    )

    assert 'ALTER MATERIALIZED VIEW "analytics"."conditions_hourly"' in query
    assert 'ADD COLUMN "max_temp" DOUBLE PRECISION' in query
    assert "GENERATED ALWAYS AS (max(temp)) STORED" in query


def test_add_generated_aggregate_column_executes_generated_sql():
    session = QueryRecorder()

    add_generated_aggregate_column(
        session,
        "conditions_hourly",
        "max_temp",
        "DOUBLE PRECISION",
        "max(temp)",
    )

    assert session.commits == 1
    assert "ALTER MATERIALIZED VIEW" in session.queries[0]
    assert 'ADD COLUMN "max_temp"' in session.queries[0]


def test_format_refresh_continuous_aggregate_with_force():
    query = format_refresh_continuous_aggregate_sql_query(
        "conditions",
        "2020-01-01",
        "2020-02-01",
        force=True,
    )

    assert "force => true" in query


def test_format_refresh_continuous_aggregate_with_newest_first_flag():
    query = format_refresh_continuous_aggregate_sql_query(
        "conditions",
        "2020-01-01",
        "2020-02-01",
        refresh_newest_first=False,
    )

    assert "refresh_newest_first => false" in query


def test_format_refresh_continuous_aggregate_with_interval_window():
    query = format_refresh_continuous_aggregate_sql_query(
        "conditions",
        window_start=timedelta(days=30),
        window_end="INTERVAL 1 day",
    )

    assert "CAST('2592000 seconds' AS INTERVAL)" in query
    assert "CAST('1 day' AS INTERVAL)" in query


def test_format_refresh_continuous_aggregate_with_integer_window():
    query = format_refresh_continuous_aggregate_sql_query(
        "conditions",
        window_start=1,
        window_end=1000,
    )

    assert "1, 1000" in query


def test_refresh_continuous_aggregate_executes_generated_sql():
    session = QueryRecorder()

    refresh_continuous_aggregate(
        session,
        "conditions",
        "2020-01-01",
        "2020-02-01",
        force=True,
    )

    assert session.commits == 1
    assert "CALL refresh_continuous_aggregate" in session.queries[0]
    assert "force => true" in session.queries[0]


def test_format_add_continuous_aggregate_policy_sql_with_tuning_options():
    query = format_add_continuous_aggregate_policy_sql_query(
        "conditions_hourly",
        start_offset="INTERVAL 1 month",
        end_offset="1 hour",
        schedule_interval=timedelta(hours=1),
        if_not_exists=True,
        timezone="UTC",
        include_tiered_data=False,
        buckets_per_batch=10,
        max_batches_per_execution=2,
        refresh_newest_first=False,
    )

    assert "SELECT add_continuous_aggregate_policy" in query
    assert "start_offset => CAST('1 month' AS INTERVAL)" in query
    assert "end_offset => CAST('1 hour' AS INTERVAL)" in query
    assert "schedule_interval => CAST('3600 seconds' AS INTERVAL)" in query
    assert "if_not_exists => true" in query
    assert "timezone => 'UTC'" in query
    assert "include_tiered_data => false" in query
    assert "buckets_per_batch => 10" in query
    assert "max_batches_per_execution => 2" in query
    assert "refresh_newest_first => false" in query


def test_format_add_continuous_aggregate_policy_sql_with_integer_offsets():
    query = format_add_continuous_aggregate_policy_sql_query(
        "integer_conditions",
        start_offset=10_000,
        end_offset=1_000,
        schedule_interval="1 hour",
    )

    assert "start_offset => 10000" in query
    assert "end_offset => 1000" in query


def test_add_continuous_aggregate_policy_executes_generated_sql():
    session = QueryRecorder()

    add_continuous_aggregate_policy(
        session,
        "conditions_hourly",
        start_offset="1 month",
        end_offset="1 hour",
        schedule_interval="1 hour",
        buckets_per_batch=5,
    )

    assert session.commits == 1
    assert "SELECT add_continuous_aggregate_policy" in session.queries[0]
    assert "buckets_per_batch => 5" in session.queries[0]


def test_format_remove_continuous_aggregate_policy_sql():
    query = format_remove_continuous_aggregate_policy_sql_query(
        "conditions_hourly",
        if_exists=True,
    )

    assert "SELECT remove_continuous_aggregate_policy" in query
    assert "'conditions_hourly'" in query
    assert "if_exists => true" in query


def test_remove_continuous_aggregate_policy_executes_generated_sql():
    session = QueryRecorder()

    remove_continuous_aggregate_policy(session, "conditions_hourly")

    assert session.commits == 1
    assert "SELECT remove_continuous_aggregate_policy" in session.queries[0]
