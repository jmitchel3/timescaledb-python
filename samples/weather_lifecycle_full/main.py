"""Runnable demo: the full TimescaleDB lifecycle for a weather table.

    docker compose -f samples/compose.yaml up -d
    python -m samples.weather_lifecycle_full.main
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.weather_lifecycle_full.pipeline import (
    convert_cold_chunks,
    generate_readings,
    hourly_rollup,
    init_db,
    insert_readings,
    lifecycle_summary,
    refresh_hourly,
    temp_gapfilled,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    readings = generate_readings(stations=3, days=14)
    start = readings[0].time  # capture before commit expires the ORM objects
    with Session(engine) as session:
        print(f"Inserted {insert_readings(session, readings)} station readings")

    refresh_hourly(engine)

    with Session(engine) as session:
        converted = convert_cold_chunks(session)
        print(f"Moved {converted} chunks into the columnstore")

        summary = lifecycle_summary(session)
        print("\nLifecycle summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

        rollup = hourly_rollup(session, station_id=1)
        print(f"\nStation 1 hourly aggregate buckets: {len(rollup)}")

        finish = start + timedelta(days=1)
        filled = temp_gapfilled(session, 1, start, finish)
        print(f"Station 1 interpolated 1-day series points: {len(filled)}")


if __name__ == "__main__":
    main()
