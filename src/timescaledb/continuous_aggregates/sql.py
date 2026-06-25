from datetime import date, datetime, timedelta
from typing import Any

import sqlalchemy
from sqlalchemy.dialects import postgresql


_POSTGRES_DIALECT = postgresql.dialect()
_IDENTIFIER_PREPARER = _POSTGRES_DIALECT.identifier_preparer


RefreshWindow = str | int | date | datetime | timedelta | None
PolicyOffset = str | int | timedelta | None


def _compile_sql(sql_template: str, params: dict[str, Any] | None = None) -> str:
    query = sqlalchemy.text(sql_template)
    if params:
        query = query.bindparams(**params)
    return str(
        query.compile(
            dialect=_POSTGRES_DIALECT,
            compile_kwargs={"literal_binds": True},
        )
    )


def _clean_interval(interval: str | timedelta) -> str:
    if isinstance(interval, timedelta):
        seconds = interval.total_seconds()
        if seconds.is_integer():
            seconds = int(seconds)
        return f"{seconds} seconds"
    cleaned_interval = interval.replace("INTERVAL", "").strip()
    return cleaned_interval.replace("'", "").replace('"', "")


def _quote_qualified_identifier(identifier: str) -> str:
    if not identifier or not identifier.strip():
        raise ValueError("identifier is required")
    return ".".join(
        _IDENTIFIER_PREPARER.quote_identifier(part.strip())
        for part in identifier.split(".")
        if part.strip()
    )


def _quote_column_names(column_names: list[str] | tuple[str, ...] | None) -> str:
    if not column_names:
        return ""
    quoted_columns = ", ".join(
        _IDENTIFIER_PREPARER.quote_identifier(column_name)
        for column_name in column_names
    )
    return f" ({quoted_columns})"


def _format_option_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, timedelta):
        return f"'{_clean_interval(value)}'"
    escaped_value = str(value).replace("'", "''")
    return f"'{escaped_value}'"


def _policy_offset_sql(bind_name: str, value: PolicyOffset) -> tuple[str, Any | None]:
    if value is None:
        return "NULL", None
    if isinstance(value, timedelta):
        return f"CAST(:{bind_name} AS INTERVAL)", _clean_interval(value)
    if isinstance(value, str):
        return f"CAST(:{bind_name} AS INTERVAL)", _clean_interval(value)
    return f":{bind_name}", value


def _append_optional_arg(
    args: list[str],
    params: dict[str, Any],
    name: str,
    value: Any,
) -> None:
    if value is None:
        return
    args.append(f"{name} => :{name}")
    params[name] = value


def _refresh_window_sql(bind_name: str, value: RefreshWindow) -> tuple[str, Any | None]:
    if value is None:
        return "NULL", None
    if isinstance(value, timedelta):
        return f"CAST(:{bind_name} AS INTERVAL)", _clean_interval(value)
    if isinstance(value, str) and value.upper().strip().startswith("INTERVAL"):
        return f"CAST(:{bind_name} AS INTERVAL)", _clean_interval(value)
    return f":{bind_name}", value


def format_create_continuous_aggregate_sql(
    view_name: str,
    select_query: str,
    column_names: list[str] | tuple[str, ...] | None = None,
    chunk_interval: str | timedelta | None = None,
    create_group_indexes: bool | None = None,
    finalized: bool | None = None,
    materialized_only: bool | None = None,
    invalidate_using: str | None = None,
    with_data: bool = True,
) -> str:
    """
    Format a CREATE MATERIALIZED VIEW statement for a continuous aggregate.
    """
    if not select_query or not select_query.strip():
        raise ValueError("select_query is required")

    options = ["timescaledb.continuous"]
    if chunk_interval is not None:
        options.append(
            "timescaledb.chunk_interval = "
            f"{_format_option_value(_clean_interval(chunk_interval))}"
        )
    if create_group_indexes is not None:
        options.append(
            "timescaledb.create_group_indexes = "
            f"{_format_option_value(create_group_indexes)}"
        )
    if finalized is not None:
        options.append(f"timescaledb.finalized = {_format_option_value(finalized)}")
    if materialized_only is not None:
        options.append(
            "timescaledb.materialized_only = "
            f"{_format_option_value(materialized_only)}"
        )
    if invalidate_using is not None:
        options.append(
            "timescaledb.invalidate_using = "
            f"{_format_option_value(invalidate_using)}"
        )

    data_clause = "WITH DATA" if with_data else "WITH NO DATA"
    return f"""
CREATE MATERIALIZED VIEW {_quote_qualified_identifier(view_name)}{_quote_column_names(column_names)}
WITH ({", ".join(options)})
AS
{select_query.strip()}
{data_clause};
""".strip()


