# Local picker agent (Phase 1 and Phase 2 reliability)

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

The agent prints a short pairing code. Enter it in the picker panel under **Agent pairing code**, then click **Pair agent**. FastAPI sends a scoped device token directly to the agent; the agent stores it locally and reconnects automatically on later launches. If the stored token is rejected after a server restart or expiry, the agent clears it and starts a new pairing flow. The code expires after five minutes and is usable once.

The development server address is `ws://127.0.0.1:8000`; a deployed agent must use the HTTPS site's `wss://` address. Install Chromium binaries for the local agent if needed:

```powershell
python -m playwright install chromium
```

## Use in the editor

Select a draft workflow node with a direct locator field, then use **Pick Element**. Optionally supply an HTTP(S) start URL. The agent opens Chromium on the local machine; navigate and sign in manually. Choose **Start Selecting**, select the highlighted element, review the structured locator, and choose **Accept**. Acceptance only updates unsaved editor state. It never saves, publishes, versions, or runs a workflow.

Use **Cancel** to close the picker context. Browser/context resources are also closed by the agent when the session closes or the agent disconnects. Expiry is checked by the single FastAPI process when picker operations occur.

## Authentication and limits

Server workflow access continues to use the application's cookie session, roles, and workflow edit access. Pairing uses a one-time five-minute code. The resulting device token is scoped to picker WebSocket access, stored locally by the agent, and expires after 30 days in this POC. It is not a general API credential and contains no target-site credentials. The legacy `POST /editor-picker/agent-token` endpoint remains available for development compatibility.

Picker sessions, pairing requests, and device claims are opaque in-memory records, expire after their TTLs, and are bound to the user where applicable. This is intentionally limited to one FastAPI process: restarting it disconnects agents, loses active sessions, and requires pairing again. No Redis routing, durable database-backed device management, profile persistence, screenshot streaming, remote desktop, or cross-instance coordination is included.

The local agent accepts only typed picker commands. It rejects unknown commands and non-HTTP(S) navigation schemes. It does not expose arbitrary Python, shell, filesystem, or server-provided JavaScript execution.

## Deferred work

The agent now has a fixed injected-inspector fallback. New tabs and popups are tracked and reported as page changes; a full tab-management UI remains deferred. Frames currently return an explicit unsupported result because reliable runner-compatible frame support needs an engine extension. The UI currently supports direct locator fields, not nested ticket-field rows. Redis routing, durable database-backed device management, production secrets, full cross-instance expiry sweeping, and packaged desktop distribution remain future work.
