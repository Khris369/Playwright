"""Apply the project's ordered MySQL SQL files.

The SQL directory contains one complete bootstrap (001_init.sql) and older
database update files.  A fresh database needs the bootstrap only; an older
database needs the numbered updates after it.  The JSON state file records
both applied and baseline-skipped files so a later run is repeatable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.database import db_connection, db_settings


BASELINE_FILE = "001_init.sql"
STATE_VERSION = 1


def migration_files(sql_dir: Path) -> list[Path]:
    """Return SQL migration files in their explicit numeric filename order."""

    return sorted(sql_dir.glob("*.sql"), key=lambda path: path.name)


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_sql(sql: str) -> list[str]:
    """Split ordinary MySQL SQL on semicolons outside strings/comments.

    The repository migrations do not use stored-program DELIMITER blocks, so
    keeping this parser small avoids adding a SQL parsing dependency while
    still handling quoted values, identifiers, and comments safely.
    """

    statements: list[str] = []
    current: list[str] = []
    index = 0
    quote: str | None = None
    in_line_comment = False
    in_block_comment = False

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue

        if quote is not None:
            current.append(char)
            if char == "\\" and next_char:
                current.append(next_char)
                index += 2
                continue
            if char == quote:
                if next_char == quote:
                    current.append(next_char)
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char == "#" or (char == "-" and next_char == "-" and
                           (index + 2 == len(sql) or sql[index + 2].isspace())):
            in_line_comment = True
            index += 1 if char == "#" else 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char in "'\"`":
            quote = char
            current.append(char)
            index += 1
            continue
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "migrations": []}

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid migration state JSON: {path}") from exc

    if (
        not isinstance(state, dict)
        or state.get("version") != STATE_VERSION
        or not isinstance(state.get("migrations"), list)
    ):
        raise RuntimeError(f"Unsupported migration state format: {path}")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def state_records(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in state["migrations"]:
        if not isinstance(record, dict) or not isinstance(record.get("file"), str):
            raise RuntimeError("Migration state contains an invalid record")
        records[record["file"]] = record
    return records


def check_record_checksums(files: Iterable[Path], records: dict[str, dict[str, Any]]) -> None:
    current_files = {path.name: path for path in files}
    for filename, record in records.items():
        path = current_files.get(filename)
        if path is None:
            raise RuntimeError(f"Recorded migration is missing from disk: {filename}")
        if record.get("sha256") != file_checksum(path):
            raise RuntimeError(
                f"Migration changed after it was recorded; create a new migration: {filename}"
            )


def record_migration(
    state: dict[str, Any],
    path: Path,
    *,
    status: str,
    reason: str | None = None,
) -> None:
    record: dict[str, Any] = {
        "file": path.name,
        "sha256": file_checksum(path),
        "status": status,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        record["reason"] = reason
    state["migrations"].append(record)


def _table_names(cursor, database: str) -> set[str]:
    cursor.execute(
        """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
        """,
        (database,),
    )
    return {str(row["TABLE_NAME"]) for row in cursor.fetchall()}


def _column_names(cursor, database: str, table: str) -> set[str]:
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (database, table),
    )
    return {str(row["COLUMN_NAME"]) for row in cursor.fetchall()}


def has_current_bootstrap(cursor, database: str) -> bool:
    """Detect the schema represented by 001_init.sql without changing data."""

    required_tables = {
        "users", "user_sessions", "workflows", "workflow_versions",
        "workflow_runs", "workflow_step_runs", "workflow_run_artifacts",
        "workflow_templates", "schema_versions", "step_types", "run_arg_presets",
        "roles", "permissions", "user_roles", "role_permissions",
        "workflow_members", "workflow_member_permissions",
    }
    if not required_tables.issubset(_table_names(cursor, database)):
        return False

    required_columns = {
        "workflows": {"owner_user_id", "created_by_user_id", "updated_by_user_id"},
        "workflow_versions": {"created_by_user_id", "updated_by_user_id", "lock_version", "updated_at"},
        "workflow_runs": {
            "workflow_id", "created_by_user_id", "trigger_source", "resolved_definition_json",
            "execution_mode", "target_step_id", "definition_hash", "error_code",
        },
        "workflow_step_runs": {"step_id", "duration_ms", "screenshot_path"},
        "workflow_run_artifacts": {"created_by_user_id"},
        "run_arg_presets": {"owner_user_id", "isActive"},
    }
    for table, columns in required_columns.items():
        if not columns.issubset(_column_names(cursor, database, table)):
            return False

    # These legacy columns are deliberately absent from the current bootstrap.
    if {"role"}.intersection(_column_names(cursor, database, "users")):
        return False
    if {"access_level"}.intersection(_column_names(cursor, database, "workflow_members")):
        return False
    return True


def _database_has_tables(cursor, database: str) -> bool:
    return bool(_table_names(cursor, database))


def execute_file(connection, path: Path) -> None:
    statements = split_sql(path.read_text(encoding="utf-8"))
    if not statements:
        raise RuntimeError(f"Migration contains no SQL statements: {path.name}")
    try:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def migrate(
    *,
    sql_dir: Path,
    state_path: Path,
    mode: str = "auto",
    dry_run: bool = False,
) -> int:
    files = migration_files(sql_dir)
    if not files:
        raise RuntimeError(f"No .sql files found in {sql_dir}")
    if files[0].name != BASELINE_FILE:
        raise RuntimeError(f"{BASELINE_FILE} must be the first migration")

    state = load_state(state_path)
    records = state_records(state)
    check_record_checksums(files, records)
    pending = [path for path in files if path.name not in records]

    if not pending:
        print("No pending migrations.")
        return 0

    settings = db_settings()
    database = str(settings["database"])
    connection = None
    selected_mode = mode

    try:
        if mode == "auto":
            if records:
                # Once this runner has started, its state file is authoritative
                # and prevents reclassifying a partially completed run.
                connection = db_connection()
                selected_mode = "existing"
            else:
                try:
                    connection = db_connection()
                    with connection.cursor() as cursor:
                        if has_current_bootstrap(cursor, database):
                            selected_mode = "baseline"
                        elif not _database_has_tables(cursor, database):
                            selected_mode = "fresh"
                        else:
                            selected_mode = "existing"
                except Exception as exc:
                    if getattr(exc, "args", [None])[0] != 1049:
                        raise
                    connection = db_connection(select_database=False)
                    selected_mode = "fresh"
        elif mode == "fresh":
            connection = db_connection(select_database=False)
        elif mode == "existing":
            connection = db_connection()
        else:
            raise RuntimeError(f"Unsupported migration mode: {mode}")

        if dry_run:
            print(f"Migration mode: {selected_mode}")
            for path in pending:
                action = (
                    "apply"
                    if (
                        selected_mode == "fresh" and path.name == BASELINE_FILE
                    )
                    or (
                        selected_mode == "existing" and path.name != BASELINE_FILE
                    )
                    else "skip"
                )
                print(f"{action}: {path.name}")
            return 0

        if selected_mode == "baseline":
            for path in pending:
                if path.name == BASELINE_FILE:
                    record_migration(
                        state,
                        path,
                        status="applied",
                        reason="current bootstrap detected",
                    )
                else:
                    record_migration(
                        state,
                        path,
                        status="skipped",
                        reason="included in 001_init.sql",
                    )
            save_state(state_path, state)
            print("Current bootstrap detected; recorded existing migrations without reapplying them.")
            return 0

        if selected_mode == "fresh":
            if BASELINE_FILE in records:
                raise RuntimeError("Fresh mode cannot reuse a recorded bootstrap")
            baseline = next(path for path in pending if path.name == BASELINE_FILE)
            print(f"Applying {baseline.name}...")
            execute_file(connection, baseline)
            record_migration(state, baseline, status="applied")
            save_state(state_path, state)
            records = state_records(state)
            pending = [path for path in files if path.name not in records]

            reason = "included in 001_init.sql"
            for path in pending:
                record_migration(state, path, status="skipped", reason=reason)
            if pending:
                save_state(state_path, state)
                print(f"Recorded {len(pending)} baseline-included file(s) as skipped.")
            return 0

        # Existing databases receive only compatibility updates after 001.
        for path in pending:
            if path.name == BASELINE_FILE:
                record_migration(state, path, status="skipped", reason="existing database")
                save_state(state_path, state)
                continue
            print(f"Applying {path.name}...")
            execute_file(connection, path)
            record_migration(state, path, status="applied")
            save_state(state_path, state)
        return 0
    finally:
        if connection is not None:
            connection.close()


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Apply ordered MySQL migrations.")
    parser.add_argument("--sql-dir", type=Path, default=root / "sql")
    parser.add_argument("--state-file", type=Path, default=root / "sql" / "migrations_state.json")
    parser.add_argument(
        "--mode",
        choices=("auto", "fresh", "existing"),
        default="auto",
        help="auto detects the current schema; fresh applies 001 only; existing applies compatibility updates",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return migrate(
            sql_dir=args.sql_dir,
            state_path=args.state_file,
            mode=args.mode,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
