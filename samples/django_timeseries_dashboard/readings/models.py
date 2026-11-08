from __future__ import annotations

from timescaledb.django.db import models


class SensorReading(models.TimescaleModel):
    # TimescaleDB requires the primary key of a hypertable to include the time
    # column, so Django's implicit ``id`` primary key cannot be used here.
    pk = models.CompositePrimaryKey("device_id", "time")
    time = models.TimescaleDateTimeField(interval="1 hour")
    device_id = models.CharField(max_length=64, db_index=True)
    temperature = models.FloatField()
    humidity = models.FloatField()

    class Meta:
        ordering = ["-time"]
