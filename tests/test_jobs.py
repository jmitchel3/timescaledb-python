from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlmodel import Session

from timescaledb import (
    alter_job,
    delete_job,
    get_job_stats,
    list_jobs,
    run_job,
)
from timescaledb.jobs import sql
from timescaledb.jobs.schemas import JobSchema, JobStatsSchema

from .conftest import RetentionModel


def _retention_job_id(session: Session) -> int:
    jobs = list_jobs(session, proc_name="policy_retention")
    assert jobs, "expected the autouse fixture to create retention jobs"
    return jobs[0].job_id


# ---------------------------------------------------------------------------
# Integration tests (require the TimescaleDB container)
# ---------------------------------------------------------------------------


def test_list_jobs_returns_jobs(session: Session):
    jobs = list_jobs(session)
    assert len(jobs) > 0
    assert all(isinstance(job, JobSchema) for job in jobs)
    assert all(isinstance(job.job_id, int) for job in jobs)
    # The autouse fixture syncs retention policies for every hypertable.
    assert any(job.proc_name == "policy_retention" for job in jobs)


def test_list_jobs_filter_by_proc_name(session: Session):
    jobs = list_jobs(session, proc_name="policy_retention")
    assert len(jobs) > 0
    assert all(job.proc_name == "policy_retention" for job in jobs)


def test_list_jobs_filter_by_hypertable(session: Session):
    table_name = RetentionModel.__tablename__
    jobs = list_jobs(session, hypertable_name=table_name)
    assert len(jobs) > 0
    assert all(job.hypertable_name == table_name for job in jobs)


def test_get_job_stats_all(session: Session):
    stats = get_job_stats(session)
    assert len(stats) > 0
    assert all(isinstance(stat, JobStatsSchema) for stat in stats)


def test_get_job_stats_by_job_id(session: Session):
    job_id = _retention_job_id(session)
    stats = get_job_stats(session, job_id=job_id)
    assert len(stats) == 1
    assert stats[0].job_id == job_id


def test_get_job_stats_by_hypertable(session: Session):
    table_name = RetentionModel.__tablename__
    stats = get_job_stats(session, hypertable_name=table_name)
    assert len(stats) > 0
    assert all(stat.hypertable_name == table_name for stat in stats)


def test_list_jobs_handles_infinity_next_start(session: Session):
    """A paused/disabled job reports ``next_start = '-infinity'``, which psycopg
    cannot decode into a ``datetime``; a plain ``SELECT *`` raises ``DataError``
    while fetching the row. ``list_jobs`` must coalesce the sentinel to ``None``
    instead of crashing.

    The scheduler only writes the sentinel asynchronously, so to keep the test
    deterministic we inject the offending ``bgw_job_stat`` row directly.
    """
    job_id = _retention_job_id(session)
    session.execute(
        sqlalchemy.text(
            "INSERT INTO _timescaledb_internal.bgw_job_stat "
            "(job_id, last_start, last_finish, next_start, "
            " last_successful_finish, last_run_success, total_runs, "
            " total_duration, total_duration_failures, total_successes, "
            " total_failures, total_crashes, consecutive_failures, "
            " consecutive_crashes, flags) "
            "VALUES (:j, '-infinity', '-infinity', '-infinity', '-infinity', "
            " true, 0, INTERVAL '0', INTERVAL '0', 0, 0, 0, 0, 0, 0) "
            "ON CONFLICT (job_id) DO UPDATE SET next_start = '-infinity'"
        ),
        {"j": job_id},
    )
    session.commit()

    jobs = list_jobs(session)
    target = next(j for j in jobs if j.job_id == job_id)
    assert target.next_start is None


def test_run_job(session: Session):
    job_id = _retention_job_id(session)

    # Foreground-run the policy. It should complete without error even when
    # there is nothing to do, and the job must remain queryable afterwards.
    run_job(session, job_id)

    stats = get_job_stats(session, job_id=job_id)
    assert len(stats) == 1
    assert stats[0].job_id == job_id


def test_alter_job_disables_scheduling(session: Session):
    job_id = _retention_job_id(session)
    alter_job(session, job_id, schedule_interval="2 hours", scheduled=False)
    session.commit()

    job = list_jobs(session, proc_name="policy_retention")
    altered = next(j for j in job if j.job_id == job_id)
    assert altered.scheduled is False
    assert altered.schedule_interval == timedelta(hours=2)


