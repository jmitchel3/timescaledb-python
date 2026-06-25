"""Runnable demo: ingest sensor data and roll it up with time_bucket.

    docker compose -f samples/compose.yaml up -d
    python -m samples.iot_sensor_network.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.iot_sensor_network.pipeline import (
    generate_readings,
    hourly_average_temperature,
    init_db,
    insert_readings,
    latest_per_sensor,
    list_sample_hypertables,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        written = insert_readings(session, generate_readings(sensors=4, hours=24))
        print(f"Inserted {written} sensor readings")
        print(f"Hypertables: {list_sample_hypertables(session)}")

        print("\nLatest temperature per sensor:")
        for sensor_id, temp in latest_per_sensor(session).items():
            print(f"  sensor {sensor_id}: {temp:.2f} C")

        print("\nHourly average temperature for sensor 1:")
        for row in hourly_average_temperature(session, sensor_id=1):
            print(f"  {row['bucket']:%Y-%m-%d %H:%M}  ->  {row['avg']:.2f} C")


if __name__ == "__main__":
    main()
