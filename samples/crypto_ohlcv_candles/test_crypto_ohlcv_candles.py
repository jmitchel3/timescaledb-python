"""Tests for the OHLCV candles sample."""

from datetime import datetime, timezone

from sqlmodel import Session

from samples.crypto_ohlcv_candles.pipeline import (
    generate_trades,
    init_db,
    insert_trades,
    ohlcv,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_candles_are_internally_consistent(engine):
    init_db(engine)
    with Session(engine) as session:
        # 600 ticks @ 6s = 1 hour of data -> 60 one-minute candles.
        insert_trades(session, generate_trades("BTCUSD", ticks=600, start=START))
        candles = ohlcv(session, "BTCUSD", interval="1 minute")

    assert len(candles) == 60
    for c in candles:
        assert c["low"] <= c["open"] <= c["high"]
        assert c["low"] <= c["close"] <= c["high"]
        assert c["high"] >= c["low"]
        assert c["volume"] > 0


def test_candles_are_isolated_per_symbol(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_trades(session, generate_trades("BTCUSD", ticks=60, start=START))
        insert_trades(
            session,
            generate_trades("ETHUSD", start_price=2_000.0, ticks=60, start=START, seed=99),
        )
        btc = ohlcv(session, "BTCUSD")
        eth = ohlcv(session, "ETHUSD")

    assert btc and eth
    # Different price regimes -> the open of the first candle differs.
    assert btc[0]["open"] > 10_000
    assert eth[0]["open"] < 5_000


def test_wider_buckets_make_fewer_candles(engine):
    init_db(engine)
    with Session(engine) as session:
        insert_trades(session, generate_trades("BTCUSD", ticks=600, start=START))
        one_min = ohlcv(session, "BTCUSD", interval="1 minute")
        five_min = ohlcv(session, "BTCUSD", interval="5 minutes")

    assert len(five_min) < len(one_min)
    assert len(five_min) == 12
