CREATE_HYPERTABLE_SQL_VIA_INTERVAL = """
SELECT create_hypertable(
    :table_name,
    by_range(:time_column, INTERVAL :chunk_time_interval),
    if_not_exists => :if_not_exists,
    migrate_data => :migrate_data
);
"""


CREATE_HYPERTABLE_SQL_VIA_INTEGER = """
SELECT create_hypertable(
    :table_name,
    by_range(:time_column, :chunk_time_interval),
    if_not_exists => :if_not_exists,
    migrate_data => :migrate_data
);
"""


LIST_AVAILABLE_HYPERTABLES_SQL = """
SELECT * FROM timescaledb_information.hypertables;
"""
