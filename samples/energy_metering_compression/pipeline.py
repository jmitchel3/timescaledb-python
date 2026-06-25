"""Ingest meter data, compress old chunks, and measure the storage savings.

Flow demonstrated:

1. ``enable_table_compression`` + ``add_compression_policy`` configure the
   package's native-compression path from the model's class vars.
2. We then compress every existing chunk *now* (instead of waiting for the
   background policy job) so the demo/test can read back real numbers.
3. ``compression_stats`` reports before/after bytes and the compression ratio.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlmodel import Session

import timescaledb
from samples._shared.db import create_tables
from samples.energy_metering_compression.models import MeterReading


def init_db(engine: Engine) -> None:
    create_tables(engine, MeterReading)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=MeterReading, commit=True)
        # Configure compression straight from the model's class vars.
        timescaledb.enable_table_compression(session, model=MeterReading, commit=True)
        timescaledb.add_compression_policy(
            session, model=MeterReading, compress_after="7 days", commit=True
        )


def generate_readings(
    meters: int = 5,
    days: int = 10,
    every_minutes: int = 15,
    end: datetime | None = None,
) -> list[MeterReading]:
    """Generate steadily-climbing kWh readings across several meters and days."""
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    step = timedelta(minutes=every_minutes)

    rows: list[MeterReading] = []
    for meter_id in range(1, meters + 1):
        kwh = 1000.0 * meter_id
        ts = start
        while ts < end:
            kwh += 0.05  # monotonically increasing meter total
            rows.append(
                MeterReading(
                    time=ts,
                    meter_id=meter_id,
                    kwh=round(kwh, 3),
                    voltage=round(230 + (meter_id % 3), 2),
                )
            )
            ts += step
    return rows


def insert_readings(session: Session, readings: list[MeterReading]) -> int:
    session.add_all(readings)
    session.commit()
    return len(readings)


def compress_all_chunks(session: Session, table_name: str = "energy_meter_readings") -> int:
    """Compress every chunk now; returns the number of chunks compressed."""
    rows = session.execute(
        sqlalchemy.text(
            "SELECT compress_chunk(c, if_not_compressed => true) "
            "FROM show_chunks(:t) c"
        ),
        {"t": table_name},
    ).fetchall()
    session.commit()
    return len(rows)


def compression_stats(
    session: Session, table_name: str = "energy_meter_readings"
) -> dict:
    """Return before/after byte counts and the compression ratio."""
    row = session.execute(
        sqlalchemy.text(
            """
            SELECT
                coalesce(sum(before_compression_total_bytes), 0) AS before_bytes,
                coalesce(sum(after_compression_total_bytes), 0)  AS after_bytes,
                count(*) FILTER (WHERE after_compression_total_bytes IS NOT NULL)
                    AS compressed_chunks
            FROM chunk_compression_stats(:t)
            """
        ),
        {"t": table_name},
    ).mappings().one()

    before = int(row["before_bytes"] or 0)
    after = int(row["after_bytes"] or 0)
    ratio = (before / after) if after else 0.0
    return {
        "before_bytes": before,
        "after_bytes": after,
        "compressed_chunks": int(row["compressed_chunks"] or 0),
        "ratio": round(ratio, 2),
    }


def compressed_chunk_count(session: Session, table_name: str = "energy_meter_readings") -> int:
    """How many chunks of ``table_name`` are currently compressed."""
    return session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name = :t AND is_compressed"
        ),
        {"t": table_name},
    ).scalar_one()
