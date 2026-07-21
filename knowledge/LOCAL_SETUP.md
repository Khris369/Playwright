# Local Setup Guide

## What this runs

WorkflowBuilder is a FastAPI application with a separately built React/Vite graph editor, a MySQL database, and Playwright Chromium for browser runs. The default local mode executes runs in a FastAPI background task in the same interactive process, so a headed browser can be visible on the local desktop.

Redis/Celery are **not required** for the current default path. Celery task definitions exist, but the HTTP dispatcher does not enqueue them unless the application code is explicitly changed to do so. Redis is optional for multi-process picker WebSocket routing.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- MySQL 8+ or a compatible MySQL/MariaDB server
- Git and PowerShell (commands below are Windows-oriented)
- Chromium installed through Playwright

Optional:

- Redis, only for picker relay experiments or future queued execution work
- An OpenAI-compatible API key, only for AI editor assistance and run troubleshooting

## 1. Create and activate a virtual environment

From the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If script execution is blocked, use `Set-ExecutionPolicy -Scope Process Bypass` for the current PowerShell session.

## 2. Install and build the editor

The editor source lives in `editor/`; its Vite output is written directly to `app/web/editor-dist/`, which FastAPI serves at `/ui/editor`.

```powershell
Push-Location editor
npm ci
npm run build
Pop-Location
```

Useful editor checks:

```powershell
Push-Location editor
npm run typecheck
npm test
Pop-Location
```

Re-run `npm run build` after changing editor source before testing it through FastAPI.

## 3. Install Playwright Chromium

```powershell
python -m playwright install chromium
```

Use `python -m playwright install` instead if other browsers are needed. On Linux, browser dependencies may require `python -m playwright install --with-deps`.

## 4. Configure the application

Create `.env` in the repository root. Do not commit it. Start with the following local example and replace all credentials/secrets with local values:

```env
APP_NAME=WorkflowBuilder
APP_ENV=local
APP_DEBUG=true

DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=workflow_builder
DB_USERNAME=root
DB_PASSWORD=
DB_CHARSET=utf8mb4
DB_COLLATION=utf8mb4_unicode_ci
DB_PREFIX=
DB_STRICT=true
DB_ENGINE=InnoDB

# Optional read connection; it defaults to the primary connection when omitted.
DB_READ_HOST=127.0.0.1
DB_READ_PORT=3306
DB_READ_DATABASE=workflow_builder
DB_READ_USERNAME=root
DB_READ_PASSWORD=

PLAYWRIGHT_HEADLESS=false
WORKFLOW_ARTIFACTS_ENABLED=true
WORKFLOW_ARTIFACTS_DIR=app/web/artifacts
WORKFLOW_TRACE_ENABLED=true
WORKFLOW_FINAL_SCREENSHOT_ENABLED=true
WORKFLOW_STEP_SCREENSHOTS_ENABLED=false
WORKFLOW_ARTIFACT_RETENTION_DAYS=14

# Optional only: enables cross-process picker message relay.
# PICKER_REDIS_URL=redis://127.0.0.1:6379/1

# Optional only: used by AI assistant/troubleshooting endpoints.
# OPENAI_API_KEY=
# OPENAI_CHAT_MODEL=gpt-4o-mini
# OPENAI_CHAT_COMPLETIONS_URL=https://api.openai.com/v1/chat/completions

# Present for the Celery worker scaffold; not used by the default route dispatcher.
# CELERY_BROKER_URL=redis://127.0.0.1:6379/0
# CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
# CELERY_TASK_ALWAYS_EAGER=false
```

`PLAYWRIGHT_HEADLESS=false` is useful locally because the workflow runner launches Chromium from the API process. Set it to `true` for a non-interactive run environment.

## 5. Initialize the database

### Fresh database

`sql/001_init.sql` is the complete current bootstrap. It creates `workflow_builder`, selects it, creates all application tables and indexes, and seeds current roles, permissions, role mappings, and legacy step-type metadata.

```powershell
mysql -u root -p < sql\001_init.sql
```

If the MySQL account has no password:

```powershell
mysql -u root < sql\001_init.sql
```

Do **not** apply the retained upgrade files after a new bootstrap.

### Existing database

Back up the database first. For a database created before the consolidated bootstrap, apply only the applicable retained updates in the order documented by [sql/README.md](../sql/README.md): `007_run_arg_presets_is_active.sql` through `013_workflow_member_permissions.sql`.

These update scripts are intentionally not idempotent; do not rerun them blindly and do not apply them to a fresh `001_init.sql` installation.

## 6. Verify the database connection

```powershell
python test_db_connection.py
```

If it fails, confirm MySQL is running, the `.env` values are correct, and the MySQL user can access `workflow_builder`.

## 7. Start the application

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/ui`
- React graph editor: `http://127.0.0.1:8000/ui/editor?workflow_id=<id>`
- Health endpoint: `http://127.0.0.1:8000/health`

The first account is created through the bootstrap-admin flow. Once an account exists, use the login page and the user-management API/UI according to role permissions.

## 8. Smoke test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
```

Then:

1. Bootstrap an admin account and sign in.
2. Create a workflow and open it in the graph editor.
3. Add a supported step, confirm server validation is successful, and save an unpublished version.
4. Run the version with safe test inputs; inspect its run/step history and optional artifacts.
5. Publish a valid version only after verifying it, because published versions are read-only in the editor.

## Optional local picker agent

The picker agent helps author locators in a separate headed local browser. It does not share its cookies or browser profile with the server-side runner.

In a second terminal, after the API is running:

```powershell
.\venv\Scripts\Activate.ps1
python -m picker_agent --server ws://127.0.0.1:8000
```

Pair the displayed code from the editor's picker-agent control. See [PICKER_AGENT.md](../PICKER_AGENT.md) for the protocol, packaging, and current limitations.

## Artifact cleanup

Run this periodically if workflow artifacts are enabled:

```powershell
python -m app.cli.cleanup_workflow_artifacts
```

Use `--days <positive-number>` to override `WORKFLOW_ARTIFACT_RETENTION_DAYS` for one cleanup run.

## Troubleshooting

- **Editor does not reflect changes:** rebuild it with `cd editor; npm run build` and hard-refresh the browser.
- **Browser does not open:** install Chromium and ensure the API is running in an interactive desktop session with `PLAYWRIGHT_HEADLESS=false`.
- **Workflow save/run fails:** verify the version graph through the editor validation panel and confirm the fresh schema or the correct upgrade sequence was applied.
- **AI endpoints return 502:** configure `OPENAI_API_KEY` and, if needed, `OPENAI_CHAT_COMPLETIONS_URL`; core workflow features do not require them.
- **Picker disconnects after server restart:** this is expected in the current in-memory picker-session model. Reconnect/pair again; Redis relay does not make sessions durable.

## Local-security notes

- Keep `.env`, generated artifacts, and any local credentials out of version control.
- Do not expose this development configuration publicly. A production deployment requires TLS/reverse-proxy hardening, secret management, rate limiting, durable worker/session design, and operational monitoring.
- Store sensitive workflow values outside shared workflow definitions; use run inputs/presets only with appropriate access control.
