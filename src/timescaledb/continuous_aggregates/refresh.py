import sqlalchemy
from sqlmodel import Session

from timescaledb.continuous_aggregates import sql
from timescaledb.continuous_aggregates.sql import RefreshWindow


def refresh_continuous_aggregate(
    session: Session,
    continuous_aggregate: str,
    window_start: RefreshWindow = None,
    window_end: RefreshWindow = None,
    force: bool = False,
    refresh_newest_first: bool | None = None,
    commit: bool = True,
) -> None:
    """
    Refresh a TimescaleDB continuous aggregate over the requested window.
    """
    sql_query = sql.format_refresh_continuous_aggregate_sql_query(
        continuous_aggregate=continuous_aggregate,
        window_start=window_start,
        window_end=window_end,
        force=force,
        refresh_newest_first=refresh_newest_first,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
