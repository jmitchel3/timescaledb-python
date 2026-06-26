from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import sqlalchemy
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.operations.base import Operation
from sqlalchemy.dialects import postgresql

from timescaledb.compression.sql import format_compression_policy_sql_query
from timescaledb.continuous_aggregates.sql import (
    format_add_continuous_aggregate_policy_sql_query,
)
from timescaledb.continuous_aggregates.sql import format_add_generated_aggregate_column_sql
from timescaledb.continuous_aggregates.sql import format_create_continuous_aggregate_sql
from timescaledb.continuous_aggregates.sql import (
    format_refresh_continuous_aggregate_sql_query,
)
from timescaledb.continuous_aggregates.sql import (
    format_remove_continuous_aggregate_policy_sql_query,
)
from timescaledb.hypercore.sql import format_add_columnstore_policy_sql_query
from timescaledb.hypercore.sql import format_enable_columnstore_sql
from timescaledb.hypercore.sql import format_remove_columnstore_policy_sql_query
from timescaledb.hypercore.sql import quote_qualified_identifier
from timescaledb.hypertables.schemas import HypertableCreateSchema
from timescaledb.retention.sql import format_retention_policy_sql_query
from timescaledb.retention.sql import get_drop_retention_policy_sql_query

_POSTGRES_DIALECT = postgresql.dialect()
_IDENTIFIER_PREPARER = _POSTGRES_DIALECT.identifier_preparer


def _compile_sql(sql_template: str, params: dict[str, Any] | None = None) -> str:
    query = sqlalchemy.text(sql_template)
    if params:
        query = query.bindparams(**params)
    return str(
        query.compile(
            dialect=_POSTGRES_DIALECT,
            compile_kwargs={"literal_binds": True},
        )
    )


def _quote_identifier(identifier: str) -> str:
    return _IDENTIFIER_PREPARER.quote_identifier(identifier)


def _extension_identifier(extension_name: str) -> str:
    if not extension_name or not extension_name.replace("_", "").isalnum():
        raise ValueError("extension_name must be an unqualified PostgreSQL identifier")
    return extension_name


def _drop_relation_sql(
    relation_kind: str,
    relation_name: str,
    *,
    if_exists: bool = True,
    cascade: bool = True,
) -> str:
    if_exists_sql = " IF EXISTS" if if_exists else ""
    cascade_sql = " CASCADE" if cascade else ""
    quoted_name = quote_qualified_identifier(relation_name)
    return f"DROP {relation_kind}{if_exists_sql} {quoted_name}{cascade_sql};"


def _drop_column_sql(
    relation_kind: str,
    relation_name: str,
    column_name: str,
    *,
    if_exists: bool = True,
    cascade: bool = False,
) -> str:
    if_exists_sql = " IF EXISTS" if if_exists else ""
    cascade_sql = " CASCADE" if cascade else ""
    quoted_relation = quote_qualified_identifier(relation_name)
    quoted_column = _quote_identifier(column_name)
    return (
        f"ALTER {relation_kind} {quoted_relation} "
        f"DROP COLUMN{if_exists_sql} {quoted_column}{cascade_sql};"
    )


def _remove_compression_policy_sql(table_name: str, if_exists: bool = True) -> str:
    return _compile_sql(
        """
SELECT remove_compression_policy(
    :hypertable_name,
    if_exists => :if_exists
);
""",
        {"hypertable_name": table_name, "if_exists": if_exists},
    )


def _enable_compression_sql(
    table_name: str,
    compress_orderby: str | None = None,
    compress_segmentby: str | None = None,
) -> str:
    clauses = ["timescaledb.compress"]
    params: dict[str, str] = {}
    if compress_orderby is not None:
        clauses.append("timescaledb.compress_orderby = :compress_orderby")
        params["compress_orderby"] = compress_orderby
    if compress_segmentby is not None:
        clauses.append("timescaledb.compress_segmentby = :compress_segmentby")
        params["compress_segmentby"] = compress_segmentby
    return _compile_sql(
        f"""
ALTER TABLE {quote_qualified_identifier(table_name)} SET (
    {", ".join(clauses)}
);
""",
        params,
    )


class _TimescaleOperation(Operation):
    reduces_to_sql = True
    serialization_attrs: tuple[str, ...] = ()

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        kwargs = {name: getattr(self, name) for name in self.serialization_attrs}
        return self.__class__.__name__, [], kwargs

    def state_forwards(self, app_label: str, state: Any) -> None:
        return None


