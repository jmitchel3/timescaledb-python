from sqlmodel import Session, text

from timescaledb import create_hypertable
from timescaledb.compression import add_compression_policy, enable_table_compression

from .conftest import ManualHypertable


def test_manual_hypertable(session: Session):
    tablename = ManualHypertable.__tablename__
    hypertable_options = {
        "time_column": "time",
        "chunk_time_interval": "7 days",
    }
    create_hypertable(
        session,
        table_name=tablename,
        hypertable_options=hypertable_options,
        commit=True,
    )


def test_enable_table_compression(session: Session):
    """Test enabling compression using table_name parameter"""
    table_name = ManualHypertable.__tablename__

    # Create hypertable if not already created
    hypertable_options = {
        "time_column": "time",
        "chunk_time_interval": "7 days",
        "if_not_exists": True,
    }
    create_hypertable(
        session,
        table_name=table_name,
        hypertable_options=hypertable_options,
        commit=True,
    )

    # Enable compression with explicit parameters
    enable_table_compression(
        session,
        table_name=table_name,
        compress_orderby="time",
        compress_segmentby="name",
        commit=True,
    )

    # Verify compression is enabled
    query = text(f"""
        SELECT compression_enabled
        FROM timescaledb_information.hypertables
        WHERE hypertable_name = '{table_name}'
    """)
    result = session.execute(query).fetchone()

    assert result is not None
    assert result[0] is True


def test_add_compression_policy(session: Session):
    """Test adding a compression policy"""
    table_name = ManualHypertable.__tablename__

    # Create hypertable if not already created
    hypertable_options = {
        "time_column": "time",
        "chunk_time_interval": "1 day",
        "if_not_exists": True,
    }
    create_hypertable(
        session,
        table_name=table_name,
        hypertable_options=hypertable_options,
        commit=True,
    )

    # First enable compression
    enable_table_compression(
        session, table_name=table_name, compress_orderby="time", commit=True
    )

    # Add compression policy
    add_compression_policy(
        session, table_name=table_name, compress_after="7 days", commit=True
    )

    # Verify compression policy exists
    query = text(f"""
        SELECT count(*)
        FROM timescaledb_information.jobs
        WHERE hypertable_name = '{table_name}'
        AND proc_name = 'policy_compression'
    """)
    result = session.execute(query).fetchone()

    assert result is not None
    assert result[0] == 1


def test_compression_with_created_before(session: Session):
    """Test compression policy with compress_created_before parameter"""
    table_name = ManualHypertable.__tablename__

    # Create hypertable if not already created
    hypertable_options = {
        "time_column": "time",
        "chunk_time_interval": "1 day",
        "if_not_exists": True,
    }
    create_hypertable(
        session,
        table_name=table_name,
        hypertable_options=hypertable_options,
        commit=True,
    )

    # Enable compression
    enable_table_compression(
        session, table_name=table_name, compress_orderby="time", commit=True
    )

    # Add compression policy with created_before
    # Explicitly create a timedelta object
    # created_before = timedelta(days=3)

    add_compression_policy(
        session,
        table_name=table_name,
        compress_created_before="30 Days",  # Pass the timedelta object
        commit=True,
    )

    # Verify compression policy exists
    query = text(f"""
        SELECT count(*)
        FROM timescaledb_information.jobs
        WHERE hypertable_name = '{table_name}'
        AND proc_name = 'policy_compression'
    """)
    result = session.execute(query).fetchone()

    assert result is not None
    assert result[0] == 1
