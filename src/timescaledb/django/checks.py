from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.apps import AppConfig
from django.apps import apps
from django.core import checks


PRIMARY_KEY_EXCLUDES_TIME_COLUMN = "timescaledb.W001"


def _candidate_models(app_configs: Iterable[AppConfig] | None) -> list[type[Any]]:
    if app_configs is None:
        return list(apps.get_models())
    return [model for app_config in app_configs for model in app_config.get_models()]


def check_model_primary_key(model: type[Any]) -> list[checks.CheckMessage]:
    """
    Warn when a managed TimescaleModel's primary key excludes its time column.

    TimescaleDB requires every unique index on a hypertable, including the
    primary key, to contain the partitioning column. A model that keeps Django's
    implicit ``id`` primary key therefore cannot be turned into a hypertable by
    ``CreateHypertable``.
    """
    from timescaledb.django.db.models import TimescaleDateTimeField
    from timescaledb.django.db.models import TimescaleModel

    opts = model._meta
    if not issubclass(model, TimescaleModel) or not opts.managed:
        return []

    time_fields = [
        field
        for field in opts.concrete_fields
        if isinstance(field, TimescaleDateTimeField)
    ]
    if not time_fields:
        return []

    pk_field_names = {field.name for field in opts.pk_fields}
    if any(field.name in pk_field_names for field in time_fields):
        return []

    time_column = time_fields[0].name
    return [
        checks.Warning(
            f"The primary key of {opts.label} does not include its time column "
            f"'{time_column}', so CreateHypertable will fail: TimescaleDB requires "
            "every unique index on a hypertable to include the partitioning column.",
            hint=(
                "Declare a composite primary key that contains the time column, "
                f'e.g. pk = models.CompositePrimaryKey("<series_field>", "{time_column}").'
            ),
            obj=model,
            id=PRIMARY_KEY_EXCLUDES_TIME_COLUMN,
        )
    ]


def check_timescale_model_primary_keys(
    app_configs: Iterable[AppConfig] | None = None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    messages: list[checks.CheckMessage] = []
    for model in _candidate_models(app_configs):
        messages.extend(check_model_primary_key(model))
    return messages