def test_alter_job_with_timedelta_and_full_options(session: Session):
    job_id = _retention_job_id(session)
    alter_job(
        session,
        job_id,
        schedule_interval=timedelta(hours=6),
        max_runtime="5 minutes",
        max_retries=3,
        retry_period=timedelta(minutes=1),
        scheduled=True,
        next_start=datetime.now(timezone.utc) + timedelta(days=1),
        if_exists=True,
    )
    session.commit()

    altered = next(
        j for j in list_jobs(session) if j.job_id == job_id
    )
    assert altered.schedule_interval == timedelta(hours=6)


def test_delete_job(session: Session):
    job_id = _retention_job_id(session)
    delete_job(session, job_id)
    session.commit()

    remaining_ids = [job.job_id for job in list_jobs(session)]
    assert job_id not in remaining_ids


# ---------------------------------------------------------------------------
# Unit tests for the SQL builders (no database required)
# ---------------------------------------------------------------------------


def test_format_list_jobs_sql_no_filters():
    query = sql.format_list_jobs_sql()
    assert query.startswith("SELECT ")
    assert "FROM timescaledb_information.jobs ORDER BY job_id;" in query
    # next_start goes to ±infinity for paused jobs; it must be coalesced to NULL
    # so psycopg never tries to decode an infinite timestamp.
    assert "next_start = '-infinity'" in query
    # initial_start is the view's other timestamptz; it must not be selected at
    # all, or fetching a paused job would still raise DataError.
    assert "initial_start" not in query
    # SELECT * would re-introduce the infinity-decoding crash.
    assert "SELECT *" not in query


def test_format_list_jobs_sql_single_filter():
    query = sql.format_list_jobs_sql(hypertable_name="metrics")
    assert "WHERE hypertable_name = 'metrics'" in query
    assert "ORDER BY job_id" in query


def test_format_list_jobs_sql_both_filters():
    query = sql.format_list_jobs_sql(
        hypertable_name="metrics", proc_name="policy_retention"
    )
    assert "hypertable_name = 'metrics'" in query
    assert "proc_name = 'policy_retention'" in query
    assert " AND " in query


def test_format_job_stats_sql_no_filters():
    query = sql.format_job_stats_sql()
    assert query.startswith("SELECT ")
    assert "FROM timescaledb_information.job_stats" in query
    assert "ORDER BY job_id;" in query
    # ±infinity timestamps are normalised to NULL.
    assert "last_successful_finish = '-infinity'" in query


def test_format_job_stats_sql_by_job_id():
    query = sql.format_job_stats_sql(job_id=42)
    assert "WHERE job_id = 42" in query


def test_format_run_job_sql():
    assert sql.format_run_job_sql(7) == "CALL run_job(7);"


def test_format_delete_job_sql():
    assert sql.format_delete_job_sql(7) == "SELECT delete_job(7);"


def test_format_alter_job_sql_job_id_only():
    assert sql.format_alter_job_sql(7) == "SELECT alter_job(7);"


def test_format_alter_job_sql_interval_string():
    query = sql.format_alter_job_sql(7, schedule_interval="INTERVAL '2 hours'")
    assert query == "SELECT alter_job(7, schedule_interval => INTERVAL '2 hours');"


def test_format_alter_job_sql_interval_timedelta():
    query = sql.format_alter_job_sql(7, retry_period=timedelta(minutes=1))
    assert "retry_period => make_interval(secs => 60.0)" in query


def test_format_alter_job_sql_all_options():
    query = sql.format_alter_job_sql(
        7,
        schedule_interval="1 day",
        max_runtime="5 minutes",
        max_retries=3,
        retry_period="1 minute",
        scheduled=False,
        next_start=datetime(2024, 1, 1),
        if_exists=True,
    )
    assert "schedule_interval => INTERVAL '1 day'" in query
    assert "max_runtime => INTERVAL '5 minutes'" in query
    assert "max_retries => 3" in query
    assert "retry_period => INTERVAL '1 minute'" in query
    assert "scheduled => false" in query
    assert "next_start => CAST('2024-01-01T00:00:00' AS timestamptz)" in query
    assert "if_exists => true" in query


def test_format_alter_job_sql_next_start_string():
    query = sql.format_alter_job_sql(7, next_start="2024-01-01 00:00:00")
    assert "next_start => CAST('2024-01-01 00:00:00' AS timestamptz)" in query
