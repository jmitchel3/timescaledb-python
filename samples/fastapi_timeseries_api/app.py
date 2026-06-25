"""FastAPI application factory wired to a TimescaleDB hypertable.

``create_app(engine)`` builds an app bound to a specific engine, which makes it
trivial to test: the test suite passes a throwaway testcontainers engine, while
``main.py`` passes the real Docker-compose engine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.engine import Engine
from sqlmodel import Session, desc, select

import timescaledb
from samples._shared.db import create_tables, get_engine
from samples.fastapi_timeseries_api.models import (
    BucketOut,
    Reading,
    ReadingIn,
    ReadingOut,
)


def init_db(engine: Engine) -> None:
    create_tables(engine, Reading)
    with Session(engine) as session:
        timescaledb.activate_timescaledb_extension(session)
        timescaledb.create_hypertable(session, model=Reading, commit=True)


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or get_engine()
    init_db(engine)

    app = FastAPI(title="TimescaleDB Time-Series API")

    def get_session():
        with Session(engine) as session:
            yield session

    @app.get("/health")
    def health(session: Session = Depends(get_session)):
        names = [h.hypertable_name for h in timescaledb.list_hypertables(session)]
        return {"status": "ok", "hypertables": names}

    @app.post("/readings", response_model=ReadingOut, status_code=201)
    def create_reading(payload: ReadingIn, session: Session = Depends(get_session)):
        reading = Reading(sensor_id=payload.sensor_id, value=payload.value)
        if payload.time is not None:
            reading.time = payload.time
        session.add(reading)
        session.commit()
        session.refresh(reading)
        return reading

    @app.get("/readings", response_model=list[ReadingOut])
    def list_readings(
        sensor_id: int | None = None,
        limit: int = 100,
        session: Session = Depends(get_session),
    ):
        query = select(Reading)
        if sensor_id is not None:
            query = query.where(Reading.sensor_id == sensor_id)
        query = query.order_by(desc(Reading.time)).limit(limit)
        return session.exec(query).all()

    @app.get("/sensors/{sensor_id}/latest", response_model=ReadingOut)
    def latest_reading(sensor_id: int, session: Session = Depends(get_session)):
        reading = session.exec(
            select(Reading)
            .where(Reading.sensor_id == sensor_id)
            .order_by(desc(Reading.time))
            .limit(1)
        ).first()
        if reading is None:
            raise HTTPException(status_code=404, detail="sensor has no readings")
        return reading

    @app.get("/sensors/{sensor_id}/hourly", response_model=list[BucketOut])
    def hourly_average(
        sensor_id: int,
        interval: str = "1 hour",
        session: Session = Depends(get_session),
    ):
        return timescaledb.time_bucket_query(
            session,
            model=Reading,
            interval=interval,
            time_field="time",
            metric_field="value",
            filters=[Reading.sensor_id == sensor_id],
        )

    return app


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
