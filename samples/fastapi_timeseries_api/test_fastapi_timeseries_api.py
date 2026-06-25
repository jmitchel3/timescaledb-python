"""Tests for the FastAPI sample using Starlette's TestClient (httpx)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from samples.fastapi_timeseries_api.app import create_app


@pytest.fixture()
def client(engine):
    app = create_app(engine)
    with TestClient(app) as test_client:
        yield test_client


def test_health_lists_hypertable(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "api_readings" in body["hypertables"]


def test_create_and_list_readings(client):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        resp = client.post(
            "/readings",
            json={
                "sensor_id": 1,
                "value": float(i),
                "time": (base + timedelta(minutes=i)).isoformat(),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["id"] is not None

    listed = client.get("/readings", params={"sensor_id": 1}).json()
    assert len(listed) == 5
    # Ordered newest-first.
    assert listed[0]["value"] == 4.0


def test_latest_endpoint_and_404(client):
    base = datetime(2026, 2, 1, tzinfo=timezone.utc)
    client.post(
        "/readings",
        json={"sensor_id": 7, "value": 42.0, "time": base.isoformat()},
    )
    latest = client.get("/sensors/7/latest")
    assert latest.status_code == 200
    assert latest.json()["value"] == 42.0

    missing = client.get("/sensors/999/latest")
    assert missing.status_code == 404


def test_hourly_bucket_endpoint(client):
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    # Two readings in the same hour -> one bucket whose avg is their mean.
    client.post(
        "/readings",
        json={"sensor_id": 3, "value": 10.0, "time": base.isoformat()},
    )
    client.post(
        "/readings",
        json={
            "sensor_id": 3,
            "value": 20.0,
            "time": (base + timedelta(minutes=10)).isoformat(),
        },
    )
    buckets = client.get("/sensors/3/hourly").json()
    assert len(buckets) == 1
    assert buckets[0]["avg"] == 15.0
