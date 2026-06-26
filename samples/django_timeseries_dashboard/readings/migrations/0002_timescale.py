from __future__ import annotations

from django.db import migrations

from timescaledb.django.db import migrations as timescale_migrations


class Migration(migrations.Migration):
    dependencies = [
        ("readings", "0001_initial"),
    ]

    operations = [
        timescale_migrations.CreateExtension(),
        timescale_migrations.CreateHypertable(
            model_name="sensorreading",
            time_column="time",
            chunk_time_interval="1 day",
            if_not_exists=True,
        ),
        timescale_migrations.AddRetentionPolicy(
            model_name="sensorreading",
            drop_after="90 days",
        ),
        timescale_migrations.EnableColumnstore(
            model_name="sensorreading",
            orderby="time DESC",
            segmentby="device_id",
        ),
        timescale_migrations.AddColumnstorePolicy(
            model_name="sensorreading",
            after="30 days",
            if_not_exists=True,
        ),
    ]
