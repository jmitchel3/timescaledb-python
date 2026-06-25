from datetime import datetime, timedelta

import sqlalchemy
from sqlmodel import Session

from timescaledb.continuous_aggregates import sql
from timescaledb.continuous_aggregates.sql import PolicyOffset


def add_continuous_aggregate_policy(
    session: Session,
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
    commit: bool = True,
) -> None:
    """
    Add a TimescaleDB refresh policy for a continuous aggregate.
    """
    sql_query = sql.format_add_continuous_aggregate_policy_sql_query(
        continuous_aggregate=continuous_aggregate,
        start_offset=start_offset,
        end_offset=end_offset,
        schedule_interval=schedule_interval,
        initial_start=initial_start,
        if_not_exists=if_not_exists,
        timezone=timezone,
        include_tiered_data=include_tiered_data,
        buckets_per_batch=buckets_per_batch,
        max_batches_per_execution=max_batches_per_execution,
        refresh_newest_first=refresh_newest_first,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()


def remove_continuous_aggregate_policy(
    session: Session,
    continuous_aggregate: str,
    if_exists: bool = True,
    commit: bool = True,
) -> None:
    """
    Remove a TimescaleDB refresh policy from a continuous aggregate.
    """
    sql_query = sql.format_remove_continuous_aggregate_policy_sql_query(
        continuous_aggregate=continuous_aggregate,
        if_exists=if_exists,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
