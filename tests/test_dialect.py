"""Tests for the TimescaleDB SQLAlchemy dialects.

These verify that the ``timescaledb`` scheme URLs registered via the
``sqlalchemy.dialects`` entry points (see ``pyproject.toml``) resolve to the
expected PostgreSQL-backed dialect classes. They do not require a database
connection.
"""

import pytest
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine.url import make_url

from timescaledb.dialect import (
    TimescaledbAsyncpgDialect,
    TimescaledbPsycopg2Dialect,
    TimescaledbPsycopgDialect,
)


@pytest.mark.parametrize(
    "url, expected_dialect, expected_driver",
    [
        ("timescaledb://u:p@h:5432/db", TimescaledbPsycopg2Dialect, "psycopg2"),
        ("timescaledb+psycopg2://u:p@h:5432/db", TimescaledbPsycopg2Dialect, "psycopg2"),
        ("timescaledb+psycopg://u:p@h:5432/db", TimescaledbPsycopgDialect, "psycopg"),
        ("timescaledb+asyncpg://u:p@h:5432/db", TimescaledbAsyncpgDialect, "asyncpg"),
    ],
)
def test_dialect_url_resolution(url, expected_dialect, expected_driver):
    dialect_cls = make_url(url).get_dialect()
    assert dialect_cls is expected_dialect
    assert dialect_cls.driver == expected_driver
    assert dialect_cls.name == "timescaledb"


@pytest.mark.parametrize(
    "dialect_cls",
    [
        TimescaledbPsycopg2Dialect,
        TimescaledbPsycopgDialect,
        TimescaledbAsyncpgDialect,
    ],
)
def test_dialects_subclass_postgres(dialect_cls):
    # TimescaleDB is a PostgreSQL extension; every dialect must remain a
    # PostgreSQL dialect so reflection and SQL compilation behave like Postgres.
    assert issubclass(dialect_cls, PGDialect)
