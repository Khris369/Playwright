from __future__ import annotations

from dataclasses import dataclass

from config import app_config


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    debug: bool


def get_settings() -> Settings:
    cfg = app_config()
    return Settings(
        app_name=str(cfg["name"]),
        environment=str(cfg["env"]),
        debug=bool(cfg["debug"]),
    )
