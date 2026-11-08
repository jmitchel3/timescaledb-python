from __future__ import annotations

from django.apps import AppConfig
from django.core import checks

from timescaledb.django import _django_version_tuple


class TimescaleDBConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "timescaledb_django"
    name = "timescaledb.django"
    verbose_name = "TimescaleDB"

    def ready(self) -> None:
        _django_version_tuple()

        from timescaledb.django.checks import check_timescale_model_primary_keys

        checks.register(check_timescale_model_primary_keys, checks.Tags.models)
