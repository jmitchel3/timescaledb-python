from __future__ import annotations

import builtins
import importlib
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

import pytest
from django.conf import settings


if not settings.configured:
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        INSTALLED_APPS=["django.contrib.contenttypes", "timescaledb.django"],
        SECRET_KEY="tests",
        USE_TZ=True,
    )

import django
from django.apps import apps
from django.db import connections
from django.db import models as django_models
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.state import ModelState
from django.db.migrations.state import ProjectState
from django.db.models import Avg

if not apps.ready:
    django.setup()

from timescaledb.django import _django_version_tuple
from timescaledb.django import _validate_django_version
from timescaledb.django.apps import TimescaleDBConfig
from timescaledb.django.db import functions
from timescaledb.django.db import migrations
from timescaledb.django.db import models
from timescaledb.django.db.backends.postgresql import base as backend_base

APP_LABEL = "django_test_app"


class DjangoMetric(models.TimescaleModel):
    time = models.TimescaleDateTimeField(interval="1 hour")
    epoch = models.IntegerField(default=0)
    device_id = models.IntegerField(default=1)
    value = models.FloatField(default=0)

    class Meta:
        app_label = APP_LABEL


class IntegrationMetric(models.TimescaleModel):
    time = models.TimescaleDateTimeField(interval="1 hour", primary_key=True)
    device_id = models.IntegerField()
    value = models.FloatField()

    class Meta:
        app_label = APP_LABEL
        db_table = "sensor_metric"
        managed = False


class RecordingSchemaEditor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(str(sql))


def _project_state() -> ProjectState:
    state = ProjectState()
    state.add_model(
        ModelState(
            APP_LABEL,
            "Metric",
            fields=[
                ("id", django_models.BigAutoField(primary_key=True)),
                ("time", django_models.DateTimeField()),
            ],
            options={"db_table": "sensor_metric"},
        )
    )
    return state


def _run_forward(operation: Any, state: ProjectState | None = None) -> str:
    editor = RecordingSchemaEditor()
    migration_state = state or _project_state()
    operation.database_forwards(APP_LABEL, editor, migration_state, migration_state)
    return editor.statements[-1]


def _run_backward(operation: Any, state: ProjectState | None = None) -> str:
    editor = RecordingSchemaEditor()
    migration_state = state or _project_state()
    operation.database_backwards(APP_LABEL, editor, migration_state, migration_state)
    return editor.statements[-1]


def _query_sql(queryset: Any) -> tuple[str, tuple[Any, ...]]:
    return queryset.query.sql_with_params()


def _database_settings_from_url(database_url: str) -> dict[str, Any]:
    parsed = urlparse(database_url)
    return {
        "ENGINE": "timescaledb.django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "OPTIONS": {"timescaledb_auto_create_extension": True},
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "CONN_HEALTH_CHECKS": False,
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": False,
        "TIME_ZONE": None,
        "TEST": {
            "CHARSET": None,
            "COLLATION": None,
            "MIGRATE": True,
            "MIRROR": None,
            "NAME": None,
        },
    }


def test_django_version_guard_accepts_5_2_and_rejects_older_versions() -> None:
    assert _validate_django_version((5, 2, 0, "final", 0)) == (
        5,
        2,
        0,
        "final",
        0,
    )

    with pytest.raises(ImportError, match="supports Django 5.2 and newer"):
        _validate_django_version((5, 1, 9, "final", 0))


def test_django_version_guard_reports_missing_django(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "django":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ImportError, match="requires Django 5.2"):
        _django_version_tuple()


def test_app_config_enforces_supported_django_version() -> None:
    app_config = TimescaleDBConfig(
        "timescaledb.django",
        importlib.import_module("timescaledb.django"),
    )

    assert app_config.label == "timescaledb_django"
    app_config.ready()


def test_model_shims_reexport_django_models_and_deconstruct_cleanly() -> None:
    assert models.IntegerField is django_models.IntegerField
    assert isinstance(DjangoMetric.objects.get_queryset(), models.TimescaleQuerySet)

    field = models.TimescaleDateTimeField(interval="2 hours")
    _, path, _, kwargs = field.deconstruct()
    assert path == "timescaledb.django.db.models.TimescaleDateTimeField"
    assert kwargs["interval"] == "2 hours"
    assert kwargs["db_index"] is True

    default_field = models.TimescaleDateTimeField()
    assert "interval" not in default_field.deconstruct()[3]


