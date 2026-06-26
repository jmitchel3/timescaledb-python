# Django Timeseries Dashboard Sample

This sample shows the first-party Django integration in `timescaledb`.

## Setup

```bash
pip install "timescaledb[django]" "psycopg[binary]"
createdb django_timeseries_dashboard
```

Configure PostgreSQL with environment variables if you are not using the local
defaults:

```bash
export POSTGRES_DB=django_timeseries_dashboard
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

## Run

```bash
cd samples/django_timeseries_dashboard
python manage.py migrate
python manage.py seed_readings
python manage.py runserver
```

Endpoints:

- `GET /readings/` returns recent raw readings.
- `GET /rollups/` returns hourly average temperature rollups using
  `TimeBucket`.
