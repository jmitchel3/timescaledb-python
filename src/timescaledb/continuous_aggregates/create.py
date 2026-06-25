from datetime import timedelta

import sqlalchemy
from sqlmodel import Session

from timescaledb.continuous_aggregates import sql


def create_continuous_aggregate(
    session: Session,
    view_name: str,
    select_query: str,
    column_names: list[str] | tuple[str, ...] | None = None,
    chunk_interval: str | timedelta | None = None,
    create_group_indexes: bool | None = None,
    finalized: bool | None = None,
    materialized_only: bool | None = None,
    invalidate_using: str | None = None,
    with_data: bool = True,
    commit: bool = True,
) -> None:
    """
    Create a TimescaleDB continuous aggregate materialized view.
    """
    sql_query = sql.format_create_continuous_aggregate_sql(
        view_name=view_name,
        select_query=select_query,
        column_names=column_names,
        chunk_interval=chunk_interval,
        create_group_indexes=create_group_indexes,
        finalized=finalized,
        materialized_only=materialized_only,
        invalidate_using=invalidate_using,
        with_data=with_data,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
