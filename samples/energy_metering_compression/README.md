# 04 · Smart-Meter Compression

Ingest smart-meter history, **compress** the older chunks, and measure the
storage savings — TimescaleDB's native compression API.

## What it shows

- Opting a model into compression via class vars (`__enable_compression__`,
  `__compress_orderby__`, `__compress_segmentby__`).
- `enable_table_compression(...)` + `add_compression_policy(...)`.
- Compressing every chunk on demand and reading `chunk_compression_stats(...)`
  to report a real before/after ratio.

> Sample 05 shows the **modern** Hypercore columnstore equivalent.

## Key files

- `models.py` — `MeterReading(TimescaleModel)`.
- `pipeline.py` — `compress_all_chunks`, `compression_stats`,
  `compressed_chunk_count`.

## Run the tests

```bash
python -m pytest samples/energy_metering_compression -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.energy_metering_compression.main
```
