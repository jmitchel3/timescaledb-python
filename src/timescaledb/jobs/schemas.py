from typing import Any, Dict, Optional

from pydantic import BaseModel


class JobSchema(BaseModel):
    """A row from ``timescaledb_information.jobs``.

    Background jobs are how TimescaleDB runs every automated policy created by
    this package: retention, compression/columnstore, and continuous-aggregate
    refresh.
    """

    job_id: int
    application_name: Optional[str] = None
    proc_schema: Optional[str] = None
    proc_name: str
    scheduled: bool = True
    hypertable_schema: Optional[str] = None
    hypertable_name: Optional[str] = None
    schedule_interval: Optional[Any] = None
    config: Optional[Dict[str, Any]] = None
    next_start: Optional[Any] = None


class JobStatsSchema(BaseModel):
    """A row from ``timescaledb_information.job_stats``.

    Use these counters to confirm in production that a policy is actually
    running and succeeding (e.g. a silently failing compression job).
    """

    job_id: int
    hypertable_schema: Optional[str] = None
    hypertable_name: Optional[str] = None
    last_run_started_at: Optional[Any] = None
    last_successful_finish: Optional[Any] = None
    last_run_status: Optional[str] = None
    job_status: Optional[str] = None
    last_run_duration: Optional[Any] = None
    next_start: Optional[Any] = None
    total_runs: Optional[int] = None
    total_successes: Optional[int] = None
    total_failures: Optional[int] = None
