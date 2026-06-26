from __future__ import annotations

from django.db.models import Avg
from django.http import JsonResponse

from timescaledb.django.db.functions import TimeBucket

from .models import SensorReading


def readings(request):
    rows = SensorReading.objects.order_by("-time")[:100]
    payload = [
        {
            "time": row.time.isoformat(),
            "device_id": row.device_id,
            "temperature": row.temperature,
            "humidity": row.humidity,
        }
        for row in rows
    ]
    return JsonResponse({"readings": payload})


def rollups(request):
    rows = (
        SensorReading.objects.annotate(bucket=TimeBucket("1 hour", "time"))
        .values("bucket")
        .annotate(avg_temperature=Avg("temperature"), avg_humidity=Avg("humidity"))
        .order_by("bucket")[:100]
    )
    payload = [
        {
            "bucket": row["bucket"].isoformat(),
            "avg_temperature": row["avg_temperature"],
            "avg_humidity": row["avg_humidity"],
        }
        for row in rows
    ]
    return JsonResponse({"rollups": payload})
