from __future__ import annotations

from typing import Any

from django.db import models as django_models
from django.db.models import *  # noqa: F401,F403

from timescaledb.django import _django_version_tuple

_django_version_tuple()


class TimescaleDateTimeField(DateTimeField):  # type: ignore[name-defined]
    def __init__(self, *args: Any, interval: str = "1 day", **kwargs: Any) -> None:
        self.interval = interval
        kwargs.setdefault("db_index", True)
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str | None, str, list[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        if self.interval != "1 day":
            kwargs["interval"] = self.interval
        return name, path, args, kwargs


class TimescaleQuerySet(django_models.QuerySet):
    def time_bucket(
        self,
        interval: str | int,
        field_name: str = "time",
        alias: str = "bucket",
        **kwargs: Any,
    ) -> "TimescaleQuerySet":
        from timescaledb.django.db.functions import TimeBucket

        return self.annotate(**{alias: TimeBucket(interval, field_name, **kwargs)})

    def time_bucket_gapfill(
        self,
        interval: str | int,
        field_name: str = "time",
        alias: str = "bucket",
        **kwargs: Any,
    ) -> "TimescaleQuerySet":
        from timescaledb.django.db.functions import TimeBucketGapfill

        return self.annotate(
            **{alias: TimeBucketGapfill(interval, field_name, **kwargs)}
        )


class TimescaleManager(django_models.Manager.from_queryset(TimescaleQuerySet)):
    pass


class TimescaleModel(django_models.Model):
    objects = TimescaleManager()

    class Meta:
        abstract = True
