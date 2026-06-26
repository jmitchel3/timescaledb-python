from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.postgres.fields import ArrayField
from django.db.models import DateTimeField
from django.db.models import Expression
from django.db.models import F
from django.db.models import FloatField
from django.db.models import Func
from django.db.models import IntegerField
from django.db.models import Value

from timescaledb.django import _django_version_tuple

_django_version_tuple()


def _clean_interval(interval: str | timedelta) -> str:
    if isinstance(interval, timedelta):
        seconds: int | float = interval.total_seconds()
        if seconds.is_integer():
            seconds = int(seconds)
        return f"{seconds} seconds"
    cleaned_interval = interval.replace("INTERVAL", "").strip()
    return cleaned_interval.replace("'", "").replace('"', "")


class _IntervalOrIntegerValue(Value):
    def __init__(self, value: str | int | timedelta, allow_integer: bool = True):
        self.allow_integer = allow_integer
        super().__init__(value)

    def as_sql(self, compiler: Any, connection: Any) -> tuple[str, list[Any]]:
        if isinstance(self.value, int):
            if not self.allow_integer:
                raise ValueError("integer offsets require an integer bucket width")
            return "%s", [self.value]
        if isinstance(self.value, (str, timedelta)):
            return "CAST(%s AS INTERVAL)", [_clean_interval(self.value)]
        raise ValueError("interval value must be a string, integer, or timedelta")


def _field_expression(value: Any) -> Expression:
    if isinstance(value, str):
        return F(value)
    if hasattr(value, "resolve_expression"):
        return value
    return Value(value)


def _literal_expression(value: Any) -> Expression:
    if hasattr(value, "resolve_expression"):
        return value
    return Value(value)


class TimeBucket(Func):
    function = "time_bucket"

    def __init__(
        self,
        bucket_width: str | int | timedelta,
        expression: Any,
        *,
        timezone: str | None = None,
        origin: Any = None,
        offset: str | int | timedelta | None = None,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        integer_bucket = isinstance(bucket_width, int)
        if integer_bucket and timezone is not None:
            raise ValueError("timezone is not supported for integer time buckets")

        expressions: list[Expression] = [
            _IntervalOrIntegerValue(bucket_width),
            _field_expression(expression),
        ]
        if timezone is not None:
            expressions.append(Value(timezone))
        if origin is not None:
            expressions.append(_literal_expression(origin))
        if offset is not None:
            expressions.append(
                _IntervalOrIntegerValue(offset, allow_integer=integer_bucket)
            )

        super().__init__(
            *expressions,
            output_field=output_field or DateTimeField(),
            **extra,
        )


class TimeBucketGapfill(Func):
    function = "time_bucket_gapfill"

    def __init__(
        self,
        bucket_width: str | int | timedelta,
        expression: Any,
        *,
        timezone: str | None = None,
        start: Any = None,
        finish: Any = None,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        integer_bucket = isinstance(bucket_width, int)
        if integer_bucket and timezone is not None:
            raise ValueError("timezone is not supported for integer gapfill buckets")

        expressions: list[Expression] = [
            _IntervalOrIntegerValue(bucket_width),
            _field_expression(expression),
        ]
        if timezone is not None:
            expressions.append(Value(timezone))
        if start is not None:
            expressions.append(_literal_expression(start))
        if finish is not None:
            expressions.append(_literal_expression(finish))

        super().__init__(
            *expressions,
            output_field=output_field or DateTimeField(),
            **extra,
        )


class Histogram(Func):
    function = "histogram"

    def __init__(
        self,
        expression: Any,
        min_value: int | float,
        max_value: int | float,
        nbuckets: int,
        *,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        super().__init__(
            _field_expression(expression),
            Value(min_value),
            Value(max_value),
            Value(nbuckets),
            output_field=output_field or ArrayField(IntegerField()),
            **extra,
        )


class First(Func):
    function = "first"

    def __init__(
        self,
        expression: Any,
        time_expression: Any,
        *,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        super().__init__(
            _field_expression(expression),
            _field_expression(time_expression),
            output_field=output_field or FloatField(),
            **extra,
        )


class Last(First):
    function = "last"


class Locf(Func):
    function = "locf"

    def __init__(
        self,
        expression: Any,
        *,
        prev: Any = None,
        treat_null_as_missing: bool | None = None,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        expressions: list[Expression] = [_field_expression(expression)]
        if prev is not None:
            expressions.append(_literal_expression(prev))
        if treat_null_as_missing is not None:
            expressions.append(Value(treat_null_as_missing))
        super().__init__(
            *expressions,
            output_field=output_field or FloatField(),
            **extra,
        )


class Interpolate(Func):
    function = "interpolate"

    def __init__(
        self,
        expression: Any,
        *,
        prev: Any = None,
        next: Any = None,
        output_field: Any = None,
        **extra: Any,
    ) -> None:
        expressions: list[Expression] = [_field_expression(expression)]
        if prev is not None:
            expressions.append(_literal_expression(prev))
        if next is not None:
            expressions.append(_literal_expression(next))
        super().__init__(
            *expressions,
            output_field=output_field or FloatField(),
            **extra,
        )


__all__ = [
    "First",
    "Histogram",
    "Interpolate",
    "Last",
    "Locf",
    "TimeBucket",
    "TimeBucketGapfill",
]
