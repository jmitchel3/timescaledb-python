from typing import Type

from sqlmodel import Session, SQLModel

from timescaledb.hypercore.add import add_columnstore_policy
from timescaledb.hypercore.enable import enable_columnstore
from timescaledb.models import TimescaleModel


def sync_columnstore_policies(session: Session, *models: Type[SQLModel]) -> None:
    """
    Enable columnstore and policies for TimescaleModel subclasses that opt in.
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
        if not getattr(model, "__enable_columnstore__", False):
            continue
        enable_columnstore(session, model=model, commit=False)
        add_columnstore_policy(session, model=model, commit=False)
    session.commit()
