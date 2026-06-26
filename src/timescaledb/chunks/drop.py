from typing import Any, List, Optional, Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.chunks import sql
from timescaledb.chunks.utils import resolve_table_name


def drop_chunks(
    session: Session,
    table_name: Optional[str] = None,
    model: Optional[Type[SQLModel]] = None,
    older_than: Optional[Any] = None,
    newer_than: Optional[Any] = None,
    created_before: Optional[Any] = None,
    created_after: Optional[Any] = None,
) -> List[str]:
    """
    Drop chunks of a hypertable that fall within the given time range.

    This is the imperative counterpart to an automated retention policy
    (``add_retention_policy``): use it for ad-hoc cleanup or to correct a
    backfill. At least one range bound is required so an entire hypertable
    cannot be emptied by accident.

    Args:
        session: SQLAlchemy/SQLModel session
        table_name: Name of the hypertable (or pass ``model``)
        model: A ``TimescaleModel``/``SQLModel`` class to resolve the table from
        older_than: Drop chunks whose time range is fully before this bound
        newer_than: Drop chunks whose time range is fully after this bound
        created_before: Drop chunks created before this bound (TimescaleDB 2.8+)
        created_after: Drop chunks created after this bound (TimescaleDB 2.8+)

    Each bound accepts a ``datetime``/``date`` (treated as a timestamp) or a
    ``timedelta``/interval string (e.g. ``"3 days"``). ``older_than`` /
    ``newer_than`` additionally accept an ``int`` for integer-partitioned
    hypertables; ``created_before`` / ``created_after`` are always time-based.

    Returns:
        List[str]: The fully-qualified names of the dropped chunks.
    """
    table_name = resolve_table_name(table_name, model)
    sql_query = sql.format_drop_chunks_sql(
        table_name=table_name,
        older_than=older_than,
        newer_than=newer_than,
        created_before=created_before,
        created_after=created_after,
    )
    rows = session.execute(sqlalchemy.text(sql_query)).fetchall()
    return [row[0] for row in rows]
