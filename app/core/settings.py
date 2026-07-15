from __future__ import annotations

from dataclasses import dataclass

from config import app_config


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    debug: bool
    workflow_artifacts_enabled: bool
    workflow_trace_enabled: bool
    workflow_final_screenshot_enabled: bool
    workflow_artifacts_dir: str


def get_settings() -> Settings:
    cfg = app_config()
    return Settings(
        app_name=str(cfg["name"]),
        environment=str(cfg["env"]),
        debug=bool(cfg["debug"]),
        workflow_artifacts_enabled=bool(cfg["workflow_artifacts_enabled"]),
        workflow_trace_enabled=bool(cfg["workflow_trace_enabled"]),
        workflow_final_screenshot_enabled=bool(cfg["workflow_final_screenshot_enabled"]),
        workflow_artifacts_dir=str(cfg["workflow_artifacts_dir"]),
    )
