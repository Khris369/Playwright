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

These files are retained only for existing installations.

## File Policy

- Keep `001_init.sql` as the complete first-time bootstrap.
- Keep only additive update files that existing databases still need.
- Do not add no-op compatibility files.
- Back up the database before applying update files manually.
