from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy


def _compile(sql: str, params: Dict[str, Any]) -> str:
    query = sqlalchemy.text(sql).bindparams(**params)
    return str(query.compile(compile_kwargs={"literal_binds": True}))


def _where(filters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Build a ``WHERE`` clause from non-None filters."""
    provided = {key: value for key, value in filters.items() if value is not None}
    if not provided:
        return "", {}
    clauses = [f"{column} = :{column}" for column in provided]
    return " WHERE " + " AND ".join(clauses), provided


def _select_columns(plain: Tuple[str, ...], ts: Tuple[str, ...]) -> str:
    """Render a column list that normalises ±infinity timestamps to NULL.

    ``timestamptz`` columns can hold ``-infinity``/``infinity`` (e.g. a paused
    job reports ``next_start = '-infinity'``), and psycopg cannot load those
    values into Python ``datetime`` objects; it raises ``DataError`` while
    fetching the row. We must therefore avoid ``SELECT *`` on these views and
    coalesce the infinities to ``NULL`` for every timestamptz column the driver
    would otherwise try to decode.
    """
    columns = list(plain)
    for column in ts:
        columns.append(
            f"CASE WHEN {column} = '-infinity' OR {column} = 'infinity' "
            f"THEN NULL ELSE {column} END AS {column}"
        )
    return ", ".join(columns)


# Columns of timescaledb_information.jobs that JobSchema consumes. ``next_start``
# is a timestamptz that goes to ±infinity for paused/disabled jobs, so it is
# normalised; ``initial_start`` is the view's other timestamptz and is omitted
# entirely so the driver never tries to decode an infinite value from it.
_JOBS_PLAIN_COLUMNS = (
    "job_id",
    "application_name",
    "proc_schema",
    "proc_name",
    "scheduled",
    "hypertable_schema",
    "hypertable_name",
    "schedule_interval",
    "config",
)
_JOBS_TS_COLUMNS = ("next_start",)


def format_list_jobs_sql(
    hypertable_name: Optional[str] = None,
    proc_name: Optional[str] = None,
) -> str:
    """Format a ``SELECT ... FROM timescaledb_information.jobs`` statement."""
    where, params = _where(
        {"hypertable_name": hypertable_name, "proc_name": proc_name}
    )
    sql = (
        f"SELECT {_select_columns(_JOBS_PLAIN_COLUMNS, _JOBS_TS_COLUMNS)} "
        f"FROM timescaledb_information.jobs{where} ORDER BY job_id;"
    )
    if not params:
        return sql
    return _compile(sql, params)


# Plain (non-timestamp) columns of timescaledb_information.job_stats.
_JOB_STATS_PLAIN_COLUMNS = (
    "hypertable_schema",
    "hypertable_name",
    "job_id",
    "last_run_status",
    "job_status",
    "last_run_duration",
    "total_runs",
    "total_successes",
    "total_failures",
)
# Timestamptz columns that can hold ±infinity (e.g. a job that has never
# succeeded reports last_successful_finish = '-infinity'). Those values cannot
# be converted to Python datetimes, so they are normalised to NULL.
_JOB_STATS_TS_COLUMNS = (
    "last_run_started_at",
    "last_successful_finish",
    "next_start",
)


def format_job_stats_sql(
    job_id: Optional[int] = None,
    hypertable_name: Optional[str] = None,
) -> str:
    """Format a ``SELECT ... FROM timescaledb_information.job_stats`` statement."""
    where, params = _where({"job_id": job_id, "hypertable_name": hypertable_name})
    columns = _select_columns(_JOB_STATS_PLAIN_COLUMNS, _JOB_STATS_TS_COLUMNS)
    sql = (
        f"SELECT {columns} "
        f"FROM timescaledb_information.job_stats{where} ORDER BY job_id;"
    )
    if not params:
        return sql
    return _compile(sql, params)


def format_run_job_sql(job_id: int) -> str:
    """Format a ``CALL run_job(...)`` statement."""
    return _compile("CALL run_job(:job_id);", {"job_id": job_id})


def format_delete_job_sql(job_id: int) -> str:
    """Format a ``SELECT delete_job(...)`` statement."""
    return _compile("SELECT delete_job(:job_id);", {"job_id": job_id})


def _interval_fragment(name: str, value: Any) -> Tuple[str, Dict[str, Any]]:
    if isinstance(value, timedelta):
        return f"{name} => make_interval(secs => :{name})", {name: value.total_seconds()}
    cleaned = str(value).replace("INTERVAL", "").strip().replace("'", "").replace('"', "")
    return f"{name} => INTERVAL :{name}", {name: cleaned}


def format_alter_job_sql(
    job_id: int,
    schedule_interval: Optional[Any] = None,
    max_runtime: Optional[Any] = None,
    max_retries: Optional[int] = None,
    retry_period: Optional[Any] = None,
    scheduled: Optional[bool] = None,
    next_start: Optional[Any] = None,
    if_exists: bool = False,
) -> str:
    """Format a ``SELECT alter_job(...)`` statement.

    Only the arguments that are explicitly provided are sent to ``alter_job`` so
    unspecified settings keep their current values.
    """
    fragments: List[str] = [":job_id"]
    params: Dict[str, Any] = {"job_id": job_id}

    for name, value in (
        ("schedule_interval", schedule_interval),
        ("max_runtime", max_runtime),
        ("retry_period", retry_period),
    ):
        if value is not None:
            fragment, fragment_params = _interval_fragment(name, value)
            fragments.append(fragment)
            params.update(fragment_params)

    if max_retries is not None:
        fragments.append("max_retries => :max_retries")
        params["max_retries"] = max_retries
    if scheduled is not None:
        fragments.append("scheduled => :scheduled")
        params["scheduled"] = scheduled
    if next_start is not None:
        value = next_start.isoformat() if isinstance(next_start, datetime) else str(
            next_start
        )
        fragments.append("next_start => CAST(:next_start AS timestamptz)")
        params["next_start"] = value
    if if_exists:
        fragments.append("if_exists => :if_exists")
        params["if_exists"] = True

    sql = f"SELECT alter_job({', '.join(fragments)});"
    return _compile(sql, params)
