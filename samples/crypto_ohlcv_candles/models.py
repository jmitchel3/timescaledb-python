"""Model for raw trade ticks."""

from sqlmodel import Field

from timescaledb import TimescaleModel


class Trade(TimescaleModel, table=True):
    __tablename__ = "crypto_trades"

    symbol: str = Field(index=True)
    price: float
    volume: float

    # Ticks are high-frequency; keep chunks small.
    __chunk_time_interval__ = "INTERVAL 1 hour"
    __drop_after__ = "INTERVAL 7 days"
