from typing import Optional, Type

from sqlmodel import SQLModel


def resolve_table_name(
    table_name: Optional[str] = None,
    model: Optional[Type[SQLModel]] = None,
) -> str:
    """
    Resolve a target hypertable name from either an explicit ``table_name`` or a
    SQLModel ``model`` class, mirroring the calling convention used elsewhere in
    the package (e.g. ``add_retention_policy``).
    """
    if model is not None:
        return str(model.__tablename__)
    if table_name is not None:
        return table_name
    raise ValueError("table_name or model is required")
