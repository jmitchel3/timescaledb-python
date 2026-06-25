"""Runnable demo: compress smart-meter history and report the savings.

    docker compose -f samples/compose.yaml up -d
    python -m samples.energy_metering_compression.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.energy_metering_compression.pipeline import (
    compress_all_chunks,
    compression_stats,
    generate_readings,
    init_db,
    insert_readings,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        written = insert_readings(session, generate_readings(meters=5, days=10))
        print(f"Inserted {written} meter readings")

        compressed = compress_all_chunks(session)
        print(f"Compressed {compressed} chunks")

        stats = compression_stats(session)
        print(
            f"\nBefore: {stats['before_bytes']:,} bytes"
            f"\nAfter:  {stats['after_bytes']:,} bytes"
            f"\nRatio:  {stats['ratio']}x smaller "
            f"across {stats['compressed_chunks']} chunks"
        )


if __name__ == "__main__":
    main()
