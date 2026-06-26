from typing import Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.hypertables.extractors import extract_model_hypertable_params
from timescaledb.hypertables.schemas import HypertableCreateSchema

# from timescaledb.hypertables.schemas import HypertableParams


def create_hypertable(
    session: Session,
    commit: bool = True,
    model: Type[SQLModel] = None,
    table_name: str = None,
    hypertable_options: dict = {
        "if_not_exists": True,
        "migrate_data": True,
    },
    overwrite_model_params: bool = False,
) -> None:
    """Create a TimescaleDB hypertable from a SQLModel class.

    This function converts a regular table into a TimescaleDB hypertable. Hypertable parameters
    can be specified either through model configuration or directly via hypertable_options.

    Args:
        session (Session): SQLAlchemy session instance
        commit (bool, optional): Whether to commit the transaction after creating the hypertable.
            Defaults to True.
        model (Type[SQLModel]): The SQLModel class to convert into a hypertable. Must have
            hypertable parameters defined either in the model or via hypertable_options.
        table_name (str, optional): Override the table name. If None, uses the model's table name.
        hypertable_options (dict, optional): Additional hypertable configuration options. Defaults to:
            {
                "if_not_exists": True,  # Skip if hypertable already exists
                "migrate_data": True,   # Migrate existing data to the hypertable
            }
        overwrite_model_params (bool, optional): If True, hypertable_options will override any
            conflicting parameters defined in the model. If False, model parameters take precedence.
            Defaults to False.

    Raises:
        ValueError: If model parameter is None.

    Example:
        ```python
        from timescaledb import TimescaleModel

        class Metrics(TimescaleModel, table=True):
            sensor_id: int
            value: float

             __time_column__: ClassVar[str] = "time"
            __chunk_time_interval__: ClassVar[str] = "INTERVAL 7 Days"
            # ... model fields ...

        # Create hypertable using model parameters
        create_hypertable(session, model=Metrics)

        # Create hypertable with custom options
        create_hypertable(
            session,
            model=Metrics,
            hypertable_options={
                "chunk_time_interval": timedelta(days=1),
                "if_not_exists": True
            },
            overwrite_model_params=True
        )
        ```
    """
    if model is None and table_name is None:
        raise ValueError("model or table_name is required")
    params = {
        "model": None,
        "table_name": table_name,
        **hypertable_options,
    }
    if model is not None:
        model_params = extract_model_hypertable_params(model)
        params = {**model_params}
        if overwrite_model_params:
            params.update(**hypertable_options)

    schema = HypertableCreateSchema(**params)
    query = schema.to_sql_query()
    session.execute(sqlalchemy.text(query))
    if commit:
        session.commit()
