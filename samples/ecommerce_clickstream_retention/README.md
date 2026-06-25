# 06 · E-commerce Clickstream + Retention

High-volume clickstream events with an automatic **retention policy** and a
funnel rollup grouped by event type.

## What it shows

- `add_retention_policy(...)` so the raw event table never grows unbounded
  (old chunks are dropped automatically).
- Grouping by `time_bucket(...)` **and** `event_type` to build funnel charts.
- A weighted event generator (lots of views, few purchases) and verifying the
  funnel narrows toward purchase.

## Key files

- `models.py` — `ClickEvent(TimescaleModel)`.
- `pipeline.py` — `events_per_bucket`, `funnel_totals`, `retention_policy_count`.

## Run the tests

```bash
python -m pytest samples/ecommerce_clickstream_retention -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.ecommerce_clickstream_retention.main
```
