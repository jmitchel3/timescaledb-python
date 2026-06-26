from __future__ import annotations

__version__ = "0.0.7"

from . import defaults, metadata
from .activator import activate_timescaledb_extension
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
from .models import TimescaleModel
from .queries import time_bucket_gapfill_query, time_bucket_query
from .retention import add_retention_policy, sync_retention_policies

__all__ = [
    "metadata",
    "TimescaleModel",
    "activate_timescaledb_extension",
    "sync_all_hypertables",
    "create_hypertable",
    "create_table_with_hypertable",
    "format_create_table_with_hypertable_sql",
    "list_hypertables",
    "create_engine",
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
