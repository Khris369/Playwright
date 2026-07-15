# Playwright Run Artifacts Dashboard Plan

## Goal

Enhance the existing backend workflow Runs dashboard with Playwright debugging artifacts while keeping the current Python workflow runner and drag-and-drop editor intact.

This is option 1 from the dashboard discussion:

- Keep `/ui/editor` as the workflow authoring surface.
- Keep `/ui?tab=runs` as the run trigger and monitoring surface.
- Keep `WorkflowRunnerService.execute_run()` as the backend execution path.
- Add trace, screenshot, video, and log artifacts to runs and steps.
- Use Playwright Trace Viewer for deep browser debugging instead of rebuilding Playwright's full dashboard.

## Non-Goals

- Do not replace the Python backend runner with Node Playwright Test.
- Do not require generated `.spec.ts` files for normal workflow execution.
- Do not rebuild Playwright UI Mode inside the app.
- Do not change the workflow editor JSON contract unless artifact metadata requires additive fields.
- Do not expose artifact files without authorization checks if auth is later added.

## Current Architecture

Current run flow:

1. User triggers a run from `/ui?tab=runs`.
2. Frontend posts to `POST /workflow-runs`.
3. `app/api/routes/workflow_runs.py` creates the run.
4. `WorkflowRunnerService.execute_run()` launches Python Playwright.
5. `app/engine/executor.py` executes workflow steps against `page`.
6. Step results are written through `WorkflowRunRepository`.
7. The Runs dashboard displays run and step status.

The key files are:

- `app/api/routes/workflow_runs.py`
- `app/services/workflow_runner.py`
- `app/services/workflow_run_repository.py`
- `app/engine/executor.py`
- `app/web/static/app.js`

## Proposed User Experience

In the Runs tab, each run should show artifact links when available:

- Trace
- Final screenshot
- Failure screenshot
- Video
- Step-level screenshots, if enabled
- Error log

Example:

```text
Run #123
Status: failed

Step 1 goto_url              passed
Step 2 fill_input            passed
Step 3 click                 failed

Artifacts
[Download trace] [Open screenshot] [Download video]
```

The trace artifact should be opened with Playwright Trace Viewer locally:

```bash
playwright show-trace path/to/trace.zip
```

Optionally, a later phase can add a helper endpoint or documented local command for opening traces.

## Storage Design

Use an application-controlled artifacts directory outside frontend source folders.

Recommended path:

```text
app/web/artifacts/workflow-runs/{run_id}/
```

Example contents:

```text
app/web/artifacts/workflow-runs/123/
  trace.zip
  video.webm
  final.png
  failure.png
  steps/
    000-goto_url.png
    001-fill_input.png
    002-click.png
```

Important constraints:

- Never derive artifact paths directly from user input.
- Use numeric `run_id` and sanitized generated filenames only.
- Keep artifacts read-only after write.
- Avoid storing secrets in filenames.
- Treat traces as sensitive because they can include DOM snapshots, URLs, typed values, console data, and network metadata.

## Database Changes

Add artifact metadata rather than hardcoding file discovery into the UI.

Suggested table:

