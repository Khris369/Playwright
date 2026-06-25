# Local Playwright Agent Future Plan

## Purpose
This document outlines a future implementation plan for running Playwright workflows on each user's own machine while keeping the workflow builder, run history, and management UI centralized on a server.

The goal is to let a user trigger a workflow from the central web UI and have the actual browser automation window open on that user's machine instead of the server machine.

## Current Behavior
Today, Playwright runs wherever the backend execution process runs.

Examples:
- If FastAPI runs the workflow inline on the developer machine, the browser opens on that developer machine.
- If a Celery worker runs the workflow on a server, the browser opens on the server, usually in headless mode.
- If another user accesses the UI through an exposed IP, their browser only accesses the web UI. The Playwright browser does not open on their machine.

## Target Architecture

### Central Server
The central server remains responsible for:
- serving the FastAPI UI/API
- storing workflows and workflow versions
- storing run records and step logs
- managing users and runner permissions
- registering local runner agents
- assigning workflow runs to runner agents
- receiving status updates and artifacts from agents

Core components:
- FastAPI
- MySQL
- optional Redis/Celery for server-side/background jobs
- artifact storage directory or object storage

### Local User Machine Agent
Each user machine runs a lightweight local agent process.

The agent is responsible for:
- authenticating to the central server
- registering itself as an available runner
- sending heartbeat status
- polling for assigned workflow jobs
- executing Playwright locally
- sending step logs and run status back to the server
- uploading screenshots, traces, videos, and other artifacts

Example launch command:

```powershell
python -m app.agent.runner --server http://your-server:8000 --token <runner-token>
```

## Recommended Communication Model
Use agent polling for the first implementation.

Why polling:
- works when users are behind office or home NAT
- avoids inbound connections to user machines
- avoids needing firewall/router changes
- simpler than WebSockets for the first version

Basic polling flow:

1. Local agent starts.
2. Agent authenticates using a scoped runner token.
3. Agent sends heartbeat to central server.
4. Agent calls the server to ask for its next assigned job.
5. Server returns a queued run if one exists.
6. Agent claims the run.
7. Agent executes the workflow with Playwright locally.
8. Agent posts step status, logs, artifacts, and final result back to the server.

## Proposed Data Model Additions

### `runners`
Stores local and shared execution machines.

Suggested columns:
- `id`
- `name`
- `owner_user_id`
- `machine_id`
- `status`
  - `online`
  - `offline`
  - `busy`
  - `disabled`
- `last_seen_at`
- `capabilities_json`
- `created_at`
- `updated_at`

Example `capabilities_json`:

```json
{
  "os": "windows",
  "browsers": ["chromium", "firefox"],
  "supports_headed": true,
  "supports_headless": true,
  "max_parallel_runs": 1
}
```

### `runner_tokens`
Stores hashed authentication tokens for local agents.

Suggested columns:
- `id`
- `runner_id`
- `token_hash`
- `name`
- `last_used_at`
- `revoked_at`
- `created_at`

Security notes:
- store only token hashes
- show the raw token only once during creation
- allow revocation from the UI
- scope each token to a single runner

### `workflow_runs` additions
Add runner assignment fields.

Suggested columns:
- `runner_id`
- `execution_mode`
  - `server_inline`
  - `server_queue`
  - `local_agent`
- `browser_name`
  - `chromium`
  - `firefox`
  - `webkit`
- `headed`
- `claimed_at`
- `claimed_by_runner_id`

### `run_artifacts`
Stores screenshots, traces, videos, and other files.

Suggested columns:
- `id`
- `workflow_run_id`
- `workflow_step_run_id`
- `artifact_type`
  - `screenshot`
  - `trace`
  - `video`
  - `console_log`
  - `network_log`
- `storage_path`
- `mime_type`
- `size_bytes`
- `created_at`

## Proposed Agent API Endpoints

Use a separate route group such as `/agent/*`.

### Runner Lifecycle

```text
POST /agent/register
POST /agent/heartbeat
POST /agent/shutdown
```

### Job Polling and Claiming

```text
GET /agent/jobs/next
POST /agent/jobs/{run_id}/claim
POST /agent/jobs/{run_id}/started
POST /agent/jobs/{run_id}/finished
POST /agent/jobs/{run_id}/failed
```

### Step Updates

```text
POST /agent/jobs/{run_id}/steps/{step_index}/started
POST /agent/jobs/{run_id}/steps/{step_index}/log
POST /agent/jobs/{run_id}/steps/{step_index}/passed
POST /agent/jobs/{run_id}/steps/{step_index}/failed
```

### Artifact Uploads

```text
POST /agent/jobs/{run_id}/artifacts
POST /agent/jobs/{run_id}/steps/{step_index}/artifacts
```

## Security Requirements

The local agent model must be implemented with strict controls.

