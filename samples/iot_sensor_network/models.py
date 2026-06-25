"""Data model for the IoT sensor network sample.

``SensorReading`` inherits from :class:`timescaledb.TimescaleModel`, which gives
it an autoincrementing ``id`` plus a timezone-aware ``time`` column and the
class-level configuration the package uses to turn the table into a hypertable.
"""

from sqlmodel import Field

from timescaledb import TimescaleModel


class SensorReading(TimescaleModel, table=True):
    __tablename__ = "iot_sensor_readings"

    sensor_id: int = Field(index=True)
    temperature_c: float
    humidity_pct: float

    # One chunk per day of readings -- a sensible default for sensor data that
    # arrives every few seconds/minutes.
    __chunk_time_interval__ = "INTERVAL 1 day"
    __drop_after__ = "INTERVAL 90 days"
