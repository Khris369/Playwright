from __future__ import annotations

import os
from pathlib import Path


def token_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "WorkflowPicker"
    root.mkdir(parents=True, exist_ok=True)
    return root / "device-token"


def load_device_token() -> str | None:
    try:
        value = token_path().read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def save_device_token(token: str) -> None:
    path = token_path()
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def clear_device_token() -> None:
    try:
        token_path().unlink(missing_ok=True)
    except OSError:
        pass
