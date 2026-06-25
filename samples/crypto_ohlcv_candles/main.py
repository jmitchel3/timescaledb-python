"""Runnable demo: build 1-minute OHLCV candles from raw trade ticks.

    docker compose -f samples/compose.yaml up -d
    python -m samples.crypto_ohlcv_candles.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.crypto_ohlcv_candles.pipeline import (
    generate_trades,
    init_db,
    insert_trades,
    ohlcv,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        trades = generate_trades("BTCUSD", ticks=600)
        print(f"Inserted {insert_trades(session, trades)} trade ticks")

        candles = ohlcv(session, "BTCUSD", interval="1 minute")
        print(f"\n{len(candles)} one-minute candles (showing first 8):")
        print(f"  {'time':>16}  {'open':>10} {'high':>10} {'low':>10} {'close':>10} {'vol':>8}")
        for c in candles[:8]:
            print(
                f"  {c['bucket']:%Y-%m-%d %H:%M}  "
                f"{c['open']:>10.2f} {c['high']:>10.2f} {c['low']:>10.2f} "
                f"{c['close']:>10.2f} {c['volume']:>8.2f}"
            )


if __name__ == "__main__":
    main()
