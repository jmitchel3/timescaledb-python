from __future__ import annotations

from typing import Any

MIN_DJANGO_VERSION = (5, 2)


def _format_version(version: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in version[:3])


def _validate_django_version(version: tuple[Any, ...]) -> tuple[Any, ...]:
    if version < MIN_DJANGO_VERSION:
        found = _format_version(version)
        minimum = _format_version(MIN_DJANGO_VERSION)
        raise ImportError(
            f"timescaledb.django supports Django {minimum} and newer; "
            f"found Django {found}."
        )
    return version


def _django_version_tuple() -> tuple[Any, ...]:
    try:
        import django
    except ImportError as exc:
        raise ImportError(
            "timescaledb.django requires Django 5.2 or newer. "
            'Install it with `pip install "timescaledb[django]"`.'
        ) from exc
    return _validate_django_version(django.VERSION)


DJANGO_VERSION = _django_version_tuple()

__all__ = ["DJANGO_VERSION", "MIN_DJANGO_VERSION"]
