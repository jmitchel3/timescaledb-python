import sqlalchemy
from sqlmodel import Session

from timescaledb.hypercore import sql


def remove_columnstore_policy(
    session: Session,
    table_name: str,
    if_exists: bool = True,
    commit: bool = True,
) -> None:
    """
    Remove a TimescaleDB Hypercore columnstore policy from a hypertable.
    """
    sql_query = sql.format_remove_columnstore_policy_sql_query(
        table_name,
        if_exists=if_exists,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
