from typing import Any, Type

from sqlmodel import SQLModel

from timescaledb.compression import validators


def _as_bool(value: Any) -> bool:
    return str(value).lower() == "true"


def extract_model_columnstore_params(model: Type[SQLModel]) -> dict | None:
    enable_columnstore = getattr(model, "__enable_columnstore__", False)
    if not _as_bool(enable_columnstore):
        return None

    orderby = getattr(
        model,
        "__columnstore_orderby__",
        getattr(model, "__compress_orderby__", None),
    )
    segmentby = getattr(
        model,
        "__columnstore_segmentby__",
        getattr(model, "__compress_segmentby__", None),
    )

    valid_orderby = validators.validate_compress_orderby_field(model, orderby)
    valid_segmentby = validators.validate_compress_segmentby_field(model, segmentby)
    validators.validate_unique_segmentby_and_orderby_fields(
        model,
        segmentby,
        orderby,
    )

    params = {
        "table_name": model.__tablename__,
        "columnstore_enabled": True,
    }
    if valid_orderby and orderby is not None:
        params["orderby"] = orderby
    if valid_segmentby and segmentby is not None:
        params["segmentby"] = segmentby
    return params


def extract_model_columnstore_policy_params(model: Type[SQLModel]) -> dict | None:
    columnstore_params = extract_model_columnstore_params(model)
    if columnstore_params is None:
        return None

    columnstore_params.update(
        {
            "after": getattr(model, "__columnstore_after__", None),
            "created_before": getattr(model, "__columnstore_created_before__", None),
            "schedule_interval": getattr(
                model,
                "__columnstore_schedule_interval__",
                None,
            ),
            "timezone": getattr(model, "__columnstore_timezone__", None),
            "if_not_exists": getattr(model, "__columnstore_if_not_exists__", True),
        }
    )
    return columnstore_params
