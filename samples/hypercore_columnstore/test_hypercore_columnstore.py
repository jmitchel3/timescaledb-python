"""Tests for the Hypercore columnstore sample."""

from datetime import datetime, timezone

from sqlmodel import Session

from samples.hypercore_columnstore.pipeline import (
    columnstore_chunk_count,
    convert_all_to_columnstore,
    generate_metrics,
    init_db,
    insert_metrics,
    policies,
)

END = datetime(2026, 2, 11, tzinfo=timezone.utc)


def test_policy_registered_on_init(engine):
    init_db(engine)
    with Session(engine) as session:
        assert "hypercore_device_metrics" in policies(session)


def test_convert_moves_chunks_into_columnstore(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_metrics(session, generate_metrics(devices=4, days=10, end=END))
        assert columnstore_chunk_count(session) == 0

        converted = convert_all_to_columnstore(session)
        assert converted > 0
        assert columnstore_chunk_count(session) == converted
