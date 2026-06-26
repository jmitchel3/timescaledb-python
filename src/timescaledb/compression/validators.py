from typing import Type

import sqlalchemy
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

from timescaledb import exceptions


def validate_compress_segmentby_field(
    model: Type[SQLModel], segmentby_field: str = None
) -> bool:
    """
    Verify if the specified field is a valid segmentby field.
    Valid types include String, Integer, Boolean, and other scalar types.
    Arrays and JSON types are not supported for segmentby.

    Column list on which to key the compressed segments.
    An identifier representing the source of the data such as device_id or tags_id is usually a good candidate.
    The default is no segment by columns.
    """
    if segmentby_field is None:
        return True
    column = model.__table__.columns.get(segmentby_field)
    if column is None:
        raise exceptions.InvalidSegmentByField(
            f"Field '{segmentby_field}' not found in model {model.__name__}"
        )

    # Types that are valid for segmentby
    valid_types = (
        AutoString,
        sqlalchemy.String,
        sqlalchemy.Integer,
        sqlalchemy.SmallInteger,
        sqlalchemy.BigInteger,
        sqlalchemy.Boolean,
        sqlalchemy.Date,
        sqlalchemy.DateTime,
        sqlalchemy.Enum,
        sqlalchemy.Float,
        sqlalchemy.Numeric,
    )

    column_type = type(column.type)
    if not issubclass(column_type, valid_types):
        raise exceptions.InvalidSegmentByField(
            f"Field '{segmentby_field}' in model {model.__name__} has invalid type {column_type.__name__}. "
            f"Must be one of: {', '.join(t.__name__ for t in valid_types)}"
        )

    return True


def validate_compress_orderby_field(
    model: Type[SQLModel], orderby_field: str = None
) -> bool:
    """
    Order used by compression, specified in the same way as the ORDER BY clause in a SELECT query.
    The default is the descending order of the hypertable's time column.

    orderby_field: format is '<column_name> [ASC | DESC] [ NULLS { FIRST | LAST } ] [, ...]',
    """
    if orderby_field is None:
        return True
    # Split on commas to handle multiple orderby fields
    for field_spec in orderby_field.split(","):
        field_spec = field_spec.strip()
        orderby_parts = field_spec.split()

        if not orderby_parts:
            raise exceptions.InvalidOrderByField("Empty orderby field specification")

        orderby_column_name = orderby_parts[0]
        column = model.__table__.columns.get(orderby_column_name)
        if column is None:
            raise exceptions.InvalidOrderByField(
                f"Field '{orderby_column_name}' not found in model {model.__name__}"
            )

        # Types that are not valid for orderby
        invalid_types = (
            sqlalchemy.JSON,
            sqlalchemy.ARRAY,
            sqlalchemy.PickleType,
        )

        column_type = type(column.type)
        if issubclass(column_type, invalid_types):
            raise exceptions.InvalidOrderByField(
                f"Field '{orderby_column_name}' in model {model.__name__} has invalid type {column_type.__name__}. "
                "JSON, ARRAY, and PickleType are not supported for orderby fields"
            )

        # Validate direction if specified
        if len(orderby_parts) > 1:
            direction = orderby_parts[1].upper()
            if direction not in ("ASC", "DESC"):
                raise exceptions.InvalidOrderByField(
                    f"Invalid direction '{direction}' in orderby field '{field_spec}'. "
                    "Must be one of: ASC, DESC"
                )

            # Validate NULLS FIRST/LAST if specified
            if len(orderby_parts) > 2:
                if len(orderby_parts) < 4:
                    raise exceptions.InvalidOrderByField(
                        f"Invalid NULLS specification in '{field_spec}'. "
                        "Must be 'NULLS FIRST' or 'NULLS LAST'"
                    )
                nulls_keyword = orderby_parts[2].upper()
                nulls_position = orderby_parts[3].upper()
                if nulls_keyword != "NULLS" or nulls_position not in ("FIRST", "LAST"):
                    raise exceptions.InvalidOrderByField(
                        f"Invalid NULLS specification in '{field_spec}'. "
                        "Must be 'NULLS FIRST' or 'NULLS LAST'"
                    )

    return True


def validate_unique_segmentby_and_orderby_fields(
    model: Type[SQLModel], segmentby_field: str = None, orderby_field: str = None
) -> bool:
    """
    Validate that the segmentby and orderby fields are unique.
    """
    if segmentby_field is None or orderby_field is None:
        return True
    orderby_fields = orderby_field.split(" ")
    orderby_column = orderby_fields[0]
    if orderby_column == segmentby_field:
        raise exceptions.InvalidCompressionFields(
            "Segmentby and orderby fields must be different"
        )
    return True
