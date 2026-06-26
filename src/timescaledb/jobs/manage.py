from typing import Any, Optional, cast

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session

from timescaledb.jobs import sql


def run_job(session: Session, job_id: int) -> None:
    """
    Run a TimescaleDB background job immediately.

    ``run_job`` is a stored procedure that manages its own transaction, so it
    must be invoked with autocommit on a connection separate from the session's
    open transaction.
    """
    engine = cast(Engine, session.get_bind())
    with engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        connection.execute(sqlalchemy.text(sql.format_run_job_sql(job_id)))


def alter_job(
    session: Session,
    job_id: int,
    schedule_interval: Optional[Any] = None,
    max_runtime: Optional[Any] = None,
    max_retries: Optional[int] = None,
    retry_period: Optional[Any] = None,
    scheduled: Optional[bool] = None,
    next_start: Optional[Any] = None,
    if_exists: bool = False,
) -> None:
    """
    Change the schedule or behaviour of an existing background job.

    Only the arguments you pass are altered; everything else keeps its current
    value. Intervals accept a ``timedelta`` or an interval string (e.g.
    ``"1 day"``); ``next_start`` accepts a ``datetime``.
    """
    sql_query = sql.format_alter_job_sql(
        job_id,
        schedule_interval=schedule_interval,
        max_runtime=max_runtime,
        max_retries=max_retries,
        retry_period=retry_period,
        scheduled=scheduled,
        next_start=next_start,
        if_exists=if_exists,
    )
    session.execute(sqlalchemy.text(sql_query))


def delete_job(session: Session, job_id: int) -> None:
    """Delete a TimescaleDB background job (and the policy it backs)."""
    session.execute(sqlalchemy.text(sql.format_delete_job_sql(job_id)))
