from __future__ import annotations

from typing import Dict

from config.app import env


def database_config() -> Dict[str, object]:
    return {
        "default": env("DB_CONNECTION", "mysql"),
        "connections": {
            "mysql": {
                "driver": "mysql",
                "host": env("DB_HOST", "127.0.0.1"),
                "port": int(env("DB_PORT", "3306") or "3306"),
                "database": env("DB_DATABASE", "workflow_builder"),
                "username": env("DB_USERNAME", "root"),
                "password": env("DB_PASSWORD", ""),
                "charset": env("DB_CHARSET", "utf8mb4"),
                "collation": env("DB_COLLATION", "utf8mb4_unicode_ci"),
                "prefix": env("DB_PREFIX", ""),
                "strict": (env("DB_STRICT", "true") or "true").lower()
                in {"1", "true", "yes", "on"},
                "engine": env("DB_ENGINE", "InnoDB"),
            },
            "mysql_read": {
                "driver": "mysql",
                "host": env("DB_READ_HOST", env("DB_HOST", "127.0.0.1")),
                "port": int(env("DB_READ_PORT", env("DB_PORT", "3306") or "3306")),
                "database": env("DB_READ_DATABASE", env("DB_DATABASE", "workflow_builder")),
                "username": env("DB_READ_USERNAME", env("DB_USERNAME", "root")),
                "password": env("DB_READ_PASSWORD", env("DB_PASSWORD", "")),
                "charset": env("DB_CHARSET", "utf8mb4"),
                "collation": env("DB_COLLATION", "utf8mb4_unicode_ci"),
                "prefix": env("DB_PREFIX", ""),
                "strict": (env("DB_STRICT", "true") or "true").lower()
                in {"1", "true", "yes", "on"},
                "engine": env("DB_ENGINE", "InnoDB"),
            },
        },
        "migrations_table": "migrations",
    }
