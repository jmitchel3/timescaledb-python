from __future__ import annotations

from timescaledb.django.db import models


class SensorReading(models.TimescaleModel):
    time = models.TimescaleDateTimeField(interval="1 hour")
    device_id = models.CharField(max_length=64, db_index=True)
    temperature = models.FloatField()
    humidity = models.FloatField()

    class Meta:
        ordering = ["-time"]
