import logging
from typing import Type

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from timescaledb.compression.add import add_compression_policy
from timescaledb.compression.enable import enable_table_compression
from timescaledb.models import TimescaleModel

logger = logging.getLogger(__name__)


def sync_compression_policies(session: Session, *models: Type[SQLModel]) -> None:
    """
    Enable compression for all hypertables
    """
    if models:
        model_list = models
    else:
        model_list = [
            model
            for model in TimescaleModel.__subclasses__()
            if getattr(model, "__table__", None) is not None
        ]
    for model in model_list:
        compress_enabled = model.__enable_compression__
        if not compress_enabled:
            continue
        try:
            enable_table_compression(session, model, commit=False)
            add_compression_policy(session, model, commit=False)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(
                f"Error syncing compression policy for {model.__name__}: {e}"
            )
            raise
    session.commit()