```sql
CREATE TABLE workflow_run_artifacts (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  workflow_run_id BIGINT NOT NULL,
  step_run_id BIGINT NULL,
  artifact_type VARCHAR(50) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  size_bytes BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Suggested artifact types:

- `trace`
- `video`
- `final_screenshot`
- `failure_screenshot`
- `step_screenshot`
- `console_log`
- `network_log`

Repository additions:

- `create_artifact(...)`
- `list_artifacts_for_run(run_id)`
- `list_artifacts_for_step(step_run_id)`

## Backend API Changes

Add artifact listing and download endpoints.

Suggested routes:

```text
GET /workflow-runs/{run_id}/artifacts
GET /workflow-runs/{run_id}/artifacts/{artifact_id}
```

Download endpoint safeguards:

- Look up artifact by ID and run ID.
- Resolve canonical path.
- Verify the resolved path remains inside the configured artifacts root.
- Return `404` for missing artifacts.
- Return generic errors without leaking filesystem paths.
- Use explicit content type and `Content-Disposition`.

## Runner Changes

Update `WorkflowRunnerService.execute_run()` to create a per-run artifact directory.

Initial Playwright context setup:

```python
context_pw = browser.new_context(record_video_dir=str(video_dir))
context_pw.tracing.start(screenshots=True, snapshots=True, sources=True)
```

On successful completion:

```python
page.screenshot(path=str(final_screenshot_path), full_page=True)
context_pw.tracing.stop(path=str(trace_path))
```

On step failure:

```python
page.screenshot(path=str(failure_screenshot_path), full_page=True)
context_pw.tracing.stop(path=str(trace_path))
```

Video handling:

- Close the context before reading the video path.
- Persist the generated video file path as a run artifact.
- If video is too large or not needed by default, gate it behind run input or config.

Step screenshots:

- Start with failure screenshot only.
- Add optional per-step screenshots later using an input flag:

```json
{
  "capture_step_screenshots": true
}
```

Recommended default artifact behavior:

- Trace: enabled
- Failure screenshot: enabled
- Final screenshot: enabled
- Video: disabled by default
- Per-step screenshots: disabled by default

## UI Changes

Update `app/web/static/app.js` in the Runs tab:

1. Fetch run artifacts after loading a run.
2. Render artifact links near the run summary.
3. Render step artifact links beside each step row if step-level artifacts exist.
4. Clearly label sensitive artifacts as local/debug artifacts.

Minimum useful UI:

- A run-level "Artifacts" section.
- Link to download `trace.zip`.
- Link to open/download screenshots.
- Link to download video when present.

## Configuration

Add settings for artifact behavior:

- `WORKFLOW_ARTIFACTS_ENABLED`
- `WORKFLOW_ARTIFACTS_DIR`
- `WORKFLOW_TRACE_ENABLED`
- `WORKFLOW_VIDEO_ENABLED`
- `WORKFLOW_STEP_SCREENSHOTS_ENABLED`
- `WORKFLOW_ARTIFACT_RETENTION_DAYS`

Defaults should be conservative:

- Artifacts enabled in local development.
- Video disabled.
- Step screenshots disabled.
- Retention policy documented even if cleanup is implemented later.

## Security Considerations

Artifacts can contain sensitive data.

Required controls:

- Do not store artifacts under arbitrary user-controlled paths.
- Do not expose filesystem paths in API responses.
- Do not include secrets in artifact filenames.
- Use canonical path checks before serving files.
- Add auth/authorization checks when the app has user auth.
- Consider redaction or disabling trace snapshots for workflows that handle secrets.
- Add artifact retention cleanup to avoid indefinite sensitive data storage.

## Implementation Phases

### Phase 1: Minimal Run Artifacts

- Add artifact directory creation.
- Capture trace, final screenshot, and failure screenshot.
- Store artifact metadata in DB.
- Add artifact list endpoint.
- Add artifact download endpoint.
- Show run-level artifact links in Runs dashboard.

Validation:

- Trigger a passing run and confirm trace/final screenshot are stored.
- Trigger a failing run and confirm trace/failure screenshot are stored.
- Download artifacts from the Runs dashboard.
- Open trace with `playwright show-trace`.

### Phase 2: Step-Level Debugging

- Link artifacts to `workflow_step_runs`.
- Add optional per-step screenshot capture.
- Render step-level artifact links.
- Add better error messages around artifact capture failures without failing the workflow solely because artifact capture failed.

Status: implemented as an opt-in feature. Enable globally with `WORKFLOW_STEP_SCREENSHOTS_ENABLED=true` or per run with:

```json
{
  "capture_step_screenshots": true
}
```

Validation:

- Enable step screenshots through run inputs.
- Confirm each step screenshot maps to the expected step index and node ID.

### Phase 3: Video and Logs

- Add optional video recording.
- Capture browser console logs.
- Capture selected network request metadata.
- Add UI sections for video/log artifacts.

Validation:

- Confirm context close flushes video files.
- Confirm large videos do not block normal run finalization.

### Phase 4: Retention and Cleanup

- Add cleanup command or scheduled task.
- Delete artifacts older than configured retention.
- Keep DB metadata in sync or mark deleted artifacts.

Status: implemented as a manual/schedulable command:

```bash
python -m app.cli.cleanup_workflow_artifacts --days 14
```

If `--days` is omitted, the command uses `WORKFLOW_ARTIFACT_RETENTION_DAYS`.

Validation:

- Run cleanup against test artifacts.
- Confirm no path traversal or accidental outside-directory deletion is possible.

## Risks

- Trace files can grow large.
- Video files can grow very large.
- Trace snapshots can expose sensitive input values.
- Artifact capture should not mask the real workflow failure.
- Serving local files must be path-safe.

## Recommendation

Implement Phase 1 first. It provides most of the debugging value with the least architecture change and keeps the current workflow runner intact.
