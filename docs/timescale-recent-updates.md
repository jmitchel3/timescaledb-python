# Recent TimescaleDB Updates

Current as of June 25, 2026.

## Findings

- The latest upstream TimescaleDB release found during this pass is 2.28.1, published June 23, 2026. It is a patch release after 2.28.0 with compressed-table and aggregate bug fixes.
- TimescaleDB 2.28.0 highlights faster `first()` and `last()` queries on compressed/columnstore data, incremental manual continuous aggregate refreshes, vectorized execution for `CASE`, and adding generated aggregate columns to continuous aggregates without rebuilding them.
- TimescaleDB 2.28.0 is also the final minor release line with PostgreSQL 15 support. Future 2.29.x releases are expected to support PostgreSQL 16, 17, and 18 only.
- Hypercore is now the current API family for columnstore storage. `ALTER TABLE (hypercore)` replaces old compression `ALTER TABLE` settings as of 2.18.0. `add_columnstore_policy()` supersedes `add_compression_policy()`, although the old compression APIs are still supported.
- TimescaleDB 2.20.0 added `CREATE TABLE ... WITH (tsdb.hypertable)` for creating hypertables directly. With that path, TimescaleDB can create a columnstore policy automatically. This Python package still uses the `create_hypertable()` conversion path.
- Recent documentation distinguishes modern columnstore policies in `timescaledb_information.jobs` with `application_name LIKE 'Columnstore%'`.
- `time_bucket()` supports timestamp, integer, and UUIDv7 time inputs. `time_bucket_gapfill()` requires bounded time filters for good behavior and supports `timezone` on TimescaleDB 2.9 or later.

## Changes Made In This Project

- Added `timescaledb.hypercore` helpers for enabling columnstore, adding/removing columnstore policies, manual chunk conversion to columnstore/rowstore, listing columnstore policies, and syncing opted-in models.
- Updated `time_bucket()` and `time_bucket_gapfill()` so integer bucket widths are sent to TimescaleDB as integers rather than interval strings, and added UUIDv7 coverage for `time_bucket()`.
- Added `timescaledb.continuous_aggregates.refresh_continuous_aggregate()` for manual continuous aggregate refreshes, including `force` and `refresh_newest_first`.
- Added continuous aggregate creation and refresh policy helpers, including the newer `buckets_per_batch`, `max_batches_per_execution`, `refresh_newest_first`, and `include_tiered_data` policy options.
- Added `add_generated_aggregate_column()` for TimescaleDB 2.28's generated aggregate-column workflow on existing continuous aggregates.
- Added `create_table_with_hypertable()` and SQL formatting support for TimescaleDB 2.20+ direct hypertable creation with `CREATE TABLE ... WITH (tsdb.hypertable)`.
- Added `TimescaleModel` columnstore class variables:
  - `__enable_columnstore__`
  - `__columnstore_orderby__`
  - `__columnstore_segmentby__`
  - `__columnstore_after__`
  - `__columnstore_created_before__`
  - `__columnstore_if_not_exists__`
  - `__columnstore_schedule_interval__`
  - `__columnstore_timezone__`
- Kept legacy compression helpers in place. Existing `enable_table_compression()` and `add_compression_policy()` callers remain supported.

## Follow-Up Opportunities

- Update the test matrix when TimescaleDB 2.29 ships, because PostgreSQL 15 support is planned to drop after the 2.28 release line.

## Sources

- TimescaleDB releases: https://github.com/timescale/timescaledb/releases
- Hypercore `ALTER TABLE`: https://www.tigerdata.com/docs/api/latest/hypercore/alter_table
- `add_columnstore_policy()`: https://www.tigerdata.com/docs/api/latest/hypercore/add_columnstore_policy
- `remove_columnstore_policy()`: https://www.tigerdata.com/docs/api/latest/hypercore/remove_columnstore_policy
- `convert_to_columnstore()`: https://www.tigerdata.com/docs/api/latest/hypercore/convert_to_columnstore
- `convert_to_rowstore()`: https://www.tigerdata.com/docs/api/latest/hypercore/convert_to_rowstore
- `CREATE TABLE` hypertables: https://www.tigerdata.com/docs/api/latest/hypertable/create_table
- `CREATE MATERIALIZED VIEW` continuous aggregates: https://www.tigerdata.com/docs/api/latest/continuous-aggregates/create_materialized_view
- `refresh_continuous_aggregate()`: https://www.tigerdata.com/docs/api/latest/continuous-aggregates/refresh_continuous_aggregate
- `add_continuous_aggregate_policy()`: https://www.tigerdata.com/docs/api/latest/continuous-aggregates/add_continuous_aggregate_policy
- `remove_continuous_aggregate_policy()`: https://www.tigerdata.com/docs/api/latest/continuous-aggregates/remove_continuous_aggregate_policy
- `time_bucket()`: https://docs2.tigerdata.com/docs/reference/timescaledb/hyperfunctions/time-series-utilities/time_bucket
- `time_bucket_gapfill()`: https://docs2.tigerdata.com/docs/reference/timescaledb/hyperfunctions/time_bucket_gapfill/time_bucket_gapfill