class _ModelTableOperation(_TimescaleOperation):
    model_name: str | None
    table_name: str | None

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
    ) -> None:
        if model_name is None and table_name is None:
            raise ValueError("model_name or table_name is required")
        self.model_name = model_name
        self.table_name = table_name

    def _resolve_table_name(self, app_label: str, state: Any) -> str:
        if self.table_name is not None:
            return self.table_name
        if self.model_name is None:
            raise ValueError("model_name or table_name is required")
        model = state.apps.get_model(app_label, self.model_name)
        return model._meta.db_table


class CreateExtension(_TimescaleOperation):
    serialization_attrs = ("extension_name", "if_not_exists")

    def __init__(
        self,
        extension_name: str = "timescaledb",
        *,
        if_not_exists: bool = True,
    ) -> None:
        self.extension_name = extension_name
        self.if_not_exists = if_not_exists

    @property
    def migration_name_fragment(self) -> str:
        return f"create_{self.extension_name}_extension"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        if_not_exists = " IF NOT EXISTS" if self.if_not_exists else ""
        extension_name = _extension_identifier(self.extension_name)
        schema_editor.execute(f"CREATE EXTENSION{if_not_exists} {extension_name};")

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        extension_name = _extension_identifier(self.extension_name)
        schema_editor.execute(f"DROP EXTENSION IF EXISTS {extension_name};")

    def describe(self) -> str:
        return f"Creates the {self.extension_name} extension"