Required controls:
- agent tokens must be scoped to one runner
- tokens must be stored hashed server-side
- tokens must be revocable
- agents may only fetch jobs assigned to their runner
- agents may only update runs they have claimed
- all agent APIs must require authentication
- run assignment must check user and runner permissions
- workflow inputs must not contain plaintext secrets
- secret values should be resolved locally only when required and only through approved mechanisms
- artifact uploads must enforce file size and file type limits
- logs must redact sensitive values
- audit logs must record runner registration, run assignment, claim, completion, and failures

Do not expose a local machine runner to arbitrary users without authentication and authorization. A browser automation runner can access internal URLs and perform actions from the runner machine's network.

## Run Assignment Flow

### User Flow
1. User opens the central workflow builder UI.
2. User selects a workflow and version.
3. User selects inputs or a preset.
4. User selects a runner, for example:
   - `My Laptop`
   - `QA Machine 1`
   - `Shared Server Runner`
5. User selects browser options:
   - headed or headless
   - Chromium, Firefox, or WebKit
6. User triggers the run.
7. Server creates `workflow_runs` row with `runner_id` and status `queued`.
8. Assigned local agent picks up and executes the run.

### Agent Flow
1. Agent polls `/agent/jobs/next`.
2. Server returns only jobs assigned to that runner.
3. Agent claims the job.
4. Server marks run as `running` or `claimed`.
5. Agent executes the workflow locally.
6. Agent sends step updates and artifacts.
7. Agent sends final run status.
8. Server marks runner as `online` or `idle`.

## Failure Handling

The implementation must handle:
- agent goes offline after claiming a job
- user closes laptop during a run
- Playwright crashes
- browser launch fails
- run exceeds timeout
- artifact upload fails
- central server restarts
- duplicate polling attempts
- stale `running` jobs

Recommended safeguards:
- heartbeat timeout marks runner as `offline`
- claimed jobs have a lease timeout
- only one agent can claim a run
- stale claimed jobs can be reset or marked failed
- step and run updates must be idempotent where possible
- run cancellation should be checked between steps

## Implementation Phases

### Phase 1 - Basic Local Agent
Objective: Prove that a user machine can execute an assigned workflow.

Planned work:
- add `runners` table
- add manual runner token creation
- add local agent entrypoint
- add heartbeat endpoint
- add job polling endpoint
- add job claim endpoint
- execute workflow locally using existing runner service
- send final status back to server

Exit criteria:
- a run assigned to a local agent opens the browser on the user's machine and updates the central run status.

### Phase 2 - Step Logs and Artifacts
Objective: Make local runs diagnosable from the central UI.

Planned work:
- send step started/passed/failed updates
- stream or batch step logs back to server
- capture screenshot on failure
- upload screenshots as artifacts
- optionally enable Playwright trace/video capture
- add artifact links in run detail UI

Exit criteria:
- users can inspect local-agent run failures from the central UI.

### Phase 3 - Runner Management UI
Objective: Let admins and users manage available execution machines.

Planned work:
- runner list page or panel
- online/offline/busy indicators
- last heartbeat display
- runner capability display
- create/revoke runner token flow
- runner selector when triggering a workflow run
- show current job per runner

Exit criteria:
- users can choose a runner and admins can manage runner access.

### Phase 4 - Hardening
Objective: Make the runner model safe for broader team usage.

Planned work:
- scoped agent authentication
- run locking and lease timeout
- cancellation support
- audit logs
- rate limits
- request body limits
- artifact upload validation
- sensitive value redaction
- runner permissions by user/team

Exit criteria:
- local agents can be used safely by multiple users without cross-runner access.

### Phase 5 - Packaging and Distribution
Objective: Make installation practical for non-developers.

Planned work:
- create a simple agent install guide
- provide `.env` or config file support
- package the agent as a Windows script or executable
- add auto-start option if needed
- add version reporting from agent to server
- add compatibility check for Python, Playwright, and browsers

Exit criteria:
- a user can install and run the local agent with minimal manual setup.

## Server-Side vs Local-Agent Execution

### Server-Side Execution
Best for:
- scheduled regression runs
- headless batch testing
- shared QA workers
- CI-style execution

Trade-offs:
- browser runs on the server
- headed browser is not visible to the triggering user
- needs server capacity planning

### Local-Agent Execution
Best for:
- interactive debugging
- workflows that need the user's desktop/network context
- headed browser observation
- user-specific environments

Trade-offs:
- depends on user machine availability
- harder to standardize environments
- requires agent installation and token management
- needs strict security controls

## First Recommended Version
Build the first version with:
- polling instead of WebSockets
- one run at a time per local agent
- headed Chromium support first
- screenshot-on-failure artifact upload
- manual runner token creation
- simple runner selector in the run trigger UI

This keeps the implementation small while proving the most important behavior: the browser opens and runs on the user's own machine.

