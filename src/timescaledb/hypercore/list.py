import sqlalchemy
from sqlmodel import Session

from timescaledb.hypercore import sql


def list_columnstore_policies(session: Session) -> list[str]:
    """
    List hypertables with TimescaleDB Hypercore columnstore policies.
    """
    sql_query = sql.list_columnstore_policies_sql_query()
    results = session.execute(sqlalchemy.text(sql_query)).fetchall()
    return [row[0] for row in results]