def format_add_generated_aggregate_column_sql(
    continuous_aggregate: str,
    column_name: str,
    data_type: str,
    aggregate_expression: str,
) -> str:
    """
    Format SQL to add a generated aggregate column to a continuous aggregate.
    """
    if not data_type or not data_type.strip():
        raise ValueError("data_type is required")
    if not aggregate_expression or not aggregate_expression.strip():
        raise ValueError("aggregate_expression is required")
    quoted_column_name = _IDENTIFIER_PREPARER.quote_identifier(column_name)
    return f"""
ALTER MATERIALIZED VIEW {_quote_qualified_identifier(continuous_aggregate)}
ADD COLUMN {quoted_column_name} {data_type.strip()}
GENERATED ALWAYS AS ({aggregate_expression.strip()}) STORED;
""".strip()


def format_refresh_continuous_aggregate_sql_query(
    continuous_aggregate: str,
    window_start: RefreshWindow = None,
    window_end: RefreshWindow = None,
    force: bool = False,
    refresh_newest_first: bool | None = None,
) -> str:
    """
    Format a TimescaleDB refresh_continuous_aggregate call.
    """
    start_sql, start_value = _refresh_window_sql("window_start", window_start)
    end_sql, end_value = _refresh_window_sql("window_end", window_end)

    args = [":continuous_aggregate", start_sql, end_sql]
    params: dict[str, Any] = {"continuous_aggregate": continuous_aggregate}

    if start_value is not None:
        params["window_start"] = start_value
    if end_value is not None:
        params["window_end"] = end_value
    if force:
        args.append("force => :force")
        params["force"] = force
    if refresh_newest_first is not None:
        args.append("refresh_newest_first => :refresh_newest_first")
        params["refresh_newest_first"] = refresh_newest_first

    sql_template = f"""
CALL refresh_continuous_aggregate(
    {", ".join(args)}
);
"""
    return _compile_sql(sql_template, params)


def format_add_continuous_aggregate_policy_sql_query(
    continuous_aggregate: str,
    start_offset: PolicyOffset,
    end_offset: PolicyOffset,
    schedule_interval: str | timedelta,
    initial_start: datetime | None = None,
    if_not_exists: bool = False,
    timezone: str | None = None,
    include_tiered_data: bool | None = None,
    buckets_per_batch: int | None = None,
    max_batches_per_execution: int | None = None,
    refresh_newest_first: bool | None = None,
) -> str:
    """
    Format a TimescaleDB add_continuous_aggregate_policy call.
    """
    start_sql, start_value = _policy_offset_sql("start_offset", start_offset)
    end_sql, end_value = _policy_offset_sql("end_offset", end_offset)
    schedule_sql, schedule_value = _policy_offset_sql(
        "schedule_interval",
        schedule_interval,
    )
    if schedule_value is None:
        raise ValueError("schedule_interval is required")

    args = [
        ":continuous_aggregate",
        f"start_offset => {start_sql}",
        f"end_offset => {end_sql}",
        f"schedule_interval => {schedule_sql}",
    ]
    params: dict[str, Any] = {
        "continuous_aggregate": continuous_aggregate,
        "schedule_interval": schedule_value,
    }
    if start_value is not None:
        params["start_offset"] = start_value
    if end_value is not None:
        params["end_offset"] = end_value

    _append_optional_arg(args, params, "initial_start", initial_start)
    if if_not_exists:
        _append_optional_arg(args, params, "if_not_exists", if_not_exists)
    _append_optional_arg(args, params, "timezone", timezone)
    _append_optional_arg(args, params, "include_tiered_data", include_tiered_data)
    _append_optional_arg(args, params, "buckets_per_batch", buckets_per_batch)
    _append_optional_arg(
        args,
        params,
        "max_batches_per_execution",
        max_batches_per_execution,
    )
    _append_optional_arg(args, params, "refresh_newest_first", refresh_newest_first)

    sql_template = f"""
SELECT add_continuous_aggregate_policy(
    {", ".join(args)}
);
"""
    return _compile_sql(sql_template, params)


def format_remove_continuous_aggregate_policy_sql_query(
    continuous_aggregate: str,
    if_exists: bool = True,
) -> str:
    sql_template = """
SELECT remove_continuous_aggregate_policy(
    :continuous_aggregate,
    if_exists => :if_exists
);
"""
    return _compile_sql(
        sql_template,
        {
            "continuous_aggregate": continuous_aggregate,
            "if_exists": if_exists,
        },
    )
