"""SQLAlchemy dialects for TimescaleDB.

TimescaleDB is a PostgreSQL extension, so these dialects subclass the standard
PostgreSQL dialects shipped with SQLAlchemy and only override the dialect
``name`` so that SQLAlchemy / SQLModel can connect using ``timescaledb://``
URLs, e.g.::

    timescaledb://user:pass@host:5432/db            # default driver (psycopg2)
    timescaledb+psycopg2://user:pass@host:5432/db   # psycopg2
    timescaledb+psycopg://user:pass@host:5432/db    # psycopg (psycopg 3)
    timescaledb+asyncpg://user:pass@host:5432/db     # asyncpg

These are wired up through the ``sqlalchemy.dialects`` entry points declared in
``pyproject.toml``:

    timescaledb           -> TimescaledbPsycopg2Dialect
    timescaledb.psycopg2  -> TimescaledbPsycopg2Dialect
    timescaledb.psycopg   -> TimescaledbPsycopgDialect    (psycopg 3)
    timescaledb.asyncpg   -> TimescaledbAsyncpgDialect

Hypertable, columnstore, compression, retention and continuous-aggregate
behaviour is handled explicitly by the helper functions in this package, so the
dialects intentionally do not layer any DDL-compiler magic on top of
PostgreSQL. They exist purely so that ``timescaledb``-scheme URLs resolve to the
matching PostgreSQL driver.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2


# These dialects do not change SQL compilation relative to their PostgreSQL
# parents, so SQLAlchemy's statement caching is safe to enable. Without this,
# SQLAlchemy emits a performance warning and disables query caching entirely.
class TimescaledbPsycopg2Dialect(PGDialect_psycopg2):
    """TimescaleDB dialect backed by the ``psycopg2`` driver."""

    name = "timescaledb"
    supports_statement_cache = True


class TimescaledbPsycopgDialect(PGDialect_psycopg):
    """TimescaleDB dialect backed by the ``psycopg`` (psycopg 3) driver."""

    name = "timescaledb"
    supports_statement_cache = True


class TimescaledbAsyncpgDialect(PGDialect_asyncpg):
    """TimescaleDB dialect backed by the ``asyncpg`` driver."""

    name = "timescaledb"
    supports_statement_cache = True


__all__ = [
    "TimescaledbPsycopg2Dialect",
    "TimescaledbPsycopgDialect",
    "TimescaledbAsyncpgDialect",
]