class CreateHypertable(_ModelTableOperation):
    reversible = False
    serialization_attrs = (
        "model_name",
        "table_name",
        "time_column",
        "chunk_time_interval",
        "if_not_exists",
        "migrate_data",
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        time_column: str = "time",
        chunk_time_interval: str | int | timedelta = "1 day",
        if_not_exists: bool = False,
        migrate_data: bool = False,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.time_column = time_column
        self.chunk_time_interval = chunk_time_interval
        self.if_not_exists = if_not_exists
        self.migrate_data = migrate_data

    @property
    def migration_name_fragment(self) -> str:
        return "create_hypertable"

    def _sql(self, app_label: str, state: Any) -> str:
        table_name = self._resolve_table_name(app_label, state)
        return HypertableCreateSchema(
            table_name=table_name,
            time_column=self.time_column,
            chunk_time_interval=self.chunk_time_interval,
            if_not_exists=self.if_not_exists,
            migrate_data=self.migrate_data,
        ).to_sql_query()

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(self._sql(app_label, to_state))

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        raise IrreversibleError("CreateHypertable cannot be reversed safely")

    def describe(self) -> str:
        return "Creates a TimescaleDB hypertable"


class DropHypertable(_ModelTableOperation):
    reversible = False
    serialization_attrs = ("model_name", "table_name", "if_exists", "cascade")

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        if_exists: bool = True,
        cascade: bool = True,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.if_exists = if_exists
        self.cascade = cascade

    @property
    def migration_name_fragment(self) -> str:
        return "drop_hypertable"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(
            _drop_relation_sql(
                "TABLE",
                table_name,
                if_exists=self.if_exists,
                cascade=self.cascade,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        raise IrreversibleError("DropHypertable cannot be reversed safely")

    def describe(self) -> str:
        return "Drops a TimescaleDB hypertable"


class AddRetentionPolicy(_ModelTableOperation):
    serialization_attrs = ("model_name", "table_name", "drop_after")

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        drop_after: str | int | timedelta,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.drop_after = drop_after

    @property
    def migration_name_fragment(self) -> str:
        return "add_retention_policy"

    def _sql(self, app_label: str, state: Any) -> str:
        table_name = self._resolve_table_name(app_label, state)
        return format_retention_policy_sql_query(table_name, self.drop_after)

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(self._sql(app_label, to_state))

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(get_drop_retention_policy_sql_query(table_name))

    def describe(self) -> str:
        return "Adds a TimescaleDB retention policy"


class RemoveRetentionPolicy(_ModelTableOperation):
    serialization_attrs = ("model_name", "table_name", "drop_after")

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        drop_after: str | int | timedelta | None = None,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.drop_after = drop_after

    @property
    def migration_name_fragment(self) -> str:
        return "remove_retention_policy"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(get_drop_retention_policy_sql_query(table_name))

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        if self.drop_after is None:
            raise IrreversibleError("drop_after is required to reverse this operation")
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(format_retention_policy_sql_query(table_name, self.drop_after))

    def describe(self) -> str:
        return "Removes a TimescaleDB retention policy"


class EnableCompression(_ModelTableOperation):
    reversible = False
    serialization_attrs = (
        "model_name",
        "table_name",
        "compress_orderby",
        "compress_segmentby",
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        compress_orderby: str | None = None,
        compress_segmentby: str | None = None,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.compress_orderby = compress_orderby
        self.compress_segmentby = compress_segmentby

    @property
    def migration_name_fragment(self) -> str:
        return "enable_compression"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(
            _enable_compression_sql(
                table_name,
                compress_orderby=self.compress_orderby,
                compress_segmentby=self.compress_segmentby,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        raise IrreversibleError("EnableCompression cannot be reversed safely")

    def describe(self) -> str:
        return "Enables TimescaleDB compression"


class AddCompressionPolicy(_ModelTableOperation):
    serialization_attrs = (
        "model_name",
        "table_name",
        "compress_after",
        "compress_created_before",
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        compress_after: str | int | timedelta | None = None,
        compress_created_before: timedelta | None = None,
    ) -> None:
        if compress_after is None and compress_created_before is None:
            raise ValueError("compress_after or compress_created_before is required")
        if compress_after is not None and compress_created_before is not None:
            raise ValueError(
                "only one of compress_after or compress_created_before is allowed"
            )
        super().__init__(model_name, table_name=table_name)
        self.compress_after = compress_after
        self.compress_created_before = compress_created_before

    @property
    def migration_name_fragment(self) -> str:
        return "add_compression_policy"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(
            format_compression_policy_sql_query(
                table_name,
                compress_after=self.compress_after,
                compress_created_before=self.compress_created_before,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(_remove_compression_policy_sql(table_name))

    def describe(self) -> str:
        return "Adds a TimescaleDB compression policy"


class RemoveCompressionPolicy(_ModelTableOperation):
    serialization_attrs = ("model_name", "table_name", "if_exists", "compress_after")

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        if_exists: bool = True,
        compress_after: str | int | timedelta | None = None,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.if_exists = if_exists
        self.compress_after = compress_after

    @property
    def migration_name_fragment(self) -> str:
        return "remove_compression_policy"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(_remove_compression_policy_sql(table_name, self.if_exists))

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        if self.compress_after is None:
            raise IrreversibleError(
                "compress_after is required to reverse this operation"
            )
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(
            format_compression_policy_sql_query(table_name, compress_after=self.compress_after)
        )

    def describe(self) -> str:
        return "Removes a TimescaleDB compression policy"


class EnableColumnstore(_ModelTableOperation):
    reversible = False
    serialization_attrs = ("model_name", "table_name", "orderby", "segmentby")

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        orderby: str | None = None,
        segmentby: str | None = None,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.orderby = orderby
        self.segmentby = segmentby

    @property
    def migration_name_fragment(self) -> str:
        return "enable_columnstore"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(
            format_enable_columnstore_sql(
                table_name,
                orderby=self.orderby,
                segmentby=self.segmentby,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        raise IrreversibleError("EnableColumnstore cannot be reversed safely")

    def describe(self) -> str:
        return "Enables TimescaleDB Hypercore columnstore"


class AddColumnstorePolicy(_ModelTableOperation):
    serialization_attrs = (
        "model_name",
        "table_name",
        "after",
        "created_before",
        "schedule_interval",
        "initial_start",
        "timezone",
        "if_not_exists",
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        after: str | int | timedelta | None = None,
        created_before: str | timedelta | None = None,
        schedule_interval: str | timedelta | None = None,
        initial_start: Any = None,
        timezone: str | None = None,
        if_not_exists: bool = False,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.after = after
        self.created_before = created_before
        self.schedule_interval = schedule_interval
        self.initial_start = initial_start
        self.timezone = timezone
        self.if_not_exists = if_not_exists

    @property
    def migration_name_fragment(self) -> str:
        return "add_columnstore_policy"

    def _sql(self, app_label: str, state: Any) -> str:
        table_name = self._resolve_table_name(app_label, state)
        return format_add_columnstore_policy_sql_query(
            table_name,
            after=self.after,
            created_before=self.created_before,
            schedule_interval=self.schedule_interval,
            initial_start=self.initial_start,
            timezone=self.timezone,
            if_not_exists=self.if_not_exists,
        )

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(self._sql(app_label, to_state))

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(format_remove_columnstore_policy_sql_query(table_name))

    def describe(self) -> str:
        return "Adds a TimescaleDB columnstore policy"


class RemoveColumnstorePolicy(_ModelTableOperation):
    serialization_attrs = (
        "model_name",
        "table_name",
        "if_exists",
        "after",
        "created_before",
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        table_name: str | None = None,
        if_exists: bool = True,
        after: str | int | timedelta | None = None,
        created_before: str | timedelta | None = None,
    ) -> None:
        super().__init__(model_name, table_name=table_name)
        self.if_exists = if_exists
        self.after = after
        self.created_before = created_before

    @property
    def migration_name_fragment(self) -> str:
        return "remove_columnstore_policy"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        table_name = self._resolve_table_name(app_label, to_state)
        schema_editor.execute(
            format_remove_columnstore_policy_sql_query(table_name, self.if_exists)
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        if self.after is None and self.created_before is None:
            raise IrreversibleError(
                "after or created_before is required to reverse this operation"
            )
        table_name = self._resolve_table_name(app_label, from_state)
        schema_editor.execute(
            format_add_columnstore_policy_sql_query(
                table_name,
                after=self.after,
                created_before=self.created_before,
            )
        )

    def describe(self) -> str:
        return "Removes a TimescaleDB columnstore policy"


class CreateContinuousAggregate(_TimescaleOperation):
    serialization_attrs = (
        "view_name",
        "select_query",
        "column_names",
        "chunk_interval",
        "create_group_indexes",
        "finalized",
        "materialized_only",
        "invalidate_using",
        "with_data",
    )

    def __init__(
        self,
        view_name: str,
        select_query: str,
        *,
        column_names: list[str] | tuple[str, ...] | None = None,
        chunk_interval: str | timedelta | None = None,
        create_group_indexes: bool | None = None,
        finalized: bool | None = None,
        materialized_only: bool | None = None,
        invalidate_using: str | None = None,
        with_data: bool = True,
    ) -> None:
        self.view_name = view_name
        self.select_query = select_query
        self.column_names = column_names
        self.chunk_interval = chunk_interval
        self.create_group_indexes = create_group_indexes
        self.finalized = finalized
        self.materialized_only = materialized_only
        self.invalidate_using = invalidate_using
        self.with_data = with_data

    @property
    def migration_name_fragment(self) -> str:
        return "create_continuous_aggregate"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            format_create_continuous_aggregate_sql(
                self.view_name,
                self.select_query,
                column_names=self.column_names,
                chunk_interval=self.chunk_interval,
                create_group_indexes=self.create_group_indexes,
                finalized=self.finalized,
                materialized_only=self.materialized_only,
                invalidate_using=self.invalidate_using,
                with_data=self.with_data,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            _drop_relation_sql("MATERIALIZED VIEW", self.view_name, cascade=True)
        )

    def describe(self) -> str:
        return "Creates a TimescaleDB continuous aggregate"


class AddGeneratedAggregateColumn(_TimescaleOperation):
    serialization_attrs = (
        "continuous_aggregate",
        "column_name",
        "data_type",
        "aggregate_expression",
    )

    def __init__(
        self,
        continuous_aggregate: str,
        column_name: str,
        data_type: str,
        aggregate_expression: str,
    ) -> None:
        self.continuous_aggregate = continuous_aggregate
        self.column_name = column_name
        self.data_type = data_type
        self.aggregate_expression = aggregate_expression

    @property
    def migration_name_fragment(self) -> str:
        return "add_generated_aggregate_column"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            format_add_generated_aggregate_column_sql(
                self.continuous_aggregate,
                self.column_name,
                self.data_type,
                self.aggregate_expression,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            _drop_column_sql("MATERIALIZED VIEW", self.continuous_aggregate, self.column_name)
        )

    def describe(self) -> str:
        return "Adds a generated aggregate column"


class RefreshContinuousAggregate(_TimescaleOperation):
    reversible = False
    serialization_attrs = (
        "continuous_aggregate",
        "window_start",
        "window_end",
        "force",
        "refresh_newest_first",
    )

    def __init__(
        self,
        continuous_aggregate: str,
        window_start: str | int | date | datetime | timedelta | None = None,
        window_end: str | int | date | datetime | timedelta | None = None,
        *,
        force: bool = False,
        refresh_newest_first: bool | None = None,
    ) -> None:
        self.continuous_aggregate = continuous_aggregate
        self.window_start = window_start
        self.window_end = window_end
        self.force = force
        self.refresh_newest_first = refresh_newest_first

    @property
    def migration_name_fragment(self) -> str:
        return "refresh_continuous_aggregate"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            format_refresh_continuous_aggregate_sql_query(
                self.continuous_aggregate,
                self.window_start,
                self.window_end,
                force=self.force,
                refresh_newest_first=self.refresh_newest_first,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        raise IrreversibleError("RefreshContinuousAggregate cannot be reversed safely")

    def describe(self) -> str:
        return "Refreshes a TimescaleDB continuous aggregate"


class AddContinuousAggregatePolicy(_TimescaleOperation):
    serialization_attrs = (
        "continuous_aggregate",
        "start_offset",
        "end_offset",
        "schedule_interval",
        "initial_start",
        "if_not_exists",
        "timezone",
        "include_tiered_data",
        "buckets_per_batch",
        "max_batches_per_execution",
        "refresh_newest_first",
    )

    def __init__(
        self,
        continuous_aggregate: str,
        *,
        start_offset: str | int | timedelta | None,
        end_offset: str | int | timedelta | None,
        schedule_interval: str | timedelta,
        initial_start: datetime | None = None,
        if_not_exists: bool = False,
        timezone: str | None = None,
        include_tiered_data: bool | None = None,
        buckets_per_batch: int | None = None,
        max_batches_per_execution: int | None = None,
        refresh_newest_first: bool | None = None,
    ) -> None:
        self.continuous_aggregate = continuous_aggregate
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.schedule_interval = schedule_interval
        self.initial_start = initial_start
        self.if_not_exists = if_not_exists
        self.timezone = timezone
        self.include_tiered_data = include_tiered_data
        self.buckets_per_batch = buckets_per_batch
        self.max_batches_per_execution = max_batches_per_execution
        self.refresh_newest_first = refresh_newest_first

    @property
    def migration_name_fragment(self) -> str:
        return "add_continuous_aggregate_policy"

    def _sql(self) -> str:
        return format_add_continuous_aggregate_policy_sql_query(
            self.continuous_aggregate,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            schedule_interval=self.schedule_interval,
            initial_start=self.initial_start,
            if_not_exists=self.if_not_exists,
            timezone=self.timezone,
            include_tiered_data=self.include_tiered_data,
            buckets_per_batch=self.buckets_per_batch,
            max_batches_per_execution=self.max_batches_per_execution,
            refresh_newest_first=self.refresh_newest_first,
        )

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(self._sql())

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            format_remove_continuous_aggregate_policy_sql_query(
                self.continuous_aggregate
            )
        )

    def describe(self) -> str:
        return "Adds a TimescaleDB continuous aggregate policy"


class RemoveContinuousAggregatePolicy(_TimescaleOperation):
    serialization_attrs = (
        "continuous_aggregate",
        "if_exists",
        "start_offset",
        "end_offset",
        "schedule_interval",
    )

    def __init__(
        self,
        continuous_aggregate: str,
        *,
        if_exists: bool = True,
        start_offset: str | int | timedelta | None = None,
        end_offset: str | int | timedelta | None = None,
        schedule_interval: str | timedelta | None = None,
    ) -> None:
        self.continuous_aggregate = continuous_aggregate
        self.if_exists = if_exists
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.schedule_interval = schedule_interval

    @property
    def migration_name_fragment(self) -> str:
        return "remove_continuous_aggregate_policy"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        schema_editor.execute(
            format_remove_continuous_aggregate_policy_sql_query(
                self.continuous_aggregate,
                if_exists=self.if_exists,
            )
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: Any,
        from_state: Any,
        to_state: Any,
    ) -> None:
        if self.schedule_interval is None:
            raise IrreversibleError(
                "schedule_interval is required to reverse this operation"
            )
        schema_editor.execute(
            format_add_continuous_aggregate_policy_sql_query(
                self.continuous_aggregate,
                start_offset=self.start_offset,
                end_offset=self.end_offset,
                schedule_interval=self.schedule_interval,
            )
        )

    def describe(self) -> str:
        return "Removes a TimescaleDB continuous aggregate policy"


__all__ = [
    "AddColumnstorePolicy",
    "AddCompressionPolicy",
    "AddContinuousAggregatePolicy",
    "AddGeneratedAggregateColumn",
    "AddRetentionPolicy",
    "CreateContinuousAggregate",
    "CreateExtension",
    "CreateHypertable",
    "DropHypertable",
    "EnableColumnstore",
    "EnableCompression",
    "RefreshContinuousAggregate",
    "RemoveColumnstorePolicy",
    "RemoveCompressionPolicy",
    "RemoveContinuousAggregatePolicy",
    "RemoveRetentionPolicy",
]
