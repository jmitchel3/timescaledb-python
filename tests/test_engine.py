"""Unit tests for timescaledb.engine.create_engine.

Creating a SQLAlchemy engine does NOT open a database connection, so these
tests run without Docker / a live database. Argument forwarding is verified by
monkeypatching the underlying ``sqlalchemy.create_engine`` so no real engine is
even constructed for those cases.
"""

import pytest
from sqlalchemy.engine import Engine

from timescaledb import engine as engine_module
from timescaledb.engine import create_engine

# A syntactically valid URL that is never actually connected to.
DUMMY_URL = "postgresql+psycopg://user:pass@localhost:5432/does_not_connect"


def test_create_engine_returns_engine_instance():
    eng = create_engine(DUMMY_URL)
    try:
        assert isinstance(eng, Engine)
        assert eng.url.database == "does_not_connect"
    finally:
        eng.dispose()


def test_create_engine_sets_read_committed_isolation():
    eng = create_engine(DUMMY_URL)
    try:
        assert (
            eng.get_execution_options().get("isolation_level")
            == "READ COMMITTED"
        )
    finally:
        eng.dispose()


def test_create_engine_forwards_kwargs():
    eng = create_engine(DUMMY_URL, echo=True)
    try:
        assert eng.echo is True
    finally:
        eng.dispose()


@pytest.fixture(name="captured_create_engine")
def captured_create_engine_fixture(monkeypatch):
    """Replace sqlalchemy.create_engine with a capturing stub."""
    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return "SENTINEL_ENGINE"

    monkeypatch.setattr(
        engine_module.sqlalchemy, "create_engine", _fake_create_engine
    )
    return captured


def test_create_engine_default_timezone_is_utc(captured_create_engine):
    result = create_engine(DUMMY_URL)

    assert result == "SENTINEL_ENGINE"
    assert captured_create_engine["url"] == DUMMY_URL
    connect_args = captured_create_engine["kwargs"]["connect_args"]
    assert connect_args["options"] == "-c timezone=UTC"


def test_create_engine_custom_timezone(captured_create_engine):
    create_engine(DUMMY_URL, timezone="America/New_York")

    connect_args = captured_create_engine["kwargs"]["connect_args"]
    assert connect_args["options"] == "-c timezone=America/New_York"


def test_create_engine_sets_isolation_execution_option(captured_create_engine):
    create_engine(DUMMY_URL)

    execution_options = captured_create_engine["kwargs"]["execution_options"]
    assert execution_options == {"isolation_level": "READ COMMITTED"}


def test_create_engine_forwards_extra_kwargs(captured_create_engine):
    create_engine(DUMMY_URL, echo=True, pool_pre_ping=True)

    kwargs = captured_create_engine["kwargs"]
    assert kwargs["echo"] is True
    assert kwargs["pool_pre_ping"] is True


def test_create_engine_preserves_user_connect_args(captured_create_engine):
    """A caller-supplied connect_args dict is preserved and augmented."""
    create_engine(
        DUMMY_URL,
        connect_args={"application_name": "my_app"},
    )

    connect_args = captured_create_engine["kwargs"]["connect_args"]
    assert connect_args["application_name"] == "my_app"
    assert connect_args["options"] == "-c timezone=UTC"
