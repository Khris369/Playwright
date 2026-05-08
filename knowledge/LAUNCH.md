# Launch Guide (Current)

## Purpose
How to run the current workflow builder stack locally.

Current default behavior:
- API executes workflow runs inline (same process/session) to support headed browser visibility.
- Redis/Celery are optional unless you explicitly switch back to queued mode.

## Prerequisites
- Python virtualenv at `./venv`
- Dependencies installed from `requirements.txt`
- MySQL database reachable from `.env`
- SQL files applied from `sql/`

## Required SQL
Apply in order:
1. `001_init.sql`
2. `002_schema_versions.sql`
3. `003_step_types.sql`
4. `004_step_types_ticket_steps.sql`
5. `005_step_types_click_by_role.sql`
6. `006_run_arg_presets.sql`

## Local Launch (Default Inline Mode)

Run API:
```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open UI:
- Dashboard: `http://127.0.0.1:8000/ui`
- Editor: `http://127.0.0.1:8000/ui/editor`

## Verification Checklist
1. Root:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```
Expected: app message JSON.

2. Health:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```
Expected: `status = ok`.

3. UI assets:
- `GET /ui`
- `GET /ui/editor`
- `GET /ui/static/app.js`

4. Functional smoke:
- Create/import workflow.
- Open editor and save current version.
- In Runs tab: select workflow/version, generate input template, save/load preset, trigger run.

## Optional Queue Mode (Advanced / Future Toggle)
If you reintroduce queue dispatch in route logic:
- Start Redis.
- Start Celery worker.
- Set queue-related env vars (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).

Worker command:
```powershell
.\venv\Scripts\python.exe -m celery -A app.worker.celery_app:celery_app worker --loglevel=info --pool=solo
```

## Troubleshooting
- UI not reflecting updates:
  - Hard refresh browser (`Ctrl+F5`).
- Step type missing in editor:
  - Confirm `003/004/005` SQL applied.
  - Confirm `GET /step-types` returns expected keys.
- Run preset errors:
  - Confirm `006_run_arg_presets.sql` applied.
  - Confirm `GET /run-arg-presets` works.
- Browser window not visible:
  - Ensure API is running in an interactive desktop session.
  - Headed windows appear where API process is running.
