# Local Setup Guide

## Purpose
This guide explains how to clone the repository and run the workflow builder locally.

The current default mode runs workflow executions inline from the API process. Redis and Celery are optional unless you intentionally switch to queued execution.
The dashboard lives at `/ui`, and the dedicated React/Vite editor lives at `/ui/editor`.

## Prerequisites

Install these before starting:

- Python 3.11 or newer
- Node.js 20 or newer
- MySQL 8 or compatible MySQL/MariaDB server
- Git
- A terminal or PowerShell

Optional for queue mode:

- Redis

## 1. Clone the Repository

```powershell
git clone <repo-url>
cd playwright
```

If the repository is cloned into a different folder name, run all commands from that project root.

## 2. Create a Python Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 3. Install Python Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Install Editor Dependencies

The React/Vite editor is managed separately from the Python backend.

```powershell
cd editor
npm ci
cd ..
```

## 5. Build the Editor

```powershell
cd editor
npm run build
cd ..
```

## 6. Install Playwright Browsers

```powershell
python -m playwright install
```

For Chromium only:

```powershell
python -m playwright install chromium
```

## 7. Create the MySQL Database

Log in to MySQL and create the database:

```sql
CREATE DATABASE IF NOT EXISTS workflow_builder
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Example using MySQL CLI:

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS workflow_builder CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

If your local MySQL root user has no password, omit `-p`.

## 8. Create the `.env` File

Create a `.env` file in the project root.

Example local configuration:

```env
# Application
APP_NAME=WorkflowBuilder
APP_ENV=local
APP_DEBUG=true

# Database
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

# Optional named read replica
DB_READ_HOST=127.0.0.1
DB_READ_PORT=3306
DB_READ_DATABASE=workflow_builder
DB_READ_USERNAME=root
DB_READ_PASSWORD=

# Queue, optional for future queued mode
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CELERY_TASK_ALWAYS_EAGER=false

# Playwright
PLAYWRIGHT_HEADLESS=false

# Troubleshoot AI, optional
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_CHAT_COMPLETIONS_URL=https://api.openai.com/v1/chat/completions
```

Notes:
- Use `PLAYWRIGHT_HEADLESS=false` if you want to see the browser window locally.
- Use `PLAYWRIGHT_HEADLESS=true` for headless execution.
- Leave `OPENAI_API_KEY` blank unless using AI troubleshooting/editor assistant features.
- Do not commit `.env`.

## 9. Apply SQL Files

Apply SQL files from `sql/` in numeric order.

Current ordered files:

1. `001_init.sql`
2. `002_schema_versions.sql`
3. `003_step_types.sql`
4. `004_step_types_ticket_steps.sql`
5. `005_step_types_click_by_role.sql`
6. `006_run_arg_presets.sql`
7. `007_run_arg_presets_is_active.sql`
8. `008_workflow_graph_versioning.sql`

Example:

```powershell
mysql -u root -p workflow_builder < sql\001_init.sql
mysql -u root -p workflow_builder < sql\002_schema_versions.sql
mysql -u root -p workflow_builder < sql\003_step_types.sql
mysql -u root -p workflow_builder < sql\004_step_types_ticket_steps.sql
mysql -u root -p workflow_builder < sql\005_step_types_click_by_role.sql
mysql -u root -p workflow_builder < sql\006_run_arg_presets.sql
mysql -u root -p workflow_builder < sql\007_run_arg_presets_is_active.sql
mysql -u root -p workflow_builder < sql\008_workflow_graph_versioning.sql
```

If your MySQL user has no password:

```powershell
mysql -u root workflow_builder < sql\001_init.sql
```

Repeat for the remaining SQL files.

Important:
- Some SQL files may be compatibility no-ops for newer fresh databases. Still apply them in order.
- `001_init.sql` includes `USE workflow_builder;`, so make sure the database exists before applying it.

## 10. Verify Database Connection

```powershell
python test_db_connection.py
```

Expected result:

```text
Connection successful. Query result: ...
```

If this fails, check:
- MySQL is running.
- `.env` database host, port, username, and password are correct.
- The `workflow_builder` database exists.

## 11. Start the API Server

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/ui`
- Editor: `http://127.0.0.1:8000/ui/editor?workflow_id=<id>`
- Health check: `http://127.0.0.1:8000/health`

## 12. Verify the App

In a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected:
- root endpoint returns the app API message
- health endpoint returns `status = ok`

Functional smoke test:

1. Open `http://127.0.0.1:8000/ui`.
2. Create or import a workflow.
3. Open the editor.
4. Add or edit steps.
5. Save the version.
6. Use the editor Runs tab to open the dashboard Runs view for that workflow/version.
7. Generate input template.
8. Trigger a run.
9. Monitor the run and step logs.

## Optional: Queue Mode with Redis and Celery

The default local setup does not require Redis/Celery. Use this only if you want queued background execution.

Start Redis first.

Then start the API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start a Celery worker in another terminal:

```powershell
.\venv\Scripts\Activate.ps1
python -m celery -A app.worker.celery_app:celery_app worker --loglevel=info --pool=solo
```

Notes:
- Celery is the background job runner.
- Redis is the message broker Celery uses.
- Playwright runs wherever the worker process runs.
- If the worker runs on your machine in headed mode, the browser window opens on your machine.

## Troubleshooting

### UI Loads but Workflows Fail to Save
Check the database connection and confirm all SQL files were applied.

### Step Types Are Missing
Confirm the `step_types` table has rows:

```sql
SELECT `key`, `name`, `is_active` FROM step_types ORDER BY sort_order;
```

If rows are missing, reapply the SQL files in order.

### Browser Does Not Open
Check `PLAYWRIGHT_HEADLESS`.

Use:

```env
PLAYWRIGHT_HEADLESS=false
```

Also confirm the API process is running in an interactive desktop session.

### Playwright Browser Install Error
Run:

```powershell
python -m playwright install
```

If browser dependencies are missing on Linux, run:

```bash
python -m playwright install --with-deps
```

### Port 8000 Already in Use
Use another port:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Then open:

```text
http://127.0.0.1:8001/ui
```

### OpenAI Features Fail
The troubleshoot/editor assistant features require `OPENAI_API_KEY`.

Core workflow builder features should still work without it.

## Current Local Development Notes

- This app is currently intended for local/internal development.
- Do not expose the app publicly without authentication and access controls.
- Do not store plaintext credentials in workflow JSON for shared usage.
- Prefer input presets and future secret references for sensitive values.
- For larger team use, review the future plans in:
  - `knowledge/SCALING_ENHANCEMENT_TIMELINE.md`
  - `knowledge/LOCAL_AGENT_FUTURE_PLAN.md`
