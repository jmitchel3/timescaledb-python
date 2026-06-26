from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from readings.models import SensorReading


class Command(BaseCommand):
    help = "Seed deterministic sensor readings for the dashboard sample."

    def handle(self, *args, **options):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        readings = []
        for hour in range(72):
            for device_index in range(3):
                readings.append(
                    SensorReading(
                        time=now - timedelta(hours=hour),
                        device_id=f"sensor-{device_index + 1}",
                        temperature=68.0 + device_index + (hour % 8) * 0.5,
                        humidity=40.0 + device_index * 2 + (hour % 6),
                    )
                )

        SensorReading.objects.bulk_create(readings, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(readings)} readings."))
