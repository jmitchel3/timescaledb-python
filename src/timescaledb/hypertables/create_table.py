from datetime import timedelta
from typing import Any, Type

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlmodel import Session, SQLModel

from timescaledb import cleaners
from timescaledb.defaults import TIME_COLUMN


_POSTGRES_DIALECT = postgresql.dialect()


def _clean_option_interval(value: str | int | timedelta) -> str | int:
    cleaned_value, interval_type = cleaners.clean_interval(value)
    if interval_type == "INVALID":
        raise ValueError("Invalid chunk interval")
    return cleaned_value


def _format_option_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    escaped_value = str(value).replace("'", "''")
    return f"'{escaped_value}'"


def format_create_table_with_hypertable_sql(
    model: Type[SQLModel],
    time_column: str | None = None,
    chunk_interval: str | int | timedelta | None = None,
    segmentby: str | None = None,
    orderby: str | None = None,
    create_default_indexes: bool | None = None,
    if_not_exists: bool = True,
) -> str:
    """
    Format a TimescaleDB 2.20+ CREATE TABLE statement with tsdb.hypertable.
    """
    if getattr(model, "__table__", None) is None:
        raise ValueError("model must be a table=True SQLModel")

    table = model.__table__
    time_column = time_column or getattr(model, "__time_column__", TIME_COLUMN)
    if time_column not in table.columns:
        raise ValueError(f"model table does not include partition column {time_column}")

    chunk_interval = chunk_interval or getattr(model, "__chunk_time_interval__", None)
    segmentby = segmentby or getattr(model, "__columnstore_segmentby__", None)
    orderby = orderby or getattr(model, "__columnstore_orderby__", None)

    compiled_table = str(
        CreateTable(table, if_not_exists=if_not_exists).compile(
            dialect=_POSTGRES_DIALECT
        )
    ).rstrip()

    options = [
        "tsdb.hypertable",
        f"tsdb.partition_column = {_format_option_value(time_column)}",
    ]
    if chunk_interval is not None:
        options.append(
            "tsdb.chunk_interval = "
            f"{_format_option_value(_clean_option_interval(chunk_interval))}"
        )
    if segmentby is not None:
        options.append(f"tsdb.segmentby = {_format_option_value(segmentby)}")
    if orderby is not None:
        options.append(f"tsdb.orderby = {_format_option_value(orderby)}")
    if create_default_indexes is not None:
        options.append(
            "tsdb.create_default_indexes = "
            f"{_format_option_value(create_default_indexes)}"
        )

    return f"{compiled_table}\nWITH ({', '.join(options)});"


def create_table_with_hypertable(
    session: Session,
    model: Type[SQLModel],
    commit: bool = True,
    time_column: str | None = None,
    chunk_interval: str | int | timedelta | None = None,
    segmentby: str | None = None,
    orderby: str | None = None,
    create_default_indexes: bool | None = None,
    if_not_exists: bool = True,
) -> None:
    """
    Create a table directly as a TimescaleDB hypertable.
    """
    sql_query = format_create_table_with_hypertable_sql(
        model=model,
        time_column=time_column,
        chunk_interval=chunk_interval,
        segmentby=segmentby,
        orderby=orderby,
        create_default_indexes=create_default_indexes,
        if_not_exists=if_not_exists,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
