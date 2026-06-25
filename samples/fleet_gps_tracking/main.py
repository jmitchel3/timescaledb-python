"""Runnable demo: manual hypertable + GPS downsampling.

    docker compose -f samples/compose.yaml up -d
    python -m samples.fleet_gps_tracking.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.fleet_gps_tracking.pipeline import (
    chunk_count,
    downsample_speed,
    generate_pings,
    init_db,
    insert_pings,
    is_hypertable,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        written = insert_pings(session, generate_pings(vehicles=3, minutes=60))
        print(f"Inserted {written} GPS pings")
        print(f"fleet_gps_pings is a hypertable: {is_hypertable(session)}")
        print(f"Chunks: {chunk_count(session)}")

        print("\nPer-minute speed for vehicle 1 (first 8 buckets):")
        for row in downsample_speed(session, vehicle_id=1)[:8]:
            print(
                f"  {row['bucket']:%H:%M}  "
                f"avg {row['avg_speed']:.1f} kph  peak {row['max_speed']:.1f} kph"
            )


if __name__ == "__main__":
    main()
