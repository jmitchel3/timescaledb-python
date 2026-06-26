from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import sqlalchemy

# The ordered set of time-range arguments accepted by TimescaleDB's
# ``show_chunks`` / ``drop_chunks`` functions. ``older_than`` / ``newer_than``
# have been available since the 1.x line; ``created_before`` / ``created_after``
# were added in TimescaleDB 2.8.
CHUNK_RANGE_ARGS = (
    "older_than",
    "newer_than",
    "created_before",
    "created_after",
)


def _render_chunk_arg(name: str, value: Any) -> Tuple[str, Dict[str, Any]]:
    """
    Render a single ``show_chunks``/``drop_chunks`` range argument.

    The argument type is driven by the Python type so callers never need a
    separate "is this a timestamp?" flag:

    * ``datetime`` / ``date`` -> a ``timestamptz`` literal
    * ``timedelta``           -> an ``INTERVAL``
    * ``int``                 -> a ``BIGINT`` (for integer-partitioned hypertables)
    * ``str``                 -> an ``INTERVAL`` literal (e.g. ``"3 days"``)

    Returns a tuple of ``(sql_fragment, bind_params)``.
    """
    if isinstance(value, (datetime, date)):
        return f"{name} => CAST(:{name} AS timestamptz)", {name: value.isoformat()}
    if isinstance(value, timedelta):
        return (
            f"{name} => make_interval(secs => :{name})",
            {name: value.total_seconds()},
        )
    # ``bool`` is a subclass of ``int`` but is never a meaningful chunk bound.
    if isinstance(value, bool):
        raise ValueError(f"{name} cannot be a boolean")
    if isinstance(value, int):
        if name in {"created_before", "created_after"}:
            raise ValueError(
                f"{name} does not support integer bounds. "
                "Use a datetime/date, timedelta, or interval string."
            )
        return f"{name} => :{name}", {name: value}
    if isinstance(value, str):
        cleaned = value.replace("INTERVAL", "").strip().replace("'", "").replace('"', "")
        return f"{name} => INTERVAL :{name}", {name: cleaned}
    raise ValueError(
        f"Unsupported type for {name}: {type(value).__name__}. "
        "Use a datetime/date, timedelta, int, or interval string."
    )


def _format_chunks_sql(
    func_name: str,
    table_name: str,
    older_than: Optional[Any] = None,
    newer_than: Optional[Any] = None,
    created_before: Optional[Any] = None,
    created_after: Optional[Any] = None,
    require_range: bool = False,
) -> str:
    """
    Build a fully-bound ``SELECT <func_name>(...)`` statement for chunk
    introspection/removal.
    """
    if not table_name:
        raise ValueError("table_name is required")

    provided = {
        "older_than": older_than,
        "newer_than": newer_than,
        "created_before": created_before,
        "created_after": created_after,
    }
    provided = {key: value for key, value in provided.items() if value is not None}

    if require_range and not provided:
        raise ValueError(
            f"{func_name} requires at least one of: {', '.join(CHUNK_RANGE_ARGS)}"
        )

    fragments = [":relation"]
    params: Dict[str, Any] = {"relation": table_name}
    for key in CHUNK_RANGE_ARGS:
        if key in provided:
            fragment, fragment_params = _render_chunk_arg(key, provided[key])
            fragments.append(fragment)
            params.update(fragment_params)

    sql = f"SELECT {func_name}({', '.join(fragments)});"
    query = sqlalchemy.text(sql).bindparams(**params)
    return str(query.compile(compile_kwargs={"literal_binds": True}))


def format_show_chunks_sql(
    table_name: str,
    older_than: Optional[Any] = None,
    newer_than: Optional[Any] = None,
    created_before: Optional[Any] = None,
    created_after: Optional[Any] = None,
) -> str:
    """Format a ``SELECT show_chunks(...)`` statement."""
    return _format_chunks_sql(
        "show_chunks",
        table_name,
        older_than=older_than,
        newer_than=newer_than,
        created_before=created_before,
        created_after=created_after,
        require_range=False,
    )


def format_drop_chunks_sql(
    table_name: str,
    older_than: Optional[Any] = None,
    newer_than: Optional[Any] = None,
    created_before: Optional[Any] = None,
    created_after: Optional[Any] = None,
) -> str:
    """
    Format a ``SELECT drop_chunks(...)`` statement.

    ``drop_chunks`` always requires a range bound so that callers cannot
    accidentally drop every chunk in a hypertable.
    """
    return _format_chunks_sql(
        "drop_chunks",
        table_name,
        older_than=older_than,
        newer_than=newer_than,
        created_before=created_before,
        created_after=created_after,
        require_range=True,
    )
