# 05 · Hypercore Columnstore

The **modern** (TimescaleDB 2.18+) compression path: the Hypercore columnstore,
driven entirely through the `timescaledb` package.

## What it shows

- Opting in via class vars (`__enable_columnstore__`, `__columnstore_orderby__`,
  `__columnstore_segmentby__`, `__columnstore_after__`).
- `enable_columnstore(...)` + `add_columnstore_policy(...)`.
- `convert_to_columnstore(...)` to move chunks into the columnstore on demand.
- `list_columnstore_policies(...)` to confirm the policy is registered.

> Contrast with sample 04, which uses the older `enable_table_compression` API.

## Key files

- `models.py` — `DeviceMetric(TimescaleModel)` with columnstore class vars.
- `pipeline.py` — `convert_all_to_columnstore`, `columnstore_chunk_count`,
  `policies`.

## Run the tests

```bash
python -m pytest samples/hypercore_columnstore -v
```

## Run the demo

```bash
docker compose -f samples/compose.yaml up -d
export DATABASE_URL="postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb"
python -m samples.hypercore_columnstore.main
```
