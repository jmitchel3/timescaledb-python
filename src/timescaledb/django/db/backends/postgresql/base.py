from __future__ import annotations

from django.db.backends.postgresql.base import DatabaseWrapper as PostgresDatabaseWrapper

from timescaledb.django import _django_version_tuple

_django_version_tuple()


class DatabaseWrapper(PostgresDatabaseWrapper):
    def get_connection_params(self) -> dict:
        params = super().get_connection_params()
        params.pop("timescaledb_auto_create_extension", None)
        return params

    def init_connection_state(self) -> None:
        super().init_connection_state()
        if self._timescaledb_auto_create_extension_enabled():
            self.ensure_timescaledb_extension()

    def _timescaledb_auto_create_extension_enabled(self) -> bool:
        options = self.settings_dict.get("OPTIONS", {})
        setting = self.settings_dict.get(
            "TIMESCALEDB_AUTO_CREATE_EXTENSION",
            options.get("timescaledb_auto_create_extension", True),
        )
        return bool(setting)

    def ensure_timescaledb_extension(self) -> None:
        with self.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
