from __future__ import annotations

__version__ = "0.2.1"

from . import defaults, metadata
from .activator import activate_timescaledb_extension
from .chunks import drop_chunks, show_chunks
from .compression import (
    add_compression_policy,
    enable_table_compression,
    sync_compression_policies,
)
from .continuous_aggregates import (
    add_continuous_aggregate_policy,
    add_generated_aggregate_column,
    create_continuous_aggregate,
    refresh_continuous_aggregate,
    remove_continuous_aggregate_policy,
)
from .defaults import get_defaults
from .engine import create_engine
from .hypercore import (
    add_columnstore_policy,
    convert_to_columnstore,
    convert_to_rowstore,
    enable_columnstore,
    list_columnstore_policies,
    remove_columnstore_policy,
    sync_columnstore_policies,
)
from .hypertables import (
    create_hypertable,
    create_table_with_hypertable,
    format_create_table_with_hypertable_sql,
    list_hypertables,
    sync_all_hypertables,
)
from .jobs import (
    alter_job,
    delete_job,
    get_job_stats,
    list_jobs,
    run_job,
)
from .models import TimescaleModel
from .queries import time_bucket_gapfill_query, time_bucket_query
from .retention import add_retention_policy, sync_retention_policies

__all__ = [
    "metadata",
    "TimescaleModel",
    "activate_timescaledb_extension",
    "sync_all_hypertables",
    "create_hypertable",
    "show_chunks",
    "drop_chunks",
    "create_table_with_hypertable",
    "format_create_table_with_hypertable_sql",
    "list_hypertables",
    "create_engine",
    "list_jobs",
    "get_job_stats",
    "run_job",
    "alter_job",
    "delete_job",
    "time_bucket_query",
    "time_bucket_gapfill_query",
    "defaults",
    "get_defaults",
    "add_retention_policy",
    "sync_retention_policies",
    "add_compression_policy",
    "enable_table_compression",
    "sync_compression_policies",
    "add_continuous_aggregate_policy",
    "add_generated_aggregate_column",
    "create_continuous_aggregate",
    "refresh_continuous_aggregate",
    "remove_continuous_aggregate_policy",
    "add_columnstore_policy",
    "convert_to_columnstore",
    "convert_to_rowstore",
    "enable_columnstore",
    "list_columnstore_policies",
    "remove_columnstore_policy",
    "sync_columnstore_policies",
]
