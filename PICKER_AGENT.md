# Local picker agent (Phase 1–3)

The element picker is a local, headed Chromium design aid. It does not share its browser profile, cookies, passwords, local storage, IndexedDB, or target-site authentication with the server-side workflow runner.

## Start locally

From the repository root, start FastAPI after configuring the normal application environment:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Sign in to the editor and start the agent in another terminal. No token is required:

```powershell
python -m picker_agent --server ws://127.0.0.1:8000
```

The agent prints a short pairing code. Enter it in the editor's standalone **Picker agent** pairing control, then click **Pair agent**. FastAPI sends a scoped device token directly to the agent; the agent stores it locally and reconnects automatically on later launches. If the stored token is rejected after a server restart or expiry, the agent clears it and starts a new pairing flow. The code expires after five minutes and is usable once.

If FastAPI or the WebSocket temporarily disconnects, the running agent retries automatically with bounded exponential backoff. You do not need to restart the agent for a transient server restart or network interruption.

The development server address is `ws://127.0.0.1:8000`; a deployed agent must use the HTTPS site's `wss://` address. Install Chromium binaries for the local agent if needed:

```powershell
python -m playwright install chromium
```

## Optional Windows packaging

For a local end-user style test, build a self-contained agent directory (the
Chromium browser binaries remain a separate local install):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_picker_agent.ps1
python -m playwright install chromium
```

Run the packaged executable once so it can be paired:

```powershell
dist\picker-agent\workflow-picker-agent\workflow-picker-agent.exe --server ws://127.0.0.1:8000
```

After pairing, it can start automatically for the signed-in Windows user:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_picker_agent_startup.ps1 `
  -AgentExecutable "$PWD\dist\picker-agent\workflow-picker-agent\workflow-picker-agent.exe" `
  -Server ws://127.0.0.1:8000
```

Remove the startup task with `scripts\uninstall_picker_agent_startup.ps1`. This
uses an interactive per-user scheduled task rather than a Windows service:
headed Chromium cannot reliably display from Session 0, where ordinary Windows
services run. The CLI remains supported for development and troubleshooting.

## Use in the editor

Select a draft workflow node with a direct locator field, then use **Pick Element**. Optionally supply an HTTP(S) start URL. The agent opens Chromium on the local machine; navigate and sign in manually. Choose **Start Selecting**, select the highlighted element, review the structured locator, and choose **Accept**. Acceptance only updates unsaved editor state. It never saves, publishes, versions, or runs a workflow.

Use **Cancel** to close the picker context. Browser/context resources are also closed by the agent when the session closes or the agent disconnects. Expiry is checked by the single FastAPI process when picker operations occur.

Picker previews are scoped to the workflow node and locator field. You can start a selection on one node, switch to another node, and return to the first node without losing its unfinished preview. Accepting a locator still writes only to that node's local editor state; it does not save or run the workflow. Active browser sessions continue to obey the normal session expiry and cancellation cleanup rules.

## Authentication and limits

Server workflow access continues to use the application's cookie session, roles, and workflow edit access. Pairing uses a one-time five-minute code. The resulting device token is scoped to picker WebSocket access, stored locally by the agent, and expires after 30 days in this POC. It is not a general API credential and contains no target-site credentials. The legacy `POST /editor-picker/agent-token` endpoint remains available for development compatibility.

Picker sessions, pairing requests, and device claims are opaque in-memory records, expire after their TTLs, and are bound to the user where applicable. Without the optional Redis relay, this is intentionally limited to one FastAPI process: restarting it disconnects agents, loses active sessions, and requires pairing again. Durable database-backed device management, profile persistence, screenshot streaming, remote desktop, and distributed presence remain deferred.

## Phase 4 shared routing (optional)

Set `PICKER_REDIS_URL` on every FastAPI instance to enable Redis pub/sub
routing for picker commands and editor results:

```text
PICKER_REDIS_URL=redis://127.0.0.1:6379/1
```

WebSocket connections remain local to the process that accepted them; Redis
relays typed JSON messages to the process holding the target user's agent or
editor socket. Leaving the setting unset preserves the local single-process
mode. Session/device records are still in memory in this increment, so durable
session storage and distributed presence/expiry are separate follow-up work.

The local agent accepts only typed picker commands. It rejects unknown commands and non-HTTP(S) navigation schemes. It does not expose arbitrary Python, shell, filesystem, or server-provided JavaScript execution.

## Deferred work

Phase 3 currently adds node-scoped draft preservation in the editor while keeping the localhost/in-memory development model unchanged.

The agent now has a fixed injected-inspector fallback. New tabs and popups are tracked and reported as page changes; a full tab-management UI remains deferred. Frames currently return an explicit unsupported result because reliable runner-compatible frame support needs an engine extension. The UI currently supports direct locator fields, not nested ticket-field rows. Redis routing, durable database-backed device management, production secrets, full cross-instance expiry sweeping, and packaged desktop distribution remain future work.
