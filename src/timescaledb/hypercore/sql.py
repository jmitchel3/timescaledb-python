from datetime import timedelta
from typing import Any

import sqlalchemy
from sqlalchemy.dialects import postgresql


_POSTGRES_DIALECT = postgresql.dialect()
_IDENTIFIER_PREPARER = _POSTGRES_DIALECT.identifier_preparer


def quote_qualified_identifier(identifier: str) -> str:
    """Quote a table or schema-qualified table identifier for DDL statements."""
    if not identifier or not identifier.strip():
        raise ValueError("identifier is required")
    return ".".join(
        _IDENTIFIER_PREPARER.quote_identifier(part.strip())
        for part in identifier.split(".")
        if part.strip()
    )


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


def _clean_interval_value(value: str | int | timedelta) -> tuple[str | int, str]:
    if isinstance(value, timedelta):
        seconds = value.total_seconds()
        if seconds.is_integer():
            seconds = int(seconds)
        return f"{seconds} seconds", "INTERVAL"
    if isinstance(value, int):
        return value, "INTEGER"
    if isinstance(value, str):
        cleaned = value.replace("INTERVAL", "").strip()
        cleaned = cleaned.replace("'", "").replace('"', "")
        return cleaned, "INTERVAL"
    return value, "INVALID"


def _policy_interval_sql(
    bind_name: str,
    value: str | int | timedelta,
    *,
    allow_integer: bool,
) -> tuple[str, str | int]:
    cleaned_value, interval_type = _clean_interval_value(value)
    if interval_type == "INTERVAL":
        return f"CAST(:{bind_name} AS INTERVAL)", cleaned_value
    if interval_type == "INTEGER" and allow_integer:
        return f"CAST(:{bind_name} AS BIGINT)", cleaned_value
    raise ValueError("Invalid interval type")


def format_enable_columnstore_sql(
    table_name: str,
    orderby: str | None = None,
    segmentby: str | None = None,
) -> str:
    clauses = ["timescaledb.enable_columnstore = true"]
    params: dict[str, str] = {}

    if orderby is not None:
        clauses.append("timescaledb.orderby = :orderby")
        params["orderby"] = orderby
    if segmentby is not None:
        clauses.append("timescaledb.segmentby = :segmentby")
        params["segmentby"] = segmentby

    sql_template = f"""
ALTER TABLE {quote_qualified_identifier(table_name)} SET (
    {", ".join(clauses)}
);
"""
    return _compile_sql(sql_template, params)


def format_add_columnstore_policy_sql_query(
    table_name: str,
    after: str | int | timedelta | None = None,
    created_before: str | timedelta | None = None,
    schedule_interval: str | timedelta | None = None,
    initial_start: Any = None,
    timezone: str | None = None,
    if_not_exists: bool = False,
) -> str:
    if (after is None and created_before is None) or (
        after is not None and created_before is not None
    ):
        raise ValueError("exactly one of after or created_before is required")

    args = [":hypertable_name"]
    params: dict[str, Any] = {"hypertable_name": table_name}

    if after is not None:
        after_sql, after_value = _policy_interval_sql(
            "after",
            after,
            allow_integer=True,
        )
        args.append(f"after => {after_sql}")
        params["after"] = after_value

    if created_before is not None:
        created_before_sql, created_before_value = _policy_interval_sql(
            "created_before",
            created_before,
            allow_integer=False,
        )
        args.append(f"created_before => {created_before_sql}")
        params["created_before"] = created_before_value

    if schedule_interval is not None:
        schedule_interval_sql, schedule_interval_value = _policy_interval_sql(
            "schedule_interval",
            schedule_interval,
            allow_integer=False,
        )
        args.append(f"schedule_interval => {schedule_interval_sql}")
        params["schedule_interval"] = schedule_interval_value

    if initial_start is not None:
        args.append("initial_start => :initial_start")
        params["initial_start"] = initial_start

    if timezone is not None:
        args.append("timezone => :timezone")
        params["timezone"] = timezone

    args.append("if_not_exists => :if_not_exists")
    params["if_not_exists"] = if_not_exists

    sql_template = f"""
CALL add_columnstore_policy(
    {", ".join(args)}
);
"""
    return _compile_sql(sql_template, params)


def format_remove_columnstore_policy_sql_query(
    table_name: str,
    if_exists: bool = True,
) -> str:
    sql_template = """
CALL remove_columnstore_policy(
    :hypertable_name,
    if_exists => :if_exists
);
"""
    return _compile_sql(
        sql_template,
        {"hypertable_name": table_name, "if_exists": if_exists},
    )


def format_convert_to_columnstore_sql_query(
    chunk_name: str,
    if_not_columnstore: bool = True,
    recompress: bool = False,
) -> str:
    sql_template = """
CALL convert_to_columnstore(
    :chunk_name,
    if_not_columnstore => :if_not_columnstore,
    recompress => :recompress
);
"""
    return _compile_sql(
        sql_template,
        {
            "chunk_name": chunk_name,
            "if_not_columnstore": if_not_columnstore,
            "recompress": recompress,
        },
    )


def format_convert_to_rowstore_sql_query(
    chunk_name: str,
    if_compressed: bool = True,
) -> str:
    sql_template = """
CALL convert_to_rowstore(
    :chunk_name,
    if_compressed => :if_compressed
);
"""
    return _compile_sql(
        sql_template,
        {"chunk_name": chunk_name, "if_compressed": if_compressed},
    )


LIST_COLUMNSTORE_POLICIES_SQL = """
SELECT DISTINCT hypertable_name
FROM timescaledb_information.jobs
WHERE application_name LIKE 'Columnstore%';
"""


def list_columnstore_policies_sql_query() -> str:
    return LIST_COLUMNSTORE_POLICIES_SQL
