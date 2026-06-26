import pytest
import sqlalchemy
from sqlmodel import Session

from timescaledb import create_hypertable
from timescaledb.hypertables.list import is_hypertable, list_hypertables
from timescaledb.retention import (
    add_retention_policy,
    drop_retention_policy,
    list_retention_policies,
    sync_retention_policies,
)

from .conftest import RetentionModel


def test_get_retention_policy_with_table_name(engine):
    """Test that retention policy is properly created and listed"""
    table_name = RetentionModel.__tablename__

    # First ensure any existing retention policy is removed
    with Session(engine) as session:
        try:
            drop_retention_policy(session, table_name=table_name)
            session.commit()
            print("Dropped existing retention policy")
        except Exception as e:
            print(f"Error dropping existing policy (may not exist): {e}")
            session.rollback()

    # Now create hypertable and add retention policy
    with Session(engine) as session:
        try:
            # First check if table exists
            result = session.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
                ),
                {"table_name": table_name},
            ).scalar()
            print(f"Table exists: {result}")

            # Create hypertable with if_not_exists=True
            create_hypertable(
                session,
                model=RetentionModel,
                hypertable_options={"if_not_exists": True},
            )
            print("Created/verified hypertable")

            # Verify it's a hypertable
            result = session.execute(
                sqlalchemy.text(
                    "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = :table_name"
                ),
                {"table_name": table_name},
            ).fetchone()
            print(f"Hypertable info: {result}")

            # Add retention policy
            add_retention_policy(session, model=RetentionModel, drop_after="1 year")
            print("Added retention policy")

            session.commit()
            print("Committed changes")
        except Exception as e:
            session.rollback()
            print(f"Error in transaction: {e}")
            raise

    # New transaction to verify changes are visible
    with Session(engine) as session:
        try:
            current_policies = list_retention_policies(session)
            print(f"Current policies: {current_policies}")
            assert table_name in current_policies
            assert is_hypertable(session, table_name) is True
        except Exception as e:
            print(f"Error verifying changes: {e}")
            raise


def test_drop_retention_policy_with_table_name(engine):
    """Test getting a retention policy using table_name parameter"""
    with Session(engine) as session:
        table_name = RetentionModel.__tablename__
        drop_retention_policy(session, table_name)
        session.commit()
    with Session(engine) as session:
        current_policies = list_retention_policies(session)
        assert table_name not in current_policies


def test_sync_retention_policies(engine):
    """Test syncing retention policies for multiple models"""
    # First transaction: clear policies
    with Session(engine) as session:
        hypertables = [table.hypertable_name for table in list_hypertables(session)]
        for table_name in hypertables:
            drop_retention_policy(session, table_name=table_name)
        session.commit()

    # Second transaction: sync policies
    with Session(engine) as session:
        sync_retention_policies(session, drop_after="6 months")
        session.commit()

    # Third transaction: verify policies
    with Session(engine) as session:
        policies = list_retention_policies(session)
        assert RetentionModel.__tablename__ in policies


def test_add_retention_policy_validation(engine):
    """Test validation in add_retention_policy"""

    with Session(engine) as session:
        drop_retention_policy(session, RetentionModel.__tablename__)
        session.commit()

    with Session(engine) as session:
        # Test with neither model nor table_name
        with pytest.raises(ValueError):
            add_retention_policy(session, model=None, table_name=None)

        # Test with both model and table_name
        add_retention_policy(
            session,
            model=RetentionModel,
            drop_after="1 year",
        )
        session.commit()

    # New transaction to verify
    with Session(engine) as session:
        policies = list_retention_policies(session)
        assert RetentionModel.__tablename__ in policies


def test_list_retention_policies_empty(engine):
    """Test listing retention policies when none exist"""
    import time

    from sqlalchemy.exc import OperationalError

    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # First transaction: clear policies
            with Session(engine) as session:
                hypertables = [
                    table.hypertable_name for table in list_hypertables(session)
                ]
                for table_name in hypertables:
                    try:
                        drop_retention_policy(session, table_name=table_name)
                    except Exception as e:
                        print(f"Error dropping policy for {table_name}: {e}")
                        session.rollback()
                        continue
                session.commit()
                break  # If we get here, everything worked
        except OperationalError as e:
            if "deadlock detected" in str(e).lower() and attempt < max_retries - 1:
                print(f"Deadlock detected, attempt {attempt + 1} of {max_retries}")
                time.sleep(retry_delay)
                continue
            raise
    else:
        raise Exception("Failed to clear retention policies after max retries")

    # Second transaction: verify empty state
    with Session(engine) as session:
        policies = list_retention_policies(session)
        print(f"Policies after clearing: {policies}")
        assert policies is None or len(policies) == 0
