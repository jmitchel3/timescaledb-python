# TimescaleDB for Python

Python client for [TimescaleDB](https://www.tigerdata.com/), the open-source
time-series database built on PostgreSQL. This package is built on
[SQLModel](https://sqlmodel.tiangolo.com/) and
[SQLAlchemy](https://www.sqlalchemy.org/) and is designed to be used with
FastAPI, Flask, and any other SQLAlchemy-based project.

It gives you Python helpers for the things you actually do with TimescaleDB:
creating hypertables, enabling the Hypercore columnstore (and legacy
compression), setting retention policies, building continuous aggregates, and
running `time_bucket` / `time_bucket_gapfill` queries.

> Looking for Django? Check out [django-timescaledb](https://github.com/jamessewell/django-timescaledb).

- **Supports:** Python 3.11, 3.12, 3.13, and 3.14
- **Targets:** TimescaleDB 2.x (Hypercore columnstore needs 2.18+; direct-create
  hypertables need 2.20+; generated aggregate columns need 2.28+)
- **License:** MIT

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Creating a hypertable](#creating-a-hypertable)
  - [Automatically via `TimescaleModel`](#automatically-via-timescalemodel)
  - [Manually via `create_hypertable`](#manually-via-create_hypertable)
  - [Direct hypertable creation (2.20+)](#direct-hypertable-creation-220)
- [Hypercore columnstore (2.18+)](#hypercore-columnstore-218)
- [Compression (legacy)](#compression-legacy)
- [Retention policies](#retention-policies)
- [Chunks](#chunks)
- [Background jobs](#background-jobs)
- [Continuous aggregates](#continuous-aggregates)
- [Querying with `time_bucket`](#querying-with-time_bucket)
- [Sample projects](#sample-projects)
- [FastAPI example](#fastapi-example)
- [Limitations & status](#limitations--status)
- [Contributing](#contributing)
- [Used by](#used-by)

## Requirements

- **Python:** 3.11, 3.12, 3.13, or 3.14.
- **PostgreSQL:** a PostgreSQL server with the TimescaleDB extension installed
  (the official `timescale/timescaledb` Docker images bundle both). The package
  targets PostgreSQL 15+ in CI.
- **TimescaleDB:** 2.x. Some features require newer releases:

  | Feature | Minimum TimescaleDB |
  | --- | --- |
  | Hypertables, compression, retention, continuous aggregates | 2.x |
  | Hypercore columnstore (`enable_columnstore`, `add_columnstore_policy`, …) | **2.18+** |
  | Direct `CREATE TABLE ... WITH (tsdb.hypertable)` (`create_table_with_hypertable`) | **2.20+** |
  | Generated aggregate columns on continuous aggregates (`add_generated_aggregate_column`) | **2.28+** |

- **A PostgreSQL driver:** any SQLAlchemy-compatible driver, e.g. `psycopg`
  (psycopg 3), `psycopg2`, or `asyncpg`. See [Installation](#installation).

## Installation

```bash
pip install timescaledb
```

You also need a PostgreSQL driver. Any SQLAlchemy-compatible driver works:
`psycopg2`, `psycopg` (v3), or `asyncpg`:

```bash
pip install "psycopg[binary]"   # recommended
```

The package registers `timescaledb` SQLAlchemy dialects, so connection URLs such
as `timescaledb://`, `timescaledb+psycopg://`, and `timescaledb+asyncpg://` are
available in addition to the standard `postgresql://` URLs.

### Optional dependencies

The core install is intentionally lightweight; it only depends on `SQLModel`
(plus the PostgreSQL driver you choose). FastAPI and uvicorn are **not** required
to use the library; they are only needed for the example apps. Install them via
the `fastapi` extra:

```bash
pip install "timescaledb[fastapi]"
```

This pulls in FastAPI + uvicorn so you can run the example FastAPI apps (see
[`samples/fastapi_timeseries_api`](./samples/fastapi_timeseries_api/) and
[`sample_project/`](./sample_project/)).

## Quickstart

```python
from sqlmodel import Field, Session, SQLModel, select

import timescaledb
from timescaledb import TimescaleModel

DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"

# create_engine pins the connection timezone (defaults to "UTC")
engine = timescaledb.create_engine(DATABASE_URL, timezone="UTC")


class Metric(TimescaleModel, table=True):
    # TimescaleModel already provides `id` and a `time` column
    sensor_id: int = Field(index=True)
    value: float


# 1. Create the regular tables
SQLModel.metadata.create_all(engine)
# 2. Convert TimescaleModel tables into hypertables (+ any policies)
timescaledb.metadata.create_all(engine)

with Session(engine) as session:
    session.add(Metric(sensor_id=1, value=42.0))
    session.commit()

    results = timescaledb.time_bucket_query(
        session,
        Metric,
        interval="1 hour",
        metric_field="value",
    )
    print(results)
```

`TimescaleModel` supplies the `id` primary key and a timezone-aware `time`
column for you, so a model only needs its own fields.

## Creating a hypertable

There are three ways to turn a table into a hypertable. Pick one:

1. **Automatically** with `TimescaleModel` + `timescaledb.metadata.create_all`:
   least code, configured with class variables.
2. **Manually** with `create_hypertable` on any table that has a `time` column.
3. **Directly** with `create_table_with_hypertable` (TimescaleDB 2.20+), which
   creates the table as a hypertable in a single statement.

### Automatically via `TimescaleModel`

```python
from sqlmodel import Field, Session, SQLModel

import timescaledb
from timescaledb import TimescaleModel

DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"
engine = timescaledb.create_engine(DATABASE_URL, timezone="UTC")


class SensorReading(TimescaleModel, table=True):
    sensor_id: int = Field(index=True)
    value: float

    # __time_column__ = "time"  # already set by TimescaleModel
    __chunk_time_interval__ = "INTERVAL 7 days"
    __drop_after__ = "INTERVAL 1 year"
    __enable_compression__ = True
    __compress_orderby__ = "time DESC"
    __compress_segmentby__ = "sensor_id"
    __migrate_data__ = True
    __if_not_exists__ = True


# Create the tables, then the hypertables + compression + retention policies
SQLModel.metadata.create_all(engine)
timescaledb.metadata.create_all(engine)
```

`timescaledb.metadata.create_all(engine)` walks every `TimescaleModel` subclass,
creates the hypertable, and applies whatever compression, columnstore, and
retention settings the model opts into.

### Database drivers (SQLAlchemy dialects)

`timescaledb` registers `timescaledb`-scheme SQLAlchemy dialects so you can make
the TimescaleDB backend explicit in your connection URL. Each one is a thin
subclass of the matching PostgreSQL driver, so behavior is identical to
PostgreSQL apart from the URL scheme:

| URL scheme | Driver | Dialect |
| --- | --- | --- |
| `timescaledb://` | `psycopg2` (default) | `TimescaledbPsycopg2Dialect` |
| `timescaledb+psycopg2://` | `psycopg2` | `TimescaledbPsycopg2Dialect` |
| `timescaledb+psycopg://` | `psycopg` (psycopg 3) | `TimescaledbPsycopgDialect` |
| `timescaledb+asyncpg://` | `asyncpg` | `TimescaledbAsyncpgDialect` |

```python
import timescaledb

# psycopg (psycopg 3)
engine = timescaledb.create_engine(
    "timescaledb+psycopg://user:password@localhost:5432/timescaledb"
)
```

Install the driver you intend to use, e.g. `pip install "psycopg[binary]"` for
psycopg 3, `pip install psycopg2-binary` for psycopg2, or `pip install asyncpg`
for asyncpg. Plain `postgresql://` URLs continue to work unchanged.

### Manually via `create_hypertable`

Use this on a plain `SQLModel` table (or any existing table) that has a `time`
column. It gives you the most direct control over each step:

```python
from sqlmodel import Field, Session, SQLModel
from datetime import datetime

import timescaledb

DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"
engine = timescaledb.create_engine(DATABASE_URL)


class Sensor(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    time: datetime = Field(default=None, primary_key=True)
    sensor_id: int = Field(index=True)
    value: float

    __tablename__ = "my_time_series_table"


hypertable_options = {
    "time_column": "time",
    "compress_orderby": "time DESC",
    "compress_segmentby": "sensor_id",
    "chunk_time_interval": "7 days",
    "drop_after": "1 year",
    "migrate_data": True,
    "if_not_exists": True,
}

table_name = "my_time_series_table"

with Session(engine) as session:
    # Create the table in the database
    SQLModel.metadata.create_all(engine)

    # Create the hypertable
    timescaledb.create_hypertable(
        session,
        commit=True,
        table_name=table_name,
        hypertable_options=hypertable_options,
    )

    # Enable compression
    timescaledb.enable_table_compression(
        session,
        commit=True,
        table_name=table_name,
        compress_orderby=hypertable_options["compress_orderby"],
        compress_segmentby=hypertable_options["compress_segmentby"],
    )
    # Compress chunks once they age past the chunk interval
    timescaledb.add_compression_policy(
        session,
        commit=True,
        table_name=table_name,
        compress_after=hypertable_options["chunk_time_interval"],
    )
    # Drop chunks after the retention window
    timescaledb.add_retention_policy(
        session,
        table_name=table_name,
        drop_after=hypertable_options["drop_after"],
    )
```

### Direct hypertable creation (2.20+)

TimescaleDB 2.20+ can create a table as a hypertable in one statement with
`CREATE TABLE ... WITH (tsdb.hypertable)`. For brand-new tables, compile and run
that SQL straight from a model:

```python
from sqlmodel import Session

import timescaledb

with Session(engine) as session:
    timescaledb.create_table_with_hypertable(
        session,
        SensorReading,
        chunk_interval="7 days",
    )
```

Use `timescaledb.format_create_table_with_hypertable_sql(...)` if you just want
the SQL string without executing it.

## Hypercore columnstore (2.18+)

TimescaleDB 2.18 introduced the Hypercore columnstore API. This package supports
the modern columnstore path (`enable_columnstore`, `add_columnstore_policy`,
`convert_to_columnstore` / `convert_to_rowstore`) while keeping the older
compression helpers available.

```python
from sqlmodel import Session

import timescaledb

with Session(engine) as session:
    timescaledb.enable_columnstore(
        session,
        table_name="my_time_series_table",
        orderby="time DESC",
        segmentby="sensor_id",
    )
    timescaledb.add_columnstore_policy(
        session,
        table_name="my_time_series_table",
        after="60 days",
        if_not_exists=True,
    )
```

You can opt in from a `TimescaleModel` instead. `timescaledb.metadata.create_all`
then enables columnstore and adds the policy automatically:

```python
from sqlmodel import Field

from timescaledb import TimescaleModel


class SensorReading(TimescaleModel, table=True):
    sensor_id: int = Field(index=True)
    value: float

    __enable_columnstore__ = True
    __columnstore_orderby__ = "time DESC"
    __columnstore_segmentby__ = "sensor_id"
    __columnstore_after__ = "60 days"
```

Available columnstore class variables: `__enable_columnstore__`,
`__columnstore_orderby__`, `__columnstore_segmentby__`, `__columnstore_after__`,
`__columnstore_created_before__`, `__columnstore_if_not_exists__`,
`__columnstore_schedule_interval__`, and `__columnstore_timezone__`.

Manual chunk conversion and policy inspection are also available via
`convert_to_columnstore`, `convert_to_rowstore`, `list_columnstore_policies`,
`remove_columnstore_policy`, and `sync_columnstore_policies`.

## Compression (legacy)

The pre-Hypercore compression helpers (`enable_table_compression`,
`add_compression_policy`, `sync_compression_policies`) remain fully supported for
existing code and older TimescaleDB versions. On TimescaleDB 2.18+, prefer the
[Hypercore columnstore](#hypercore-columnstore-218) API for new work. See the
[manual hypertable example](#manually-via-create_hypertable) above for usage.

## Retention policies

Drop chunks automatically once they age past a window:

```python
timescaledb.add_retention_policy(
    session,
    table_name="my_time_series_table",
    drop_after="1 year",
)
```

Or opt in from a model with `__drop_after__` and let
`timescaledb.metadata.create_all` apply it. Use `sync_retention_policies` to
reconcile policies across all opted-in models.

## Chunks

Chunks are the physical partitions that make up a hypertable. Inspect them with
`show_chunks` and remove them on demand with `drop_chunks`, the imperative
counterpart to a retention policy, handy for ad-hoc cleanup or fixing a backfill:

```python
# List every chunk of a hypertable
chunks = timescaledb.show_chunks(session, table_name="my_time_series_table")

# Only the chunks older than a window (also accepts a datetime, timedelta,
# or, for integer-partitioned hypertables, an int)
old = timescaledb.show_chunks(
    session,
    table_name="my_time_series_table",
    older_than="3 months",
)

# Drop chunks older than a window. At least one bound (older_than/newer_than/
# created_before/created_after) is required so you can't empty a hypertable by
# accident. Returns the names of the dropped chunks.
dropped = timescaledb.drop_chunks(
    session,
    table_name="my_time_series_table",
    older_than="3 months",
)
session.commit()
```

Both helpers also accept a `model=` argument instead of `table_name=`, and the
`created_before` / `created_after` bounds (TimescaleDB 2.8+).

## Background jobs

Every automated policy (retention, compression/columnstore, and
continuous-aggregate refresh) runs as a TimescaleDB *background job*. In
production you need to confirm those jobs actually run and succeed (a silently
failing compression job means unbounded storage growth), so the package lets you
inspect and manage them:

```python
# List jobs (optionally filtered by hypertable or policy procedure)
jobs = timescaledb.list_jobs(session)
retention_jobs = timescaledb.list_jobs(session, proc_name="policy_retention")

# Inspect run statistics: last run, last success, totals, failures
for stat in timescaledb.get_job_stats(session):
    print(stat.job_id, stat.last_run_status, stat.total_failures)

job_id = retention_jobs[0].job_id

# Run a job now (foreground), reschedule it, or pause/delete it
timescaledb.run_job(session, job_id)
timescaledb.alter_job(session, job_id, schedule_interval="6 hours")
timescaledb.alter_job(session, job_id, scheduled=False)  # pause
timescaledb.delete_job(session, job_id)
session.commit()
```

`list_jobs` returns `JobSchema` objects and `get_job_stats` returns
`JobStatsSchema` objects. ±infinity timestamps (e.g. a job that has never
succeeded) are normalised to `None`.

## Continuous aggregates

Continuous aggregates can be created, scheduled, refreshed, and extended from a
SQLModel session:

```python
from datetime import datetime, timezone
from sqlmodel import Session

import timescaledb

with Session(engine) as session:
    timescaledb.create_continuous_aggregate(
        session,
        "conditions_summary_hourly",
        """
        SELECT time_bucket('1 hour', time) AS bucket, avg(temp) AS avg_temp
        FROM conditions
        GROUP BY bucket
        """,
        with_data=False,
    )
    timescaledb.add_continuous_aggregate_policy(
        session,
        "conditions_summary_hourly",
        start_offset="1 month",
        end_offset="1 hour",
        schedule_interval="1 hour",
        buckets_per_batch=10,
        refresh_newest_first=True,
    )
    timescaledb.refresh_continuous_aggregate(
        session,
        "conditions_summary_hourly",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        force=True,
    )
    # TimescaleDB 2.28+: add a generated aggregate column without a full rebuild
    timescaledb.add_generated_aggregate_column(
        session,
        "conditions_summary_hourly",
        "max_temp",
        "DOUBLE PRECISION",
        "max(temp)",
    )
```

Remove a refresh policy with `remove_continuous_aggregate_policy`. The newer
policy options (`buckets_per_batch`, `max_batches_per_execution`,
`refresh_newest_first`, and `include_tiered_data`) are all supported.

## Querying with `time_bucket`

Two helpers wrap the most common time-series read patterns and return a list of
`{"bucket": ..., "avg": ...}` mappings.

`time_bucket_query` buckets rows by an interval and aggregates a metric field:

```python
rows = timescaledb.time_bucket_query(
    session,
    Metric,
    interval="1 hour",
    time_field="time",
    metric_field="value",
)
```

`time_bucket_gapfill_query` fills gaps in a bounded time range, with optional
**LOCF** (last observation carried forward) or **interpolation**:

```python
from datetime import datetime, timezone

rows = timescaledb.time_bucket_gapfill_query(
    session,
    Metric,
    interval="1 hour",
    metric_field="value",
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    finish=datetime(2026, 1, 2, tzinfo=timezone.utc),
    use_locf=True,        # or use_interpolate=True
)
```

Both accept a `filters` list of SQLAlchemy conditions for narrowing the query.

## Sample projects

The [`samples/`](./samples/) directory has **ten self-contained, fully tested**
example projects, each focused on a different TimescaleDB feature. Every sample
runs against TimescaleDB in Docker and ships with a `pytest` suite that spins up
a throwaway container automatically via
[`testcontainers`](https://testcontainers.com/).

| # | Project | Highlights |
|---|---------|------------|
| 01 | [`iot_sensor_network`](./samples/iot_sensor_network/) | `TimescaleModel`, `create_hypertable`, `time_bucket_query`, last-point query |
| 02 | [`devops_metrics_gapfill`](./samples/devops_metrics_gapfill/) | `time_bucket_gapfill_query` with gapfill, LOCF, and interpolation |
| 03 | [`crypto_ohlcv_candles`](./samples/crypto_ohlcv_candles/) | `first()`/`last()` + `time_bucket` → OHLCV candlesticks |
| 04 | [`energy_metering_compression`](./samples/energy_metering_compression/) | native compression + measuring the ratio |
| 05 | [`hypercore_columnstore`](./samples/hypercore_columnstore/) | Hypercore columnstore (2.18+) |
| 06 | [`ecommerce_clickstream_retention`](./samples/ecommerce_clickstream_retention/) | retention policy + funnel rollups |
| 07 | [`fleet_gps_tracking`](./samples/fleet_gps_tracking/) | manual `create_hypertable` path + downsampling |
| 08 | [`continuous_aggregates_rollups`](./samples/continuous_aggregates_rollups/) | hierarchical continuous aggregates (hourly → daily) |
| 09 | [`fastapi_timeseries_api`](./samples/fastapi_timeseries_api/) | a FastAPI REST API over a hypertable, tested with `TestClient` |
| 10 | [`weather_lifecycle_full`](./samples/weather_lifecycle_full/) | capstone: hypertable + columnstore + retention + continuous aggregate + gapfill |

See [`samples/README.md`](./samples/README.md) for setup and how to run the
suites. There is also a minimal end-to-end FastAPI app in
[`sample_project/`](./sample_project/).

## FastAPI example

A minimal FastAPI app over a hypertable. The pattern mirrors
[`sample_project/`](./sample_project/).

`models.py`
```python
from datetime import datetime

from sqlmodel import Field, SQLModel

from timescaledb import TimescaleModel


class Metric(TimescaleModel, table=True):
    temp: float

    __enable_compression__ = True
    __chunk_time_interval__ = "2 weeks"
    __drop_after__ = "1 year"


class MetricCreate(SQLModel):
    temp: float


class MetricRead(SQLModel):
    id: int
    temp: float
    time: datetime
```

`database.py`
```python
from sqlmodel import Session, SQLModel

import timescaledb

DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"

engine = timescaledb.create_engine(DATABASE_URL, timezone="UTC", echo=False)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    # Create all tables that inherit from SQLModel
    SQLModel.metadata.create_all(engine)
    # Create hypertables (+ policies) for all TimescaleModel subclasses
    timescaledb.metadata.create_all(engine)
```

`main.py`
```python
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from .database import get_session, init_db
from .models import Metric, MetricCreate, MetricRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/metrics/", response_model=MetricRead)
def create_metric(metric: MetricCreate, session: Session = Depends(get_session)):
    db_metric = Metric.model_validate(metric)
    session.add(db_metric)
    session.commit()
    session.refresh(db_metric)
    return db_metric


@app.get("/metrics/{metric_id}", response_model=MetricRead)
def read_metric(metric_id: int, session: Session = Depends(get_session)):
    metric = session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    return metric


@app.get("/metrics/", response_model=list[MetricRead])
def list_metrics(session: Session = Depends(get_session)):
    return session.exec(select(Metric)).all()
```

`timescaledb.create_engine` wraps `sqlmodel.create_engine` (itself a wrapper
around `sqlalchemy.create_engine`) and pins the connection timezone for you.

## Limitations & status

- **Beta.** The package is in the `0.x` series; the public API is still
  settling and may change between releases. Pin a version if you need stability.
- **Helpers are synchronous.** The `timescaledb.asyncpg` dialect is registered so
  you can use a `timescaledb+asyncpg://` URL with raw/async SQLAlchemy, but the
  helper functions in this package (`create_hypertable`, `time_bucket_query`,
  `enable_columnstore`, the continuous-aggregate helpers, etc.) are all
  synchronous and operate on a SQLModel/SQLAlchemy `Session`. There is no async
  helper API yet.

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for how to
set up a dev environment, run the test suite (Docker + `testcontainers`), run
lint/mypy, and the release process. For runnable, end-to-end examples of every
feature, see the [`samples/`](./samples/) directory.

## Used by

- [analytics-api](https://github.com/codingforentrepreneurs/analytics-api):
  complete tutorial project for building an Analytics API using FastAPI +
  TimescaleDB.

---

For a summary of recent upstream TimescaleDB changes and how they map onto this
package, see [`docs/timescale-recent-updates.md`](./docs/timescale-recent-updates.md).
</content>
</invoke>
