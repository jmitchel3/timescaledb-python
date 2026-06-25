"""Runnable demo: move device-metric chunks into the Hypercore columnstore.

    docker compose -f samples/compose.yaml up -d
    python -m samples.hypercore_columnstore.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.hypercore_columnstore.pipeline import (
    columnstore_chunk_count,
    convert_all_to_columnstore,
    generate_metrics,
    init_db,
    insert_metrics,
    policies,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        written = insert_metrics(session, generate_metrics(devices=4, days=10))
        print(f"Inserted {written} device metrics")
        print(f"Columnstore policies: {policies(session)}")

        converted = convert_all_to_columnstore(session)
        print(f"Converted {converted} chunks to the columnstore")
        print(f"Columnstore chunks now: {columnstore_chunk_count(session)}")


if __name__ == "__main__":
    main()
