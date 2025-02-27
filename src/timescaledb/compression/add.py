from datetime import timedelta
from typing import Type

import sqlalchemy
from sqlmodel import Session, SQLModel

from timescaledb.compression import extractors, sql


def add_compression_policy(
    session: Session,
    model: Type[SQLModel] = None,
    table_name: str = None,
    commit: bool = True,
    compress_after: str | int | timedelta | None = None,
    compress_created_before: timedelta | None = None,
) -> None:
    """
    Add an automatic compression policy to a hypertable

    This function adds a policy that automatically compresses chunks based on age
    or creation time. Note that compression must be enabled on the table first
    using the enable_table_compression function.

    Parameters
    ----------
    session : Session
        SQLAlchemy session
    model : Type[SQLModel], optional
        SQLModel class with compression policy metadata
    table_name : str, optional
        Name of the table to add compression policy to (required if model not provided)
    commit : bool, default=True
        Whether to commit the transaction
    compress_after : str | int | timedelta, optional
        Time interval after which to compress chunks (e.g., '7 days')
    compress_created_before : timedelta, optional
        Compress chunks created before this time interval

    Raises
    ------
    ValueError
        If neither model nor table_name is provided

    Notes
    -----
    At least one of compress_after or compress_created_before must be provided
    to create a meaningful compression policy.
    """
    if all([model is None, table_name is None]):
        raise ValueError("model or table_name is required to add a compression policy")

    to_execute = []

    if model is not None:
        policy_params = extractors.extract_model_compression_policy_params(model)
        compress_enabled = policy_params.get("compress_enabled", False)

        # If compression is not enabled for this model, don't add a policy
        if not compress_enabled:
            return

        actual_table_name = policy_params["table_name"]
        model_compress_after = policy_params.get("compress_after")
        model_compress_created_before = policy_params.get("compress_created_before")

        # Use model parameters if provided, otherwise use function parameters
        effective_compress_after = model_compress_after or compress_after
        effective_compress_created_before = (
            model_compress_created_before or compress_created_before
        )

        if effective_compress_after:
            to_execute.append(
                sql.format_compression_policy_sql_query(
                    table_name=actual_table_name,
                    compress_after=effective_compress_after,
                )
            )

        if effective_compress_created_before:
            to_execute.append(
                sql.format_compression_policy_sql_query(
                    table_name=actual_table_name,
                    compress_created_before=effective_compress_created_before,
                )
            )
    else:
        # Using table_name directly
        if compress_after is not None:
            to_execute.append(
                sql.format_compression_policy_sql_query(
                    table_name=table_name,
                    compress_after=compress_after,
                )
            )

        if compress_created_before is not None:
            to_execute.append(
                sql.format_compression_policy_sql_query(
                    table_name=table_name,
                    compress_created_before=compress_created_before,
                )
            )

    # Execute all SQL statements
    for query in to_execute:
        session.execute(sqlalchemy.text(query))

    if commit and to_execute:
        session.commit()

    # if model is None and table_name is None:
    #     raise ValueError("model or table_name is required to add a compression policy")

    # enable_compression = getattr(model, "__enable_compression__", False)
    # enable_compression_bool = str(enable_compression).lower() == "true"
    # if not enable_compression_bool:
    #     raise ValueError("Compression is not enabled for this model")

    # compress_orderby = getattr(model, "__compress_orderby__", None)
    # valid_orderby = validate_compress_orderby_field(model, compress_orderby)
    # compress_segmentby = getattr(model, "__compress_segmentby__", None)
    # valid_segmentby = validate_compress_segmentby_field(model, compress_segmentby)
    # validate_unique_segmentby_and_orderby_fields(
    #     model, compress_segmentby, compress_orderby
    # )
    # params = {}
    # has_orderby = valid_orderby and compress_orderby is not None
    # has_segmentby = valid_segmentby and compress_segmentby is not None
    # if has_orderby:
    #     params["compress_orderby"] = compress_orderby
    # if has_segmentby:
    #     params["compress_segmentby"] = compress_segmentby

    # sql_template = sql.get_alter_compression_policy_sql(
    #     model.__tablename__, with_orderby=has_orderby, with_segmentby=has_segmentby
    # )

    # query = sqlalchemy.text(sql_template).bindparams(**params)
    # compiled_query = str(query.compile(compile_kwargs={"literal_binds": True}))
    # session.execute(sqlalchemy.text(compiled_query))
    # if commit:
    #   session.commit()
