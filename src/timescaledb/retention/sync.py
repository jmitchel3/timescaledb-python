import logging
from typing import Type

from sqlmodel import Session, SQLModel

from timescaledb.models import TimescaleModel
from timescaledb.retention.add import add_retention_policy
from timescaledb.retention.list import list_retention_policies

logger = logging.getLogger(__name__)


def sync_retention_policies(
    session: Session,
    *models: Type[SQLModel],
    drop_after=None,
) -> None:
    """
    Create retention policies for all hypertables
    """
    # Use SQLAlchemy's transaction context
    with session.begin():
        if models:
            model_list = sorted(
                models, key=lambda m: m.__tablename__
            )  # Sort for consistent ordering
        else:
            model_list = sorted(
                [
                    model
                    for model in TimescaleModel.__subclasses__()
                    if getattr(model, "__table__", None) is not None
                ],
                key=lambda m: m.__tablename__,
            )

        current_policies = list_retention_policies(session)
        if current_policies is None:
            current_policies = []

        logger.info(f"Current retention policies: {current_policies}")
        logger.info(
            f"Syncing retention policies for models: {[m.__name__ for m in model_list]}"
        )

        for model in model_list:
            table_name = model.__tablename__
            if table_name in current_policies:
                logger.info(f"Retention policy for {model.__name__} already exists")
                continue

            logger.info(f"Adding retention policy for {model.__name__}")
            add_retention_policy(session, model, drop_after=drop_after)
