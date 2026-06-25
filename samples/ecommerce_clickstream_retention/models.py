"""Model for raw e-commerce clickstream events."""

from sqlmodel import Field

from timescaledb import TimescaleModel


class ClickEvent(TimescaleModel, table=True):
    __tablename__ = "ecommerce_click_events"

    event_type: str = Field(index=True)  # view, add_to_cart, purchase, ...
    user_id: int = Field(index=True)
    path: str

    __chunk_time_interval__ = "INTERVAL 1 day"
    # Raw clickstream is high-volume and only needed short-term; drop after 30 days.
    __drop_after__ = "INTERVAL 30 days"
