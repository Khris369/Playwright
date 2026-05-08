# SQL Convention

- `001_init.sql`: baseline table creation.
- `002_*.sql`, `003_*.sql`, ...: incremental schema updates.
- Keep files additive and ordered.
- In this project we use schema-first SQL files (no migration framework required).
- Current SQL style: minimal DDL, primary keys only unless explicitly needed.
