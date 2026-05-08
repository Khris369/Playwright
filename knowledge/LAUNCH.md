# Launch Guide

## Purpose
This document defines how to start and operate the current workflow builder stack.

Current services:
- API (`FastAPI`)
- Worker (`Celery`)
- Broker/Backend (`Redis`)

## Prerequisites
- Python virtualenv available at `./venv`
- Dependencies installed from `requirements.txt`
- MySQL database created and reachable from `.env`
- Redis available locally or remotely

## Environment
Ensure `.env` has these queue keys:
- `CELERY_BROKER_URL=redis://127.0.0.1:6379/0`
- `CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0`
- `CELERY_TASK_ALWAYS_EAGER=false`

## Local Launch (3 terminals)

## Terminal 1: Redis
If Redis is installed locally, start it with your local method.

Example with Docker:
```powershell
docker run --name wf-redis -p 6379:6379 redis:7
```

## Terminal 2: API
```powershell
$env:CELERY_TASK_ALWAYS_EAGER="false"
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Terminal 3: Celery Worker
```powershell
$env:CELERY_TASK_ALWAYS_EAGER="false"
.\venv\Scripts\python.exe -m celery -A app.worker.celery_app:celery_app worker --loglevel=info --pool=solo
```

## Verification Checklist
1. API root:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```
Expected: `{"message":"WorkflowBuilder API"}`

2. Health endpoint:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```
Expected: `status = ok`

3. Trigger run:
- Create workflow
- Create version
- `POST /workflow-runs`
- Verify worker picks task and run status changes

## Troubleshooting
- `Cannot connect to redis://127.0.0.1:6379/0`:
  - Redis is not running or not reachable.
- `ModuleNotFoundError: celery`:
  - Install deps in venv: `./venv/Scripts/python.exe -m pip install -r requirements.txt`
- Run stuck in `queued`:
  - Worker is not running or broker URL mismatch.

## Non-Eager vs Eager
- Non-eager (`CELERY_TASK_ALWAYS_EAGER=false`): real queue + worker execution.
- Eager (`CELERY_TASK_ALWAYS_EAGER=true`): task executes inline (no separate worker required).

## Production Launch Direction
Target setup should run all services together via orchestration.

Recommended:
- `docker-compose.yml` with services:
  - `api`
  - `worker`
  - `redis`
  - `ui` (Phase 5)

Then one command:
```bash
docker compose up -d
```

This is the planned release model; for now use the 3-terminal local launch above.

## Server Readiness Checklist
Use this before deployment discussions to identify blockers early.

1. Host and OS
- Required:
  - Linux or Windows server where Python services can run continuously.
- If not available:
  - Use a VM or container host dedicated for API/worker.

2. Runtime and Process Management
- Required:
  - Python 3.11+ (or validated project version), pip, virtualenv.
  - A process manager (`systemd`, `supervisor`, `pm2`, NSSM, or Docker restart policy).
- If not available:
  - Temporary: run manually in terminals (not production-safe).

3. Redis (Queue Broker)
- Required:
  - Reachable Redis endpoint for Celery broker/result backend.
- Options:
  - Native Redis service on same server.
  - Redis in Docker.
  - Managed Redis service (cloud).
- If not available:
  - Use eager mode (`CELERY_TASK_ALWAYS_EAGER=true`) for development only.

4. MySQL Database
- Required:
  - Reachable MySQL with required tables already provisioned.
  - Stable credentials in environment config.
- If not available:
  - Provision dedicated DB first; app cannot run workflow persistence without it.

5. Network and Firewall
- Required:
  - API port exposed internally (or via reverse proxy).
  - Outbound access from worker to target websites under test.
  - Access to Redis and MySQL ports.
- If not available:
  - Coordinate firewall allowlists and outbound egress rules.

6. DNS / TLS / Reverse Proxy
- Recommended for production:
  - Domain name, TLS certificate, reverse proxy (`nginx`/`traefik`/IIS).
- If not available:
  - Internal HTTP only for non-production environments.

7. Secrets and Config Management
- Required:
  - `.env` values provided securely (`DB_*`, `CELERY_*`).
- Better options:
  - Vault/secret manager, environment injection by CI/CD or host platform.
- If not available:
  - Restrict `.env` file permissions and avoid committing secrets.

8. Observability and Logs
- Required:
  - API and worker logs retained and accessible.
- Recommended:
  - Central log aggregation and alerting for failed runs.
- If not available:
  - Start with local file logs and scheduled cleanup.

9. Scaling and Concurrency
- Required:
  - Decide initial worker concurrency and queue load expectations.
- Options:
  - Single worker (`--pool=solo`) for simplicity.
  - Multiple workers/instances for throughput.
- If not available:
  - Keep low concurrency and accept slower queue drain.

10. Reliability / Restart Strategy
- Required:
  - Auto-restart on crash/reboot for API, worker, Redis.
- If not available:
  - Operational risk is high; deployment not recommended.

11. Browser Automation Runtime (for future real Playwright-backed steps)
- Required later:
  - Playwright browser dependencies and OS libraries on worker hosts.
- If not available:
  - Keep engine in simulated/state-driven mode only.

## Deployment Mode Decision Matrix
Choose one mode per environment.

1. Dev quick mode
- `CELERY_TASK_ALWAYS_EAGER=true`
- No Redis/worker service required
- Tradeoff: not true async behavior

2. Staging/production-like mode
- `CELERY_TASK_ALWAYS_EAGER=false`
- Redis + Celery worker required
- Recommended before production go-live

3. Production mode
- Non-eager + managed processes + TLS/proxy + monitoring
- Prefer container orchestration or robust service manager
