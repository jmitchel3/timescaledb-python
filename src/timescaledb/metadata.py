from sqlalchemy.engine import Engine
from sqlmodel import Session

from timescaledb.activator import activate_timescaledb_extension
from timescaledb.compression import sync_compression_policies
from timescaledb.hypercore import sync_columnstore_policies
from timescaledb.hypertables import sync_all_hypertables
from timescaledb.retention import sync_retention_policies


def create_all(engine: Engine) -> None:
    with Session(engine) as session:
        activate_timescaledb_extension(session)
        sync_all_hypertables(session)
        sync_compression_policies(session)
        sync_columnstore_policies(session)
        sync_retention_policies(session, drop_after="1 day")
