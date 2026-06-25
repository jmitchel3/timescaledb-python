"""Turn a stream of trade ticks into OHLCV candlesticks.

The candle aggregation leans on two TimescaleDB hyperfunctions exposed straight
through SQLAlchemy's ``func``:

* ``first(price, time)`` -> the *opening* price of the bucket
* ``last(price, time)``  -> the *closing* price of the bucket

combined with plain ``min`` / ``max`` / ``sum`` and the package's ``time_bucket``
helper from :mod:`timescaledb.hyperfunctions`.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

import timescaledb
from samples._shared.db import create_tables
from samples.crypto_ohlcv_candles.models import Trade
from timescaledb.hyperfunctions import time_bucket


def init_db(engine: Engine) -> None:
    create_tables(engine, Trade)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=Trade, commit=True)


def generate_trades(
    symbol: str = "BTCUSD",
    start_price: float = 30_000.0,
    ticks: int = 600,
    start: datetime | None = None,
    every_seconds: int = 6,
    seed: int = 11,
) -> list[Trade]:
    """Generate a deterministic random-walk tick stream for one symbol."""
    rng = random.Random(seed)
    start = start or (datetime.now(timezone.utc) - timedelta(seconds=ticks * every_seconds))
    price = start_price
    out: list[Trade] = []
    for i in range(ticks):
        price = max(1.0, price * (1 + rng.uniform(-0.002, 0.002)))
        out.append(
            Trade(
                time=start + timedelta(seconds=i * every_seconds),
                symbol=symbol,
                price=round(price, 2),
                volume=round(rng.uniform(0.01, 2.5), 4),
            )
        )
    return out


def insert_trades(session: Session, trades: list[Trade]) -> int:
    session.add_all(trades)
    session.commit()
    return len(trades)


def ohlcv(session: Session, symbol: str, interval: str = "1 minute") -> list[dict]:
    """Return OHLCV candles for ``symbol`` at the requested bucket width."""
    bucket = time_bucket(interval, Trade.time)
    query = (
        select(
            bucket.label("bucket"),
            func.first(Trade.price, Trade.time).label("open"),
            func.max(Trade.price).label("high"),
            func.min(Trade.price).label("low"),
            func.last(Trade.price, Trade.time).label("close"),
            func.sum(Trade.volume).label("volume"),
        )
        .where(Trade.symbol == symbol)
        .group_by(bucket)
        .order_by(bucket)
    )
    return list(session.exec(query).mappings().all())
