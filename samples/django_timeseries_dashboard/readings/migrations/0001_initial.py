from __future__ import annotations

from django.db import migrations
from django.db import models

from timescaledb.django.db import models as timescale_models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SensorReading",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "device_id",
                        "time",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "time",
                    timescale_models.TimescaleDateTimeField(interval="1 hour"),
                ),
                ("device_id", models.CharField(db_index=True, max_length=64)),
                ("temperature", models.FloatField()),
                ("humidity", models.FloatField()),
            ],
            options={"ordering": ["-time"]},
        ),
    ]
