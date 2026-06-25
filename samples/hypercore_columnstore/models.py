"""Model opting in to the Hypercore columnstore via class vars.

This is the modern (TimescaleDB 2.18+) replacement for the older compression
API shown in sample 04. The ``__columnstore_*`` class vars drive the package's
``enable_columnstore`` / ``add_columnstore_policy`` helpers.
"""

from sqlmodel import Field

from timescaledb import TimescaleModel


class DeviceMetric(TimescaleModel, table=True):
    __tablename__ = "hypercore_device_metrics"

    device_id: int = Field(index=True)
    value: float

    __chunk_time_interval__ = "INTERVAL 1 day"

    # Hypercore columnstore configuration.
    __enable_columnstore__ = True
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "device_id"
    __columnstore_after__ = "7 days"
    __columnstore_if_not_exists__ = True
