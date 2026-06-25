"""Table model + request/response schemas for the API."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from timescaledb import TimescaleModel


class Reading(TimescaleModel, table=True):
    __tablename__ = "api_readings"

    sensor_id: int = Field(index=True)
    value: float

    __chunk_time_interval__ = "INTERVAL 1 day"
    __drop_after__ = "INTERVAL 90 days"


class ReadingIn(SQLModel):
    sensor_id: int
    value: float
    time: Optional[datetime] = None


class ReadingOut(SQLModel):
    id: int
    sensor_id: int
    value: float
    time: datetime


class BucketOut(SQLModel):
    bucket: datetime
    avg: Optional[float] = None
