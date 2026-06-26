# Django Support Plan

## Goal

Add first-class Django support to this package through an optional
`timescaledb[django]` install, a Django integration namespace, migration
operations, ORM query helpers, and a sample Django project.

The intended outcome is that Django users can use this package directly instead
of relying on older third-party integrations that target older Django/Python
versions.

## Guiding Decisions

- Keep Django optional. The default install should remain lightweight for
  SQLModel, SQLAlchemy, FastAPI, and Flask users.
- Use the package namespace: `timescaledb.django`, with convenience imports under
  `timescaledb.django.db`.
- Prefer explicit migration operations for database changes. TimescaleDB schema
  behavior should be visible in Django migrations instead of hidden behind model
  import side effects.
- Add a thin custom Django PostgreSQL backend to activate the TimescaleDB
  extension safely.
- Add compatibility-style shims, but do not clone older third-party internals
  wholesale.
- Replace public documentation references to older third-party integrations with
  the new first-party Django integration once available.

## Proposed Public API

### Installation

```bash
pip install "timescaledb[django]"
```

### Settings

```python
INSTALLED_APPS = [
    "timescaledb.django",
    # ...
]

DATABASES = {
    "default": {
        "ENGINE": "timescaledb.django.db.backends.postgresql",
        # standard Django PostgreSQL connection settings
    }
}
```

### Models

```python
from timescaledb.django.db import models


class Metric(models.TimescaleModel):
    time = models.TimescaleDateTimeField(interval="1 day")
    sensor_id = models.IntegerField()
    value = models.FloatField()
```

### Migrations

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
    ]
```

### Queries

```python
from timescaledb.django.db.functions import TimeBucket

Metric.objects.annotate(bucket=TimeBucket("1 hour", "time"))
```

## Workstreams

### 1. Packaging

- Add a `django` optional dependency group in `pyproject.toml`.
- Choose supported Django versions based on currently supported upstream Django
  releases.
- Keep PostgreSQL driver dependencies explicit in docs unless the Django extra
  intentionally pins one.

### 2. Django App Namespace

Add a package layout similar to:

```text
src/timescaledb/django/
    __init__.py
    apps.py
    db/
        __init__.py
        models.py
        migrations.py
        functions.py
        backends/
            postgresql/
                __init__.py
                base.py
```

The `timescaledb.django.db` namespace should expose the common model, field,
migration, and query helper APIs.

### 3. Custom Backend

Create `timescaledb.django.db.backends.postgresql` as a thin subclass of
Django's built-in PostgreSQL backend.

Initial responsibilities:

- Preserve standard Django PostgreSQL behavior.
- Run `CREATE EXTENSION IF NOT EXISTS timescaledb` at an appropriate database
  setup point.
- Avoid adding custom schema editor behavior unless a concrete feature requires
  it.
- Work with standard Django migrations and tests.

### 4. Migration Operations

Add explicit migration operations for common TimescaleDB lifecycle tasks:

- `CreateExtension`
- `CreateHypertable`
- `DropHypertable` or a documented reversal strategy
- `AddRetentionPolicy`
- `RemoveRetentionPolicy`
- `EnableCompression` for legacy compression
- `AddCompressionPolicy`
- `EnableColumnstore` for Hypercore
- `AddColumnstorePolicy`
- `RemoveColumnstorePolicy`
- Continuous aggregate creation and policy helpers where practical

These operations should reuse existing SQL-generation code where possible rather
than duplicating TimescaleDB SQL by hand.

### 5. ORM Helpers

Add Django expression helpers for TimescaleDB functions:

- `TimeBucket`
- `TimeBucketGapfill`
- `Histogram`
- `First`
- `Last`
- Gapfill helpers such as `Locf` and `Interpolate` if they compose cleanly with
  Django expressions.

These helpers should be usable independently of the compatibility model shims.

### 6. Compatibility Shims

Add Django-friendly convenience APIs:

- `TimescaleModel`
- `TimescaleDateTimeField`
- Optional manager/queryset helpers for common time-bucket queries

The shims should make simple cases pleasant, but migrations should remain the
source of truth for database setup.

### 7. Sample Django Project

Add a sample project under `samples/django_timeseries_dashboard/`.

It should demonstrate:

- Installing with `timescaledb[django]`
- Configuring the custom Django backend
- A Django model using `timescaledb.django.db.models`
- Migrations that activate TimescaleDB and create a hypertable
- Retention policy setup
- Hypercore/columnstore policy setup
- Seed data via a Django management command
- Time-bucket aggregation using Django ORM helpers
- A simple view or API endpoint for raw readings and rollups
- A README with setup, migration, seed, and run commands

The sample should prove the integration works in a normal Django project, not
just through isolated helper functions.

### 8. Documentation

Update public docs to cover:

- Why Django support is first-party in this package.
- Installation with `timescaledb[django]`.
- Backend configuration.
- Model and migration examples.
- Query helper examples.
- Sample project walkthrough.
- Limitations and version support.

Remove the README recommendation to use an older third-party integration once
first-party Django support is implemented.

### 9. Tests

Add focused coverage for:

- Optional import behavior when Django is not installed.
- Django app import and settings integration.
- Migration operation SQL generation.
- Backend extension activation behavior.
- ORM expression SQL compilation.
- Integration tests against a TimescaleDB container.
- Sample project smoke tests.

The initial tests should prioritize deterministic SQL generation and migration
behavior, then expand to database-backed integration coverage.

## Suggested Sequence

1. Add the optional dependency and package skeleton.
2. Implement migration operations for extension activation and hypertable
   creation.
3. Add the custom backend.
4. Add ORM expression helpers.
5. Add compatibility model/field shims.
6. Add the sample Django project.
7. Update README and docs to remove older third-party integration references.
8. Expand integration tests and CI coverage.

## Open Questions

- Which Django versions should the first release support?
- Should `timescaledb[django]` install a PostgreSQL driver, or should docs keep
  driver installation explicit?
- Should extension activation happen only through migrations, only through the
  custom backend, or both?
- How much of the existing SQLModel-oriented model configuration should be
  mirrored in Django model metadata?
- Which continuous aggregate features belong in the first Django release versus
  a follow-up?
