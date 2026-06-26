from typing import Any, List, Optional, Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.chunks import sql
from timescaledb.chunks.utils import resolve_table_name


def show_chunks(
    session: Session,
    table_name: Optional[str] = None,
    model: Optional[Type[SQLModel]] = None,
    older_than: Optional[Any] = None,
    newer_than: Optional[Any] = None,
    created_before: Optional[Any] = None,
    created_after: Optional[Any] = None,
) -> List[str]:
    """
    List the chunks of a hypertable, optionally filtered by a time range.

    Args:
        session: SQLAlchemy/SQLModel session
        table_name: Name of the hypertable (or pass ``model``)
        model: A ``TimescaleModel``/``SQLModel`` class to resolve the table from
        older_than: Only chunks whose time range is fully before this bound
        newer_than: Only chunks whose time range is fully after this bound
        created_before: Only chunks created before this bound (TimescaleDB 2.8+)
        created_after: Only chunks created after this bound (TimescaleDB 2.8+)

    Each bound accepts a ``datetime``/``date`` (treated as a timestamp) or a
    ``timedelta``/interval string (e.g. ``"3 days"``). ``older_than`` /
    ``newer_than`` additionally accept an ``int`` for integer-partitioned
    hypertables; ``created_before`` / ``created_after`` are always time-based.

    Returns:
        List[str]: The fully-qualified names of the matching chunks.
    """
    table_name = resolve_table_name(table_name, model)
    sql_query = sql.format_show_chunks_sql(
        table_name=table_name,
        older_than=older_than,
        newer_than=newer_than,
        created_before=created_before,
        created_after=created_after,
    )
    rows = session.execute(sqlalchemy.text(sql_query)).fetchall()
    return [row[0] for row in rows]