def test_time_bucket_expression_compiles_interval_and_integer_buckets() -> None:
    sql, params = _query_sql(
        DjangoMetric.objects.annotate(bucket=functions.TimeBucket("1 hour", "time"))
    )
    assert "time_bucket(CAST(%s AS INTERVAL)" in sql
    assert "1 hour" in params

    sql, params = _query_sql(
        DjangoMetric.objects.annotate(
            bucket=functions.TimeBucket(
                300,
                "epoch",
                output_field=django_models.IntegerField(),
            )
        )
    )
    assert "time_bucket(%s" in sql
    assert 300 in params


def test_time_bucket_expression_compiles_optional_arguments() -> None:
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sql, params = _query_sql(
        DjangoMetric.objects.annotate(
            bucket=functions.TimeBucket(
                "1 hour",
                "time",
                timezone="UTC",
                origin=origin,
                offset="15 minutes",
            )
        )
    )

    assert "time_bucket(CAST(%s AS INTERVAL)" in sql
    assert "UTC" in params
    assert "15 minutes" in params
    assert "2026-01-01 00:00:00" in params


def test_time_bucket_gapfill_and_gapfill_manager_compile() -> None:
    sql, params = _query_sql(
        DjangoMetric.objects.time_bucket_gapfill(
            "1 hour",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            finish=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert "time_bucket_gapfill(CAST(%s AS INTERVAL)" in sql
    assert "1 hour" in params


def test_manager_time_bucket_helper_compiles() -> None:
    sql, params = _query_sql(DjangoMetric.objects.time_bucket("2 hours"))

    assert "time_bucket(CAST(%s AS INTERVAL)" in sql
    assert "2 hours" in params


def test_timescale_aggregate_expressions_compile() -> None:
    sql, params = _query_sql(
        DjangoMetric.objects.annotate(
            first_value=functions.First("value", "time"),
            last_value=functions.Last("value", "time"),
            histogram=functions.Histogram("value", 0, 100, 10),
            carried=functions.Locf("value", prev=0, treat_null_as_missing=True),
            interpolated=functions.Interpolate("value", prev=1, next=2),
        )
    )

    assert "first(" in sql
    assert "last(" in sql
    assert "histogram(" in sql
    assert "locf(" in sql
    assert "interpolate(" in sql
    assert 100 in params
    assert True in params


def test_time_bucket_rejects_invalid_integer_options() -> None:
    with pytest.raises(ValueError, match="timezone is not supported"):
        functions.TimeBucket(300, "epoch", timezone="UTC")

    with pytest.raises(ValueError, match="timezone is not supported"):
        functions.TimeBucketGapfill(300, "epoch", timezone="UTC")

    with pytest.raises(ValueError, match="integer offsets"):
        _query_sql(
            DjangoMetric.objects.annotate(
                bucket=functions.TimeBucket("1 hour", "time", offset=1)
            )
        )

    invalid = functions._IntervalOrIntegerValue(object())  # noqa: SLF001
    with pytest.raises(ValueError, match="interval value"):
        invalid.as_sql(None, None)


def test_expression_helpers_cover_timedelta_and_expression_inputs() -> None:
    assert functions._clean_interval(timedelta(seconds=90)) == "90 seconds"  # noqa: SLF001
    assert functions._clean_interval(timedelta(milliseconds=1500)) == "1.5 seconds"  # noqa: SLF001
    field_expression = django_models.F("value")
    assert functions._field_expression(field_expression) is field_expression  # noqa: SLF001
    assert isinstance(functions._field_expression(42), django_models.Value)  # noqa: SLF001
    value_expression = django_models.Value("2026-01-01")
    assert functions._literal_expression(value_expression) is value_expression  # noqa: SLF001

    sql, params = _query_sql(
        DjangoMetric.objects.annotate(
            bucket=functions.TimeBucket(
                timedelta(hours=1),
                django_models.F("time"),
                origin=value_expression,
            )
        )
    )
    assert "time_bucket(CAST(%s AS INTERVAL)" in sql
    assert "3600 seconds" in params
    assert "2026-01-01" in params


def test_gapfill_locf_and_interpolate_optional_argument_branches() -> None:
    sql, params = _query_sql(
        DjangoMetric.objects.annotate(
            bucket=functions.TimeBucketGapfill(
                "1 hour",
                "time",
                timezone="UTC",
            ),
            carried=functions.Locf("value"),
            interpolated=functions.Interpolate("value"),
        )
    )

    assert "time_bucket_gapfill(CAST(%s AS INTERVAL)" in sql
    assert "locf(" in sql
    assert "interpolate(" in sql
    assert "UTC" in params


def test_backend_creates_timescaledb_extension() -> None:
    statements: list[str] = []

    class Cursor:
        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def execute(self, sql: str) -> None:
            statements.append(sql)

    class Wrapper(backend_base.DatabaseWrapper):
        def __init__(self, settings_dict: dict[str, Any]) -> None:
            self.settings_dict = settings_dict

        def cursor(self) -> Cursor:
            return Cursor()

    wrapper = Wrapper({"OPTIONS": {}})
    assert wrapper._timescaledb_auto_create_extension_enabled() is True
    wrapper.ensure_timescaledb_extension()
    assert statements == ["CREATE EXTENSION IF NOT EXISTS timescaledb;"]

    assert (
        Wrapper({"OPTIONS": {"timescaledb_auto_create_extension": False}})
        ._timescaledb_auto_create_extension_enabled()
        is False
    )
    assert (
        Wrapper({"TIMESCALEDB_AUTO_CREATE_EXTENSION": False, "OPTIONS": {}})
        ._timescaledb_auto_create_extension_enabled()
        is False
    )


def test_backend_init_connection_state_runs_extension_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Wrapper(backend_base.DatabaseWrapper):
        def __init__(self, settings_dict: dict[str, Any]) -> None:
            self.settings_dict = settings_dict

    wrapper = Wrapper({"OPTIONS": {}})
    monkeypatch.setattr(
        backend_base.PostgresDatabaseWrapper,
        "init_connection_state",
        lambda self: calls.append("postgres"),
    )
    monkeypatch.setattr(
        wrapper,
        "ensure_timescaledb_extension",
        lambda: calls.append("timescaledb"),
    )

    wrapper.init_connection_state()
    assert calls == ["postgres", "timescaledb"]

    calls.clear()
    disabled_wrapper = Wrapper({"OPTIONS": {"timescaledb_auto_create_extension": False}})
    monkeypatch.setattr(
        disabled_wrapper,
        "ensure_timescaledb_extension",
        lambda: calls.append("disabled"),
    )
    disabled_wrapper.init_connection_state()
    assert calls == ["postgres"]


def test_backend_strips_custom_option_from_driver_connection_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Wrapper(backend_base.DatabaseWrapper):
        def __init__(self) -> None:
            self.settings_dict = {"OPTIONS": {"timescaledb_auto_create_extension": True}}

    monkeypatch.setattr(
        backend_base.PostgresDatabaseWrapper,
        "get_connection_params",
        lambda self: {
            "dbname": "test",
            "timescaledb_auto_create_extension": True,
        },
    )

    assert Wrapper().get_connection_params() == {"dbname": "test"}


@pytest.mark.parametrize(
    ("operation", "description"),
    [
        (migrations.CreateExtension(), "Creates"),
        (migrations.CreateHypertable("Metric"), "Creates"),
        (migrations.DropHypertable("Metric"), "Drops"),
        (migrations.AddRetentionPolicy("Metric", drop_after="90 days"), "Adds"),
        (migrations.RemoveRetentionPolicy("Metric"), "Removes"),
        (migrations.EnableCompression("Metric"), "Enables"),
        (
            migrations.AddCompressionPolicy("Metric", compress_after="30 days"),
            "Adds",
        ),
        (migrations.RemoveCompressionPolicy("Metric"), "Removes"),
        (migrations.EnableColumnstore("Metric"), "Enables"),
        (migrations.AddColumnstorePolicy("Metric", after="30 days"), "Adds"),
        (migrations.RemoveColumnstorePolicy("Metric"), "Removes"),
        (
            migrations.CreateContinuousAggregate(
                "metric_hourly",
                "SELECT time_bucket('1 hour', time) AS bucket FROM sensor_metric GROUP BY bucket",
            ),
            "Creates",
        ),
        (
            migrations.AddGeneratedAggregateColumn(
                "metric_hourly",
                "max_value",
                "DOUBLE PRECISION",
                "max(value)",
            ),
            "Adds",
        ),
        (migrations.RefreshContinuousAggregate("metric_hourly"), "Refreshes"),
        (
            migrations.AddContinuousAggregatePolicy(
                "metric_hourly",
                start_offset="7 days",
                end_offset="1 hour",
                schedule_interval="1 hour",
            ),
            "Adds",
        ),
        (migrations.RemoveContinuousAggregatePolicy("metric_hourly"), "Removes"),
    ],
)
def test_migration_operations_describe_and_deconstruct(
    operation: Any,
    description: str,
) -> None:
    assert description in operation.describe()
    assert operation.migration_name_fragment
    assert operation.state_forwards(APP_LABEL, _project_state()) is None
    name, args, kwargs = operation.deconstruct()
    assert name == operation.__class__.__name__
    assert args == []
    assert set(kwargs) == set(operation.serialization_attrs)


def test_create_extension_operation_sql_and_validation() -> None:
    operation = migrations.CreateExtension(if_not_exists=False)
    assert _run_forward(operation) == "CREATE EXTENSION timescaledb;"
    assert _run_backward(operation) == "DROP EXTENSION IF EXISTS timescaledb;"

    with pytest.raises(ValueError, match="extension_name"):
        _run_forward(migrations.CreateExtension("timescaledb;drop"))


def test_hypertable_operations_use_model_state_table_names() -> None:
    create_sql = _run_forward(
        migrations.CreateHypertable(
            "Metric",
            chunk_time_interval="12 hours",
            if_not_exists=True,
            migrate_data=True,
        )
    )
    assert "SELECT create_hypertable" in create_sql
    assert "'sensor_metric'" in create_sql
    assert "INTERVAL '12 hours'" in create_sql
    assert "if_not_exists => true" in create_sql

    drop_sql = _run_forward(
        migrations.DropHypertable(table_name="public.sensor_metric", cascade=False)
    )
    assert drop_sql == 'DROP TABLE IF EXISTS "public"."sensor_metric";'

    with pytest.raises(IrreversibleError):
        migrations.CreateHypertable("Metric").database_backwards(
            APP_LABEL,
            RecordingSchemaEditor(),
            _project_state(),
            _project_state(),
        )
    with pytest.raises(IrreversibleError):
        migrations.DropHypertable("Metric").database_backwards(
            APP_LABEL,
            RecordingSchemaEditor(),
            _project_state(),
            _project_state(),
        )
    with pytest.raises(ValueError, match="model_name or table_name"):
        migrations.CreateHypertable()

    malformed_operation = migrations.CreateHypertable(table_name="sensor_metric")
    malformed_operation.table_name = None
    with pytest.raises(ValueError, match="model_name or table_name"):
        malformed_operation._resolve_table_name(APP_LABEL, _project_state())  # noqa: SLF001


def test_retention_policy_operations_are_reversible_when_configured() -> None:
    add_sql = _run_forward(migrations.AddRetentionPolicy("Metric", drop_after="90 days"))
    assert "SELECT add_retention_policy" in add_sql
    assert "INTERVAL '90 days'" in add_sql

    remove_sql = _run_backward(migrations.AddRetentionPolicy("Metric", drop_after="90 days"))
    assert "SELECT remove_retention_policy" in remove_sql

    remove_operation = migrations.RemoveRetentionPolicy("Metric", drop_after="30 days")
    assert "remove_retention_policy" in _run_forward(remove_operation)
    assert "add_retention_policy" in _run_backward(remove_operation)

    with pytest.raises(IrreversibleError, match="drop_after"):
        _run_backward(migrations.RemoveRetentionPolicy("Metric"))


def test_compression_policy_operations_cover_forward_and_reverse_sql() -> None:
    assert migrations._compile_sql("SELECT 1") == "SELECT 1"  # noqa: SLF001

    plain_enable_sql = _run_forward(migrations.EnableCompression("Metric"))
    assert "timescaledb.compress" in plain_enable_sql
    assert "compress_orderby" not in plain_enable_sql

    enable_sql = _run_forward(
        migrations.EnableCompression(
            "Metric",
            compress_orderby="time DESC",
            compress_segmentby="device_id",
        )
    )
    assert 'ALTER TABLE "sensor_metric" SET' in enable_sql
    assert "timescaledb.compress_orderby = 'time DESC'" in enable_sql
    assert "timescaledb.compress_segmentby = 'device_id'" in enable_sql

    with pytest.raises(IrreversibleError):
        _run_backward(migrations.EnableCompression("Metric"))

    add_operation = migrations.AddCompressionPolicy("Metric", compress_after="7 days")
    assert "add_compression_policy" in _run_forward(add_operation)
    assert "remove_compression_policy" in _run_backward(add_operation)

    remove_operation = migrations.RemoveCompressionPolicy(
        "Metric",
        compress_after="7 days",
    )
    assert "remove_compression_policy" in _run_forward(remove_operation)
    assert "add_compression_policy" in _run_backward(remove_operation)

    with pytest.raises(ValueError, match="required"):
        migrations.AddCompressionPolicy("Metric")
    with pytest.raises(ValueError, match="only one"):
        migrations.AddCompressionPolicy(
            "Metric",
            compress_after="7 days",
            compress_created_before=timedelta(days=1),
        )
    with pytest.raises(IrreversibleError, match="compress_after"):
        _run_backward(migrations.RemoveCompressionPolicy("Metric"))


def test_columnstore_operations_cover_forward_and_reverse_sql() -> None:
    enable_sql = _run_forward(
        migrations.EnableColumnstore(
            "Metric",
            orderby="time DESC",
            segmentby="device_id",
        )
    )
    assert 'ALTER TABLE "sensor_metric" SET' in enable_sql
    assert "timescaledb.enable_columnstore = true" in enable_sql
    assert "timescaledb.orderby = 'time DESC'" in enable_sql

    with pytest.raises(IrreversibleError):
        _run_backward(migrations.EnableColumnstore("Metric"))

    add_operation = migrations.AddColumnstorePolicy(
        "Metric",
        after="30 days",
        schedule_interval="1 hour",
        if_not_exists=True,
    )
    assert "CALL add_columnstore_policy" in _run_forward(add_operation)
    assert "CALL remove_columnstore_policy" in _run_backward(add_operation)

    remove_operation = migrations.RemoveColumnstorePolicy("Metric", after="30 days")
    assert "CALL remove_columnstore_policy" in _run_forward(remove_operation)
    assert "CALL add_columnstore_policy" in _run_backward(remove_operation)

    with pytest.raises(IrreversibleError, match="after or created_before"):
        _run_backward(migrations.RemoveColumnstorePolicy("Metric"))


def test_continuous_aggregate_operations_cover_lifecycle_sql() -> None:
    create_operation = migrations.CreateContinuousAggregate(
        "analytics.metric_hourly",
        """
        SELECT time_bucket('1 hour', time) AS bucket, avg(value) AS avg_value
        FROM sensor_metric
        GROUP BY bucket
        """,
        column_names=["bucket", "avg_value"],
        chunk_interval="1 day",
        create_group_indexes=False,
        finalized=True,
        materialized_only=False,
        invalidate_using="wal",
        with_data=False,
    )
    create_sql = _run_forward(create_operation)
    assert 'CREATE MATERIALIZED VIEW "analytics"."metric_hourly"' in create_sql
    assert "timescaledb.continuous" in create_sql
    assert "WITH NO DATA" in create_sql
    assert (
        _run_backward(create_operation)
        == 'DROP MATERIALIZED VIEW IF EXISTS "analytics"."metric_hourly" CASCADE;'
    )

    generated_column = migrations.AddGeneratedAggregateColumn(
        "analytics.metric_hourly",
        "max_value",
        "DOUBLE PRECISION",
        "max(value)",
    )
    assert "ADD COLUMN" in _run_forward(generated_column)
    assert (
        _run_backward(generated_column)
        == 'ALTER MATERIALIZED VIEW "analytics"."metric_hourly" DROP COLUMN IF EXISTS "max_value";'
    )

    refresh = migrations.RefreshContinuousAggregate(
        "metric_hourly",
        window_start="2026-01-01",
        window_end="2026-01-02",
        force=True,
        refresh_newest_first=False,
    )
    assert "CALL refresh_continuous_aggregate" in _run_forward(refresh)
    with pytest.raises(IrreversibleError):
        _run_backward(refresh)

    add_policy = migrations.AddContinuousAggregatePolicy(
        "metric_hourly",
        start_offset="7 days",
        end_offset="1 hour",
        schedule_interval="1 hour",
        if_not_exists=True,
        timezone="UTC",
        include_tiered_data=False,
        buckets_per_batch=2,
        max_batches_per_execution=1,
        refresh_newest_first=False,
    )
    assert "add_continuous_aggregate_policy" in _run_forward(add_policy)
    assert "remove_continuous_aggregate_policy" in _run_backward(add_policy)

    remove_policy = migrations.RemoveContinuousAggregatePolicy(
        "metric_hourly",
        start_offset="7 days",
        end_offset="1 hour",
        schedule_interval="1 hour",
    )
    assert "remove_continuous_aggregate_policy" in _run_forward(remove_policy)
    assert "add_continuous_aggregate_policy" in _run_backward(remove_policy)

    with pytest.raises(IrreversibleError, match="schedule_interval"):
        _run_backward(migrations.RemoveContinuousAggregatePolicy("metric_hourly"))


def test_django_sample_project_contains_expected_timescale_surfaces() -> None:
    sample_dir = Path("samples/django_timeseries_dashboard")
    settings_text = (sample_dir / "dashboard/settings.py").read_text()
    models_text = (sample_dir / "readings/models.py").read_text()
    migration_text = (sample_dir / "readings/migrations/0002_timescale.py").read_text()
    views_text = (sample_dir / "readings/views.py").read_text()
    seed_text = (
        sample_dir / "readings/management/commands/seed_readings.py"
    ).read_text()

    assert "timescaledb.django.db.backends.postgresql" in settings_text
    assert "TimescaleDateTimeField" in models_text
    assert "CreateHypertable" in migration_text
    assert "AddRetentionPolicy" in migration_text
    assert "AddColumnstorePolicy" in migration_text
    assert "TimeBucket" in views_text
    assert "bulk_create" in seed_text


def test_django_backend_migration_and_orm_integration_against_timescale(
    timescale_url: str,
) -> None:
    alias = "timescale_django_integration"
    connections.databases[alias] = _database_settings_from_url(timescale_url)
    connection = connections[alias]
    state = _project_state()

    try:
        with connection.schema_editor(atomic=False) as schema_editor:
            schema_editor.execute('DROP MATERIALIZED VIEW IF EXISTS "metric_hourly" CASCADE;')
            schema_editor.execute('DROP TABLE IF EXISTS "sensor_metric" CASCADE;')
            schema_editor.execute(
                """
CREATE TABLE "sensor_metric" (
    "time" TIMESTAMPTZ NOT NULL PRIMARY KEY,
    "device_id" INTEGER NOT NULL,
    "value" DOUBLE PRECISION NOT NULL
);
"""
            )
            migrations.CreateExtension().database_forwards(
                APP_LABEL,
                schema_editor,
                state,
                state,
            )
            migrations.CreateHypertable(
                "Metric",
                chunk_time_interval="1 day",
                if_not_exists=True,
            ).database_forwards(APP_LABEL, schema_editor, state, state)
            schema_editor.execute(
                """
INSERT INTO "sensor_metric" ("time", "device_id", "value")
VALUES
    ('2026-01-01 00:00:00+00', 1, 10.0),
    ('2026-01-01 01:00:00+00', 1, 12.0);
"""
            )
            migrations.AddRetentionPolicy("Metric", drop_after="90 days").database_forwards(
                APP_LABEL,
                schema_editor,
                state,
                state,
            )
            migrations.RemoveRetentionPolicy("Metric").database_forwards(
                APP_LABEL,
                schema_editor,
                state,
                state,
            )
            migrations.CreateContinuousAggregate(
                "metric_hourly",
                """
SELECT time_bucket('1 hour', time) AS bucket, avg(value) AS avg_value
FROM sensor_metric
GROUP BY bucket
""",
                with_data=False,
            ).database_forwards(APP_LABEL, schema_editor, state, state)

        rows = list(
            IntegrationMetric.objects.using(alias)
            .annotate(bucket=functions.TimeBucket("1 hour", "time"))
            .values("bucket")
            .annotate(avg_value=Avg("value"))
            .order_by("bucket")
        )

        assert [row["avg_value"] for row in rows] == [10.0, 12.0]

        with connection.cursor() as cursor:
            cursor.execute(
                """
SELECT count(*)
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'sensor_metric';
"""
            )
            assert cursor.fetchone()[0] == 1
    finally:
        try:
            if connection.connection is not None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'DROP MATERIALIZED VIEW IF EXISTS "metric_hourly" CASCADE;'
                    )
                    cursor.execute('DROP TABLE IF EXISTS "sensor_metric" CASCADE;')
        finally:
            connection.close()
            connections.databases.pop(alias, None)
