from datetime import datetime
from typing import ClassVar, Optional

import sqlmodel
from sqlmodel import Field, SQLModel

from timescaledb.defaults import CHUNK_TIME_INTERVAL, DROP_AFTER, TIME_COLUMN
from timescaledb.utils import get_utc_now


class TimescaleModel(SQLModel):
    """
    Abstract base class for Timescale hypertables.
    Subclasses must define the required class variables for TimescaleDB configuration.
    """

    id: Optional[int] = Field(
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

    # Required TimescaleDB configuration class variables
    __time_column__: ClassVar[str] = TIME_COLUMN
    __chunk_time_interval__: ClassVar[str] = CHUNK_TIME_INTERVAL
    __drop_after__: ClassVar[str] = DROP_AFTER
    __enable_compression__: ClassVar[bool] = False
    __compress_orderby__: ClassVar[Optional[str]] = None
    __compress_segmentby__: ClassVar[Optional[str]] = None
    __enable_columnstore__: ClassVar[bool] = False
    __columnstore_orderby__: ClassVar[Optional[str]] = None
    __columnstore_segmentby__: ClassVar[Optional[str]] = None
    __columnstore_after__: ClassVar[Optional[str]] = None
    __columnstore_created_before__: ClassVar[Optional[str]] = None
    __columnstore_if_not_exists__: ClassVar[bool] = True
    __columnstore_schedule_interval__: ClassVar[Optional[str]] = None
    __columnstore_timezone__: ClassVar[Optional[str]] = None
