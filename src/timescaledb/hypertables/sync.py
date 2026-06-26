import logging
from typing import Type

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from timescaledb.hypertables.create import create_hypertable
from timescaledb.hypertables.list import list_hypertables
from timescaledb.models import TimescaleModel

logger = logging.getLogger(__name__)


def sync_all_hypertables(session: Session, *models: Type[SQLModel]) -> None:
    """
    Set up hypertables for all models that inherit from TimescaleModel.
    If no models are provided, all SQLModel subclasses in the current SQLModel registry will be checked.

    Args:
        session: SQLModel session
        *models: Optional specific models to set up. If none provided, all models will be checked.
    """
    if models:
        model_list = models
    else:
        # Get all TimescaleModel subclasses that have table=True
        model_list = [
            model
            for model in TimescaleModel.__subclasses__()
            if getattr(model, "__table__", None) is not None
        ]
    current_hypertables = [x.hypertable_name for x in list_hypertables(session)]
    for model in model_list:
        if model.__tablename__ in current_hypertables:
            logger.info(f"Hypertable for `{model.__name__}` exists. Skipping...")
            continue
        try:
            create_hypertable(
                session,
                commit=False,
                model=model,
                table_name=None,
                hypertable_options={
                    "if_not_exists": True,
                    "migrate_data": True,
                },
            )
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error creating hypertable for {model.__name__}: {e}")
            raise
    session.commit()
