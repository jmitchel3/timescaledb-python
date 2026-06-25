from datetime import timedelta
from typing import Any, Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.hypercore import extractors, sql


def add_columnstore_policy(
    session: Session,
    model: Type[SQLModel] = None,
    table_name: str = None,
    commit: bool = True,
    after: str | int | timedelta | None = None,
    created_before: str | timedelta | None = None,
    schedule_interval: str | timedelta | None = None,
    initial_start: Any = None,
    timezone: str | None = None,
    if_not_exists: bool = False,
) -> None:
    """
    Add a TimescaleDB Hypercore policy that moves chunks to the columnstore.
    """
    if model is None and table_name is None:
        raise ValueError("model or table_name is required to add a columnstore policy")

    table_name_to_use = table_name
    if model is not None:
        policy_params = extractors.extract_model_columnstore_policy_params(model)
        if policy_params is None:
            return
        table_name_to_use = policy_params["table_name"]
        after = policy_params.get("after") if policy_params.get("after") else after
        created_before = (
            policy_params.get("created_before")
            if policy_params.get("created_before")
            else created_before
        )
        schedule_interval = (
            policy_params.get("schedule_interval")
            if policy_params.get("schedule_interval")
            else schedule_interval
        )
        timezone = policy_params.get("timezone") or timezone
        if_not_exists = policy_params.get("if_not_exists", if_not_exists)

        if after is None and created_before is None:
            return

    sql_query = sql.format_add_columnstore_policy_sql_query(
        table_name=table_name_to_use,
        after=after,
        created_before=created_before,
        schedule_interval=schedule_interval,
        initial_start=initial_start,
        timezone=timezone,
        if_not_exists=if_not_exists,
    )
    session.execute(sqlalchemy.text(sql_query))
    if commit:
        session.commit()
