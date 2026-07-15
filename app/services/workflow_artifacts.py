from __future__ import annotations

import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.settings import get_settings
from app.services.workflow_run_repository import WorkflowRunRepository


def artifacts_root() -> Path:
    root = Path(get_settings().workflow_artifacts_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    return root.resolve()


def run_artifact_dir(run_id: int) -> Path:
    if run_id < 1:
        raise ValueError("invalid_run_id")
    path = artifacts_root() / "workflow-runs" / str(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def step_artifact_dir(run_id: int) -> Path:
    path = run_artifact_dir(run_id) / "steps"
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_artifact_path(path: Path) -> str:
    root = artifacts_root()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("artifact_outside_root")
    return resolved.relative_to(root).as_posix()


def resolve_artifact_path(relative_path: str) -> Path:
    root = artifacts_root()
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("artifact_outside_root")
    return resolved


def record_artifact(
    run_id: int,
    artifact_type: str,
    path: Path,
    step_run_id: int | None = None,
    mime_type: str | None = None,
) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    detected_mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return WorkflowRunRepository.create_artifact(
        workflow_run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        file_path=relative_artifact_path(path),
        mime_type=detected_mime,
        size_bytes=path.stat().st_size,
    )


def cleanup_artifacts_older_than(days: int | None = None, batch_size: int = 500) -> dict[str, int]:
    retention_days = get_settings().workflow_artifact_retention_days if days is None else days
    if retention_days < 1:
        raise ValueError("retention_days_must_be_positive")
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    rows = WorkflowRunRepository.list_artifacts_created_before(cutoff, limit=batch_size)
    removed_files = 0
    removed_rows: list[int] = []
    for row in rows:
        try:
            path = resolve_artifact_path(str(row["file_path"]))
        except ValueError:
            removed_rows.append(int(row["id"]))
            continue
        if path.exists() and path.is_file():
            path.unlink()
            removed_files += 1
        removed_rows.append(int(row["id"]))
        _remove_empty_parents(path.parent)
    deleted_rows = WorkflowRunRepository.delete_artifacts(removed_rows)
    return {
        "files_deleted": removed_files,
        "rows_deleted": deleted_rows,
        "rows_scanned": len(rows),
    }


def _remove_empty_parents(path: Path) -> None:
    root = artifacts_root()
    current = path.resolve()
    while current != root and current.is_relative_to(root):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
