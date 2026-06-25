"""Tests for the IoT sensor network sample (runs against Docker TimescaleDB)."""

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from samples.iot_sensor_network.models import SensorReading
from samples.iot_sensor_network.pipeline import (
    generate_readings,
    hourly_average_temperature,
    init_db,
    insert_readings,
    latest_per_sensor,
    list_sample_hypertables,
)


def test_table_becomes_a_hypertable(engine):
    init_db(engine)
    with Session(engine) as session:
        assert "iot_sensor_readings" in list_sample_hypertables(session)


def test_ingest_and_bucket(engine):
    init_db(engine)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    readings = generate_readings(sensors=3, hours=24, every_minutes=10, end=end)

    with Session(engine) as session:
        written = insert_readings(session, readings)
        assert written == len(readings)

        total = session.exec(select(func.count()).select_from(SensorReading)).one()
        assert total == written

        buckets = hourly_average_temperature(session, sensor_id=1)
        # 24 hours of data, bucketed hourly -> ~25 buckets (inclusive endpoints).
        assert 24 <= len(buckets) <= 26
        for row in buckets:
            # Sensor 1 baseline 19C +/- a 5C daily swing and small noise.
            assert 12.0 < row["avg"] < 26.0


def test_latest_per_sensor_has_one_row_each(engine):
    init_db(engine)
    end = datetime(2026, 3, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        insert_readings(session, generate_readings(sensors=5, hours=6, end=end))
        latest = latest_per_sensor(session)
        assert set(latest.keys()) == {1, 2, 3, 4, 5}
        assert all(isinstance(v, float) for v in latest.values())
