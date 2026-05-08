from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

_ENV_LOADED = False


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_env_file(path: str = ".env") -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(path)
    if not env_path.exists():
        _ENV_LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)

    _ENV_LOADED = True


def env(key: str, default: str | None = None) -> str | None:
    load_env_file()
    return os.getenv(key, default)


def app_config() -> Dict[str, object]:
    return {
        "name": env("APP_NAME", "WorkflowBuilder"),
        "env": env("APP_ENV", "local"),
        "debug": _to_bool(env("APP_DEBUG"), default=True),
    }
