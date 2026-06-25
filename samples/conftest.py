"""Pytest fixtures shared by every sample project's test suite.

A single TimescaleDB container (Docker, via ``testcontainers``) is started once
per test session and reused by all samples. Each test gets a freshly reset
``public`` schema, so samples are fully isolated from one another.

Requires Docker to be running. Install deps with::

    pip install -r samples/requirements.txt
"""

from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session
from testcontainers.postgres import PostgresContainer

from samples._shared.db import get_engine, reset_database


@pytest.fixture(scope="session")
def timescale_container() -> Generator[PostgresContainer, None, None]:
    """Start one throwaway TimescaleDB container for the whole test session."""
    container = PostgresContainer(
        image="timescale/timescaledb:latest-pg17",
        username="test_user",
        password="test_password",
        dbname="test_db",
        driver="psycopg",
    )
    with container as running:
        yield running


@pytest.fixture(scope="session")
def timescale_url(timescale_container: PostgresContainer) -> str:
    """Return the SQLAlchemy URL for the running test container."""
    return timescale_container.get_connection_url()


@pytest.fixture()
def engine(timescale_url: str) -> Generator[Engine, None, None]:
    """A TimescaleDB engine pointed at a freshly reset schema for each test."""
    eng = get_engine(timescale_url)
    reset_database(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine: Engine) -> Generator[Session, None, None]:
    """A SQLModel session bound to the per-test engine."""
    with Session(engine) as sess:
        yield sess
