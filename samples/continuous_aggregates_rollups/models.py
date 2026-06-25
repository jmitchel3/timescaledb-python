"""Raw weather conditions feeding the continuous aggregates."""

from sqlmodel import Field

from timescaledb import TimescaleModel


class WeatherCondition(TimescaleModel, table=True):
    __tablename__ = "weather_conditions"

    location: str = Field(index=True)
    temperature: float

    __chunk_time_interval__ = "INTERVAL 1 day"
    __drop_after__ = "INTERVAL 365 days"
