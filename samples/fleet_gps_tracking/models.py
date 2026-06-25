"""A *plain* SQLModel (not TimescaleModel) for GPS pings.

This sample deliberately uses an ordinary ``SQLModel`` table so it can show the
manual ``timescaledb.create_hypertable(..., hypertable_options=...)`` path -- the
alternative to inheriting from ``TimescaleModel``. The only requirement is a
timestamp column (here ``time``) that is part of the primary key.
"""

from datetime import datetime

import sqlmodel
from sqlmodel import Field, SQLModel

from timescaledb.utils import get_utc_now


class GpsPing(SQLModel, table=True):
    __tablename__ = "fleet_gps_pings"

    id: int = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"autoincrement": True},
    )
    time: datetime = Field(
        default_factory=get_utc_now,
        sa_type=sqlmodel.DateTime(timezone=True),
        primary_key=True,
        nullable=False,
    )
    vehicle_id: int = Field(index=True)
    lat: float
    lon: float
    speed_kph: float


# Options passed straight to create_hypertable -- no class vars involved.
HYPERTABLE_OPTIONS = {
    "time_column": "time",
    "chunk_time_interval": "INTERVAL 1 day",
    "if_not_exists": True,
    "migrate_data": True,
}
