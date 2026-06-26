from typing import List, Optional

import sqlalchemy
from sqlmodel import Session

from timescaledb.jobs import sql
from timescaledb.jobs.schemas import JobSchema, JobStatsSchema


def list_jobs(
    session: Session,
    hypertable_name: Optional[str] = None,
    proc_name: Optional[str] = None,
) -> List[JobSchema]:
    """
    List the TimescaleDB background jobs.

    Args:
        session: SQLAlchemy/SQLModel session
        hypertable_name: Only jobs attached to this hypertable
        proc_name: Only jobs running this procedure (e.g. ``"policy_retention"``,
            ``"policy_compression"``, ``"policy_refresh_continuous_aggregate"``)

    Returns:
        List[JobSchema]: One entry per matching job.
    """
    sql_query = sql.format_list_jobs_sql(
        hypertable_name=hypertable_name,
        proc_name=proc_name,
    )
    rows = session.execute(sqlalchemy.text(sql_query)).fetchall()
    return [JobSchema(**dict(row._mapping)) for row in rows]


def get_job_stats(
    session: Session,
    job_id: Optional[int] = None,
    hypertable_name: Optional[str] = None,
) -> List[JobStatsSchema]:
    """
    Get run statistics for TimescaleDB background jobs.

    Args:
        session: SQLAlchemy/SQLModel session
        job_id: Only stats for this job
        hypertable_name: Only stats for jobs attached to this hypertable

    Returns:
        List[JobStatsSchema]: Run counters and last/next run information.
    """
    sql_query = sql.format_job_stats_sql(
        job_id=job_id,
        hypertable_name=hypertable_name,
    )
    rows = session.execute(sqlalchemy.text(sql_query)).fetchall()
    return [JobStatsSchema(**dict(row._mapping)) for row in rows]
