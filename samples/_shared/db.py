"""Database helpers shared by all sample projects.

These helpers are intentionally tiny -- they wrap the bits of engine/session
setup that every sample needs so the sample code can stay focused on the
*TimescaleDB* concepts being demonstrated.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

import timescaledb

# Matches the credentials in ``samples/compose.yaml``. Override with the
# ``DATABASE_URL`` environment variable to point at any TimescaleDB instance.
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
)


def get_database_url() -> str:
    """Return the database URL from ``$DATABASE_URL`` or the compose default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str | None = None, echo: bool = False) -> Engine:
    """Create a TimescaleDB-aware SQLAlchemy engine (timezone pinned to UTC)."""
    return timescaledb.create_engine(url or get_database_url(), timezone="UTC", echo=echo)


def create_tables(engine: Engine, *models: type) -> None:
    """Create only the given models' tables (not the whole global metadata).

    Samples share one ``SQLModel.metadata`` registry, so creating "all" tables
    would pull in every other sample. Passing an explicit ``tables=`` list keeps
    each sample's ``init`` honest about exactly what it owns.
    """
    SQLModel.metadata.create_all(engine, tables=[m.__table__ for m in models])


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a committed-on-success session and always close it."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database(engine: Engine) -> None:
    """Return the ``public`` schema to a clean slate without touching the extension.

    Drops every continuous aggregate and every table (hypertables included) so a
    sample's ``main.py`` / test starts from nothing. This is deliberately written
    to leave the ``timescaledb`` extension itself intact.
    """
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        )
        conn.execute(
            sqlalchemy.text(
                """
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN
                        SELECT view_schema, view_name
                        FROM timescaledb_information.continuous_aggregates
                    LOOP
                        EXECUTE format(
                            'DROP MATERIALIZED VIEW IF EXISTS %I.%I CASCADE',
                            r.view_schema, r.view_name
                        );
                    END LOOP;

                    FOR r IN
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                    LOOP
                        EXECUTE format(
                            'DROP TABLE IF EXISTS public.%I CASCADE', r.tablename
                        );
                    END LOOP;
                END $$;
                """
            )
        )
