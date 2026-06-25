"""Runnable demo: clickstream funnel rollups + a retention policy.

    docker compose -f samples/compose.yaml up -d
    python -m samples.ecommerce_clickstream_retention.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.ecommerce_clickstream_retention.pipeline import (
    funnel_totals,
    generate_events,
    init_db,
    insert_events,
    retention_policy_count,
)


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine, drop_after="30 days")

    with Session(engine) as session:
        written = insert_events(session, generate_events(count=2000, hours=12))
        print(f"Inserted {written} click events")
        print(f"Retention policies on the table: {retention_policy_count(session)}")

        print("\nFunnel totals:")
        for event_type in ("view", "add_to_cart", "checkout", "purchase"):
            print(f"  {event_type:>12}: {funnel_totals(session).get(event_type, 0)}")


if __name__ == "__main__":
    main()
