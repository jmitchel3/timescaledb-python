import sqlalchemy
from sqlmodel import Session

from timescaledb.continuous_aggregates import sql


def add_generated_aggregate_column(
    session: Session,
    continuous_aggregate: str,
    column_name: str,
    data_type: str,
    aggregate_expression: str,
    commit: bool = True,
) -> None:
    """
    Add a generated aggregate column to an existing continuous aggregate.
    """
    sql_query = sql.format_add_generated_aggregate_column_sql(
        continuous_aggregate=continuous_aggregate,
        column_name=column_name,
        data_type=data_type,
        aggregate_expression=aggregate_expression,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
