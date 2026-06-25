"""Model for smart-meter energy readings with compression opted in.

The ``__enable_compression__`` / ``__compress_*`` class vars tell the package how
to configure native TimescaleDB compression for this hypertable. ``segmentby``
groups rows by meter so per-meter scans stay fast even when compressed; the
descending ``orderby`` keeps the newest reading first inside each compressed
batch.
"""

from sqlmodel import Field

from timescaledb import TimescaleModel


class MeterReading(TimescaleModel, table=True):
    __tablename__ = "energy_meter_readings"

    meter_id: int = Field(index=True)
    kwh: float
    voltage: float

    __chunk_time_interval__ = "INTERVAL 1 day"
    __enable_compression__ = True
    __compress_orderby__ = "time DESC"
    __compress_segmentby__ = "meter_id"
    __drop_after__ = "INTERVAL 365 days"
