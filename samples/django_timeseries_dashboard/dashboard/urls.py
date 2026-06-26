from __future__ import annotations

from django.urls import path

from readings import views

urlpatterns = [
    path("readings/", views.readings, name="readings"),
    path("rollups/", views.rollups, name="rollups"),
]
