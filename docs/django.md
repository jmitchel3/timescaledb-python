# Django Support

`timescaledb.django` provides optional first-party Django support for Django 5.2
and newer. The core package does not import Django unless you use this namespace.

## Installation

```bash
pip install "timescaledb[django]" "psycopg[binary]"
```

The `django` extra installs Django only. Install the PostgreSQL driver you want
to use explicitly.

## Settings

```python
INSTALLED_APPS = [
    "timescaledb.django",
    # your apps
]

DATABASES = {
    "default": {
        "ENGINE": "timescaledb.django.db.backends.postgresql",
        "NAME": "timeseries",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

The backend subclasses Django's PostgreSQL backend and runs:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

Set `OPTIONS["timescaledb_auto_create_extension"] = False` if extension
activation is handled entirely by migrations or database provisioning.

## Models

```python
from timescaledb.django.db import models


class Metric(models.TimescaleModel):
    time = models.TimescaleDateTimeField(interval="1 hour")
    sensor_id = models.IntegerField()
    value = models.FloatField()
```

`timescaledb.django.db.models` reexports Django model fields and adds:

- `TimescaleModel`
- `TimescaleDateTimeField`
- `TimescaleQuerySet.time_bucket`
- `TimescaleQuerySet.time_bucket_gapfill`

Migrations remain the source of truth for TimescaleDB schema changes.

## Migrations

```python
from django.db import migrations
from timescaledb.django.db import migrations as timescale_migrations


class Migration(migrations.Migration):
    operations = [
        timescale_migrations.CreateExtension(),
        timescale_migrations.CreateHypertable(
            model_name="metric",
            time_column="time",
            chunk_time_interval="1 day",
            if_not_exists=True,
        ),
        timescale_migrations.AddRetentionPolicy(
            model_name="metric",
            drop_after="90 days",
        ),
        timescale_migrations.EnableColumnstore(
            model_name="metric",
            orderby="time DESC",
            segmentby="sensor_id",
        ),
        timescale_migrations.AddColumnstorePolicy(
            model_name="metric",
            after="30 days",
            if_not_exists=True,
        ),
    ]
```

Available operations include:

- Extension: `CreateExtension`
- Hypertables: `CreateHypertable`, `DropHypertable`
- Retention: `AddRetentionPolicy`, `RemoveRetentionPolicy`
- Legacy compression: `EnableCompression`, `AddCompressionPolicy`,
  `RemoveCompressionPolicy`
- Hypercore columnstore: `EnableColumnstore`, `AddColumnstorePolicy`,
  `RemoveColumnstorePolicy`
- Continuous aggregates: `CreateContinuousAggregate`,
  `AddGeneratedAggregateColumn`, `RefreshContinuousAggregate`,
  `AddContinuousAggregatePolicy`, `RemoveContinuousAggregatePolicy`

Some operations are intentionally irreversible when TimescaleDB does not provide
a safe inverse.

## Query Helpers

```python
from django.db.models import Avg
from timescaledb.django.db.functions import TimeBucket

Metric.objects.annotate(bucket=TimeBucket("1 hour", "time")).values(
    "bucket"
).annotate(avg_value=Avg("value"))
```

Expression helpers:

- `TimeBucket`
- `TimeBucketGapfill`
- `Histogram`
- `First`
- `Last`
- `Locf`
- `Interpolate`

The queryset shims wrap the most common annotations:

```python
Metric.objects.time_bucket("1 hour").values("bucket").annotate(avg_value=Avg("value"))
```

## Sample Project

See [`samples/django_timeseries_dashboard`](../samples/django_timeseries_dashboard/)
for a runnable Django project with model migrations, TimescaleDB migration
operations, seed data, raw readings, and hourly rollups.
