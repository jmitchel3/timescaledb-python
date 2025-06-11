# TimescaleDB for Python

Python Client for TimescaleDB -- an open-source time-series database built on PostgreSQL. This package is based on SQLModel and SQLAlchemy and designed to be used with FastAPI, Flask, and more.

Looking for Django? [Check out django-timescaledb](https://github.com/jamessewell/django-timescaledb)

## Installation

```bash
pip install timescaledb
```

## Quickstart

The timescaledb python package provides helpers for creating hypertables, configuring compression, retention policies, and more.

## Two ways to create a TimescaleDB Model

- Automatically via `TimescaleModel`
- Manually via `create_hypertable` on any table with a `time` column

Let's take a look at the manual way first.


### Manually Create a Hypertable

```python
from sqlmodel import create_engine, Field, SQLModel
import timescaledb

TIMESCALE_DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"
engine = create_engine(TIMESCALE_DATABASE_URL)

class Sensor(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    time: datetime = Field(default=None, primary_key=True)
    sensor_id: int = Field(index=True)
    value: float

    __tablename__ = "my_time_series_table"


hypertable_options = {
    "time_column": "time",
    "compress_orderby": "time DESC",
    "compress_segmentby": "sensor_id",
    "chunk_time_interval": "7 days",
    "drop_after": "1 year",
    "migrate_data": True,
    "if_not_exists": True,
}

# Create the table and the hypertable
with Session(engine) as session:
    # Create the table in the database
    SQLModel.metadata.create_all(engine)
    # Create the hypertable
    table_name="my_time_series_table"
    timescaledb.create_hypertable(
        session, 
        commit=True, 
        table_name=table_name, 
        hypertable_options=hypertable_options
    )

    # Enable compression
    timescaledb.enable_table_compression(
        session, 
        commit=True, 
        table_name=table_name, 
        compress_orderby=hypertable_options.get('compress_orderby'), 
        compress_segmentby=hypertable_options.get('compress_segmentby')
    )
    # Add compression interval policy
    timescaledb.add_compression_policy(
        session, 
        commit=True,
        table_name=table_name, 
        compress_after=hypertable_options.get('chunk_time_interval')
    )
    # Add retention policy
    timescaledb.add_retention_policy(
        session, 
        table_name=table_name, 
        drop_after=hypertable_options.get('drop_after')
    )
```


### Automatically via `TimescaleModel`


```python
from sqlmodel import Field

import timescaledb
from timescaledb import create_engine, TimescaleModel

TIMESCALE_DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"
engine = create_engine(TIMESCALE_DATABASE_URL, timezone="UTC")

class SensorDos(TimescaleModel, table=True):
    sensor_id: int = Field(index=True)
    value: float
    
    # __time_column__ = "time" # set in TimescaleModel
    __chunk_time_interval__ = "INTERVAL 7 days"
    __drop_after__ = "INTERVAL 1 year"
    __enable_compression__ = True
    __compress_orderby__ = "time DESC"
    __compress_segmentby__ = "sensor_id"  
    __migrate_data__ = True
    __if_not_exists__ = True


# Create the table and the hypertable
with Session(engine) as session:
    # Create the table in the database
    SQLModel.metadata.create_all(engine)
    # Creates all hypertable, add compression policies, and add retention policy
    timescaledb.metadata.create_all(engine)
```



## Used by

- [analytics-api](https://github.com/codingforentrepreneurs/analytics-api) - Complete tutorial project for building an Analytics API using FastAPI + TimescaleDB


## Sample Usage 

Below is a sample of using `timescaledb` in a FastAPI app much like the example in [./sample_project](./sample_project).

`src/models.py`
```python
from sqlmodel import Field, SQLModel

from timescaledb import TimescaleModel

# create a model
class Metric(TimescaleModel, table=True):
    temp: float

    __enable_compression__ = True
    __chunk_time_interval__ = "2 weeks"
    __drop_after__ = "1 year"


class MetricCreate(Metric):
    # not a table but a Pydantic model
    temp: float


class MetricRead(Metric):
    # not a table but a Pydantic model
    id: int
    temp: float
    time: datetime = Field(default=None)
```


### Initialize the Database

The `timescaledb.create_engine` is a wrapper around `sqlmodel.create_engine` (which is a wrapper around `sqlalchemy.create_engine`) that ensures a timezone is set for your database. 

`src/database.py`
```python
import timescaledb
from sqlmodel import Session, SQLModel

DATABASE_URL = "postgresql://user:password@localhost:5432/timescaledb"
TIME_ZONE = "UTC"
ECHO_QUERIES = False

engine = timescaledb.create_engine(DATABASE_URL, timezone=TIME_ZONE, echo=ECHO_QUERIES)


def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    # Create all tables
    print("Creating database tables...")
    # automatically creates all tables that inherit from SQLModel
    SQLModel.metadata.create_all(engine)

    print("Creating hypertables...")
    # automatically creates hypertables for all models that inherit from TimescaleModel
    timescaledb.metadata.create_all(engine)

```


### Create a FastAPI App

Put it all together in a FastAPI app.

`src/main.py`
```python
from fastapi import FastAPI

from .database import init_db, get_session
from .models import Metric, MetricCreate, MetricRead

app = FastAPI()

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/metrics/", response_model=MetricRead)
def create_metric(metric: MetricCreate, session: Session = Depends(get_session)):
    db_metric = models.Metric.from_orm(metric)
    session.add(db_metric)
    session.commit()
    session.refresh(db_metric)
    return db_metric


@app.get("/metrics/{metric_id}", response_model=MetricRead)
def read_metric(metric_id: int, session: Session = Depends(get_session)):
    metric = session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, message="Metric not found")
    return metric


@app.get("/metrics/", response_model=list[MetricRead])
def list_metrics(session: Session = Depends(get_session)):
    metrics = session.query(Metric).all()
    return metrics
```

