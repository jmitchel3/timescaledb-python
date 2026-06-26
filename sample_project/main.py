from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from app import models
from app.database import get_session, init_db
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, desc, select

from timescaledb import list_hypertables
from timescaledb.queries import time_bucket_gapfill_query


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FastAPI SQLModel Demo", lifespan=lifespan)


@app.get("/")
def root(session: Session = Depends(get_session)):
    hypertables = list_hypertables(session)
    return {
        "message": "Hello World",
        "hypertables": [hypertable.model_dump() for hypertable in hypertables],
    }


@app.post("/metrics/", response_model=models.MetricRead)
def create_metric(metric: models.MetricCreate, session: Session = Depends(get_session)):
    db_metric = models.Metric.model_validate(metric)
    session.add(db_metric)
    session.commit()
    session.refresh(db_metric)
    return db_metric


@app.get("/metrics/{metric_id}", response_model=models.MetricRead)
def read_metric(metric_id: int, session: Session = Depends(get_session)):
    metric = session.get(models.Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    return metric


@app.get("/metrics/", response_model=list[models.MetricRead])
def list_metrics(session: Session = Depends(get_session)):
    metrics = session.exec(select(models.Metric)).all()
    return metrics


@app.get("/metrics/buckets/", response_model=list[dict])
def get_metric_buckets(
    interval: str = "1 hour", session: Session = Depends(get_session)
):
    """Get metrics aggregated into time buckets"""
    latest_metric = session.exec(
        select(models.Metric).order_by(desc(models.Metric.time))
    ).first()

    if not latest_metric:
        return []
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    raw_results = time_bucket_gapfill_query(
        session=session,
        model=models.Metric,
        time_field="time",
        metric_field="temp",
        interval=interval,
        use_interpolate=True,
        use_locf=False,
        start=start_time,
        finish=end_time,
    )
    return raw_results
