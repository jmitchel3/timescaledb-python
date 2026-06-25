"""Model for server resource metrics."""

from sqlmodel import Field

from timescaledb import TimescaleModel


class ServerMetric(TimescaleModel, table=True):
    __tablename__ = "devops_server_metrics"

    host: str = Field(index=True)
    cpu_pct: float
    mem_pct: float

    __chunk_time_interval__ = "INTERVAL 1 hour"
    __drop_after__ = "INTERVAL 30 days"
