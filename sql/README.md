# SQL Convention

This project uses plain ordered SQL files instead of a migration framework.

## Fresh Install

For a new database, apply only:

1. `001_init.sql`

`001_init.sql` contains the current complete schema, including:

- users
- workflows and workflow versions
- workflow runs and step runs
- workflow run artifacts
- workflow templates
- schema versions
- step types and current default seeds
- run argument presets
- account ownership columns added for future auth
- roles, permissions, user_roles, role_permissions, and workflow_members

## Existing Database Updates

For databases that were initialized before the latest consolidated schema, apply the update files in order:

1. `007_run_arg_presets_is_active.sql`
2. `008_workflow_graph_versioning.sql`
3. `009_accounts.sql`
4. `010_workflow_last_updated.sql`
5. `011_rbac.sql`
6. `012_remove_legacy_user_role.sql`
7. `013_workflow_member_permissions.sql`
8. `014_verify_element_step_type.sql`

These files are retained only for existing installations.

## File Policy

- Keep `001_init.sql` as the complete first-time bootstrap.
- Keep only additive update files that existing databases still need.
- Do not add no-op compatibility files.
- Back up the database before applying update files manually.

## Migration Runner

Run the ordered migration command from the repository root:

```text
python -m app.cli.migrate
```

The command uses the existing `DB_*` settings, detects whether the configured
database is fresh, legacy, or already at the current bootstrap, and writes
checksummed results to `sql/migrations_state.json`. A fresh database applies
`001_init.sql` and records the compatibility files as included in that
bootstrap. An older database applies the numbered update files after `001` in
filename order. Use `--dry-run` to inspect the planned actions, or
`--mode fresh` / `--mode existing` when automatic detection is not suitable.
