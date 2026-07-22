from config.app import app_config
from app.core import settings as settings_module


def test_playwright_headless_defaults_false(monkeypatch) -> None:
    monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)

    assert app_config()["playwright_headless"] is False


def test_playwright_headless_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")

    assert app_config()["playwright_headless"] is True


def test_settings_exposes_playwright_headless(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_module,
        "app_config",
        lambda: {
            "name": "WorkflowBuilder",
            "env": "test",
            "debug": False,
            "playwright_headless": True,
            "workflow_artifacts_enabled": True,
            "workflow_trace_enabled": True,
            "workflow_final_screenshot_enabled": True,
            "workflow_step_screenshots_enabled": False,
            "workflow_artifact_retention_days": 14,
            "workflow_artifacts_dir": "app/web/artifacts",
        },
    )

    assert settings_module.get_settings().playwright_headless is True
