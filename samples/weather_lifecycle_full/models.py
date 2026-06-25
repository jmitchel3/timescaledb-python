"""A production-style hypertable: compression + columnstore + retention config."""

from sqlmodel import Field

from timescaledb import TimescaleModel


class StationReading(TimescaleModel, table=True):
    __tablename__ = "station_readings"

    station_id: int = Field(index=True)
    temp_c: float
    wind_kph: float

    # Chunk daily; move chunks to the columnstore after a week; drop after a year.
    __chunk_time_interval__ = "INTERVAL 1 day"
    __enable_columnstore__ = True
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "station_id"
    __columnstore_after__ = "7 days"
    __columnstore_if_not_exists__ = True
    __drop_after__ = "INTERVAL 365 days"
