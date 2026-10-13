from pathlib import Path

from app.cli.migrate import migration_files, split_sql


def test_migration_files_are_sorted_and_ignore_non_sql_files(tmp_path: Path) -> None:
    (tmp_path / "010_later.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "README.md").write_text("not a migration", encoding="utf-8")

    assert [path.name for path in migration_files(tmp_path)] == [
        "001_first.sql",
        "010_later.sql",
    ]


def test_split_sql_ignores_comments_and_semicolons_in_literals() -> None:
    sql = """
    -- comment; ignored
    INSERT INTO example (value) VALUES ('one;two');
    /* comment; ignored */
    SELECT `literal;identifier`, "quoted;value";
    """

    assert split_sql(sql) == [
        "INSERT INTO example (value) VALUES ('one;two')",
        'SELECT `literal;identifier`, "quoted;value"',
    ]
