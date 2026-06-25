# 02 · DevOps Metrics — Gapfill / LOCF / Interpolation

Monitoring agents miss scrapes. This sample ingests deliberately *gappy* CPU
metrics and reconstructs an evenly-spaced series three ways.

## What it shows

- `time_bucket_gapfill_query(...)` to produce one bucket per interval even when
  data is missing.
- **LOCF** (`use_locf=True`) — carry the last value forward across a gap.
- **Interpolation** (`use_interpolate=True`) — linearly bridge a gap.
- Raw gapfill (neither) — empty buckets come back as `avg = None`.

## Key files

- `models.py` — `ServerMetric(TimescaleModel)`.
- `pipeline.py` — `generate_sparse_metrics` (punches a hole in the data),
  `cpu_series`.

## Run the tests

```bash
python -m pytest samples/devops_metrics_gapfill -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.devops_metrics_gapfill.main
```
