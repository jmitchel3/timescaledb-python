import sqlalchemy
from sqlmodel import Session

from timescaledb.hypercore import sql


def convert_to_columnstore(
    session: Session,
    chunk_name: str,
    if_not_columnstore: bool = True,
    recompress: bool = False,
    commit: bool = True,
) -> None:
    """
    Manually convert one chunk to the TimescaleDB Hypercore columnstore.
    """
    sql_query = sql.format_convert_to_columnstore_sql_query(
        chunk_name,
        if_not_columnstore=if_not_columnstore,
        recompress=recompress,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()


def convert_to_rowstore(
    session: Session,
    chunk_name: str,
    if_compressed: bool = True,
    commit: bool = True,
) -> None:
    """
    Manually convert one chunk from the columnstore back to the rowstore.
    """
    sql_query = sql.format_convert_to_rowstore_sql_query(
        chunk_name,
        if_compressed=if_compressed,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
