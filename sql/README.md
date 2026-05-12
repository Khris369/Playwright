# SQL Convention

- `001_init.sql`: baseline table creation for a fresh database.
- `002_*.sql`, `003_*.sql`, ...: additive schema updates for existing databases.
- Keep files additive and ordered.
- In this project we use schema-first SQL files (no migration framework required).
- Current SQL style: minimal DDL with `AUTO_INCREMENT` primary keys for repository `lastrowid` usage.

## Current Ordered Files
1. `001_init.sql`
2. `002_schema_versions.sql` (compatibility no-op; consolidated into `001`)
3. `003_step_types.sql` (compatibility no-op; consolidated into `001`)
4. `004_step_types_ticket_steps.sql` (compatibility no-op; consolidated into `003`)
5. `005_step_types_click_by_role.sql` (compatibility no-op; consolidated into `003`)
6. `006_run_arg_presets.sql` (compatibility no-op; consolidated into `001`)
7. `007_run_arg_presets_is_active.sql` (additive safety migration for pre-consolidation DBs)
