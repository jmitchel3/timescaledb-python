from __future__ import annotations

from django.apps import AppConfig

from timescaledb.django import _django_version_tuple


class TimescaleDBConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "timescaledb_django"
    name = "timescaledb.django"
    verbose_name = "TimescaleDB"

    def ready(self) -> None:
        _django_version_tuple()
