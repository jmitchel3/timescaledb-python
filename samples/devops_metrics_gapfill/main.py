"""Runnable demo: reconstruct an even CPU series from sparse, gappy data.

    docker compose -f samples/compose.yaml up -d
    python -m samples.devops_metrics_gapfill.main
"""

from __future__ import annotations

from sqlmodel import Session

from samples._shared.db import get_engine, reset_database
from samples.devops_metrics_gapfill.pipeline import (
    cpu_series,
    generate_sparse_metrics,
    init_db,
    insert_metrics,
    utc,
)


def _print_series(title: str, rows: list[dict]) -> None:
    print(f"\n{title}")
    for row in rows:
        value = "   (gap)" if row["avg"] is None else f"{row['avg']:7.2f}"
        print(f"  {row['bucket']:%H:%M}  {value}")


def main() -> None:
    engine = get_engine()
    reset_database(engine)
    init_db(engine)

    start, finish = utc(2026, 1, 1, 0, 0), utc(2026, 1, 1, 2, 0)
    with Session(engine) as session:
        metrics = generate_sparse_metrics("web-1", start=start)
        print(f"Inserted {insert_metrics(session, metrics)} sparse metrics "
              f"(with a deliberate monitoring outage)")

        _print_series("Raw buckets (gaps show as None):",
                      cpu_series(session, "web-1", start, finish))
        _print_series("LOCF (last value carried forward):",
                      cpu_series(session, "web-1", start, finish, use_locf=True))
        _print_series("Interpolated (linear across the gap):",
                      cpu_series(session, "web-1", start, finish, use_interpolate=True))


if __name__ == "__main__":
    main()
