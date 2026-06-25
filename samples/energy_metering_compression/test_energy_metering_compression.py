"""Tests for the compression sample."""

from datetime import datetime, timezone

import sqlalchemy
from sqlmodel import Session

from samples.energy_metering_compression.pipeline import (
    compress_all_chunks,
    compressed_chunk_count,
    compression_stats,
    generate_readings,
    init_db,
    insert_readings,
)

END = datetime(2026, 1, 11, tzinfo=timezone.utc)


def test_compression_reduces_storage(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_readings(session, generate_readings(meters=5, days=10, end=END))

        compressed = compress_all_chunks(session)
        assert compressed > 0
        assert compressed_chunk_count(session) == compressed

        stats = compression_stats(session)
        assert stats["compressed_chunks"] == compressed
        assert stats["before_bytes"] > 0
        # Highly repetitive meter data compresses well -- expect real savings.
        assert stats["after_bytes"] < stats["before_bytes"]
        assert stats["ratio"] > 1.0


def test_policy_is_registered(engine):
    init_db(engine)
    with Session(engine) as session:
        jobs = session.execute(
            sqlalchemy.text(
                "SELECT count(*) FROM timescaledb_information.jobs "
                "WHERE hypertable_name = 'energy_meter_readings' "
                "AND proc_name LIKE '%compression%'"
            )
        ).scalar_one()
    assert jobs >= 1
