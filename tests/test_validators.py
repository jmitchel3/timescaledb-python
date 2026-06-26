from datetime import timedelta

import pytest
from sqlalchemy import String
from sqlmodel import Field, SQLModel

from timescaledb.exceptions import (
    InvalidChunkTimeInterval,
    InvalidTimeColumn,
    InvalidTimeColumnType,
)
from timescaledb.hypertables.validators import (
    validate_chunk_time_interval,
    validate_time_column,
)

from .conftest import Metric, Record


def test_validate_time_column_valid():
    """Test validation of a valid time column"""
    # Function should not raise an exception for valid time column
    validate_time_column(Metric)  # Should pass without raising an exception


def test_validate_time_column_missing():
    """Test validation when time column is missing"""
    with pytest.raises(InvalidTimeColumn, match="does not have a valid time column"):
        validate_time_column(Record)  # Record model doesn't have a time column


def test_validate_time_column_invalid_type():
    """Test validation when time column has invalid type"""

    class InvalidTimeTypeModel(SQLModel, table=True):
        id: int = Field(primary_key=True)
        time: str = Field(
            sa_type=String
        )  # Only need this one custom model for invalid type test

    with pytest.raises(
        InvalidTimeColumnType, match="invalid data type for the time column"
    ):
        validate_time_column(InvalidTimeTypeModel)


def test_validate_chunk_time_interval_datetime_column():
    """Test validation of chunk time interval for datetime columns"""
    # Valid interval string
    validate_chunk_time_interval(Metric, "time", "INTERVAL 1 DAY")

    # Valid timedelta
    validate_chunk_time_interval(Metric, "time", timedelta(days=1))

    # Invalid timedelta (testing lines 71-72)
    class BadTimedelta(timedelta):
        def total_seconds(self):
            return float("inf")  # This will fail int() conversion

    with pytest.raises(InvalidChunkTimeInterval, match="must be an integer"):
        validate_chunk_time_interval(Metric, "time", BadTimedelta())

    # Valid integer (microseconds)
    validate_chunk_time_interval(Metric, "time", 86400000000)  # 1 day in microseconds

    # Invalid string (testing string validation)
    with pytest.raises(InvalidChunkTimeInterval, match="must be an INTERVAL"):
        validate_chunk_time_interval(Metric, "time", "not an interval")

    # Invalid interval string format
    with pytest.raises(InvalidChunkTimeInterval, match="must be an INTERVAL"):
        validate_chunk_time_interval(Metric, "time", "1 DAY")


def test_validate_chunk_time_interval_invalid_column():
    """Test validation when time column doesn't exist"""
    with pytest.raises(InvalidChunkTimeInterval, match="Time column .* not found"):
        validate_chunk_time_interval(Metric, "nonexistent", "INTERVAL 1 DAY")


def test_validate_chunk_time_interval_unsupported_type():
    """Test validation with unsupported column type"""

    class UnsupportedTypeModel(SQLModel, table=True):
        id: int = Field(primary_key=True)
        time: str = Field(sa_type=String)  # String type is not supported for time

    with pytest.raises(InvalidChunkTimeInterval, match="Unsupported time column type"):
        validate_chunk_time_interval(UnsupportedTypeModel, "time", "INTERVAL 1 DAY")
