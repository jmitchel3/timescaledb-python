"""Runnable demo: hierarchical continuous aggregates (hourly -> daily).

    docker compose -f samples/compose.yaml up -d
    python -m samples.continuous_aggregates_rollups.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.continuous_aggregates_rollups.pipeline import (
    daily_rollup,
    generate_conditions,
    hourly_rollup,
    init_db,
    insert_conditions,
    refresh_all,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    with Session(engine) as session:
        written = insert_conditions(session, generate_conditions(days=5))
        print(f"Inserted {written} raw weather conditions")

    refresh_all(engine)

    hourly = hourly_rollup(engine, location="nyc")
    daily = daily_rollup(engine, location="nyc")
    print(f"\nNYC hourly buckets: {len(hourly)}  |  NYC daily buckets: {len(daily)}")

    print("\nNYC daily rollup:")
    for row in daily:
        print(
            f"  {row['bucket']:%Y-%m-%d}  "
            f"avg {row['avg_temp']:.2f}  min {row['min_temp']:.2f}  max {row['max_temp']:.2f}"
        )


if __name__ == "__main__":
    main()
