"""Tests for the gapfill sample."""

from sqlmodel import Session

from samples.devops_metrics_gapfill.pipeline import (
    cpu_series,
    generate_sparse_metrics,
    init_db,
    insert_metrics,
    utc,
)

START = utc(2026, 1, 1, 0, 0)
FINISH = utc(2026, 1, 1, 2, 0)


def _seed(engine):
    init_db(engine)
    with Session(engine) as session:
        metrics = generate_sparse_metrics("web-1", start=START)
        insert_metrics(session, metrics)


def test_raw_buckets_have_holes(engine):
    _seed(engine)
    with Session(engine) as session:
        rows = cpu_series(session, "web-1", START, FINISH)
    # Bucketing at 5 min over 2 hours => 25 buckets, and the seeded outage
    # (buckets 3 & 4) leaves at least two of them empty.
    assert len(rows) == 25
    assert any(r["avg"] is None for r in rows)


def test_locf_fills_every_bucket(engine):
    _seed(engine)
    with Session(engine) as session:
        rows = cpu_series(session, "web-1", START, FINISH, use_locf=True)
    # The leading bucket can still be NULL (nothing precedes it), but the gap
    # in the middle must be filled.
    interior = rows[1:]
    assert all(r["avg"] is not None for r in interior)


def test_interpolate_fills_gap_between_neighbors(engine):
    _seed(engine)
    with Session(engine) as session:
        raw = cpu_series(session, "web-1", START, FINISH)
        interp = cpu_series(session, "web-1", START, FINISH, use_interpolate=True)

    gap_indexes = [i for i, r in enumerate(raw) if r["avg"] is None]
    assert gap_indexes, "expected at least one gap to interpolate"
    # Interpolation must produce numbers where raw had None (for interior gaps).
    for i in gap_indexes:
        if 0 < i < len(interp) - 1:
            assert interp[i]["avg"] is not None
