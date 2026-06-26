from __future__ import annotations

TIME_COLUMN = "time"
CHUNK_TIME_INTERVAL = "INTERVAL 7 days"
COMPRESS_SEGMENTBY = "identifier"
COMPRESS_AFTER = "INTERVAL 7 days"
COMPRESS_ORDERBY = "time DESC"
DROP_AFTER = "INTERVAL 3 months"


def get_defaults() -> dict[str, str]:
    """Return the current TimescaleDB default settings as a dict.

    Maps each default setting name to its current value. Useful for
    inspecting the values that hypertable, compression, and retention
    helpers fall back to when an explicit argument is not provided.
    """
    return {
        "TIME_COLUMN": TIME_COLUMN,
        "CHUNK_TIME_INTERVAL": CHUNK_TIME_INTERVAL,
        "COMPRESS_SEGMENTBY": COMPRESS_SEGMENTBY,
        "COMPRESS_AFTER": COMPRESS_AFTER,
        "COMPRESS_ORDERBY": COMPRESS_ORDERBY,
        "DROP_AFTER": DROP_AFTER,
    }
