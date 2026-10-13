from __future__ import annotations

from typing import Any, Dict

from config import database_config


class DatabaseConfigError(RuntimeError):
    pass


class DatabaseManager:
    def __init__(self) -> None:
        self._config = database_config()

    def default_connection_name(self) -> str:
        return str(self._config["default"])

    def connection_settings(self, name: str | None = None) -> Dict[str, Any]:
        connection_name = name or self.default_connection_name()
        connections = self._config.get("connections", {})
        settings = connections.get(connection_name)

        if settings is None:
            raise DatabaseConfigError(
                f"Connection '{connection_name}' not found in config/database.py"
            )

        return settings

    def connect(self, name: str | None = None, *, select_database: bool = True):
        settings = self.connection_settings(name)
        driver = settings.get("driver")

        if driver != "mysql":
            raise DatabaseConfigError(f"Unsupported driver: {driver}")

        try:
            import pymysql
        except ImportError as exc:
            raise DatabaseConfigError(
                "PyMySQL is not installed. Install it with: pip install pymysql"
            ) from exc

        connection_kwargs = {
            "host": settings["host"],
            "port": int(settings["port"]),
            "user": settings["username"],
            "password": settings["password"],
            "charset": settings["charset"],
            "autocommit": False,
            "cursorclass": pymysql.cursors.DictCursor,
        }
        if select_database:
            connection_kwargs["database"] = settings["database"]
        return pymysql.connect(**connection_kwargs)


_db = DatabaseManager()


def db_connection(name: str | None = None, *, select_database: bool = True):
    return _db.connect(name, select_database=select_database)


def db_settings(name: str | None = None) -> Dict[str, Any]:
    return _db.connection_settings(name)
