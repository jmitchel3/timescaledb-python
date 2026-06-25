from typing import Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.hypercore import extractors, sql


def enable_columnstore(
    session: Session,
    model: Type[SQLModel] = None,
    table_name: str = None,
    commit: bool = True,
    orderby: str | None = None,
    segmentby: str | None = None,
) -> None:
    """
    Enable TimescaleDB Hypercore columnstore for a hypertable.
    """
    if model is None and table_name is None:
        raise ValueError("model or table_name is required to enable columnstore")

    table_name_to_use = table_name
    if model is not None:
        columnstore_params = extractors.extract_model_columnstore_params(model)
        if columnstore_params is None:
            return
        table_name_to_use = columnstore_params["table_name"]
        if orderby is None:
            orderby = columnstore_params.get("orderby")
        if segmentby is None:
            segmentby = columnstore_params.get("segmentby")

    sql_query = sql.format_enable_columnstore_sql(
        table_name_to_use,
        orderby=orderby,
        segmentby=segmentby,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
