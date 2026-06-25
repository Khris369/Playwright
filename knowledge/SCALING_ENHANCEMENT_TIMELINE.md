# Scaling Enhancement Timeline

## Purpose
This timeline outlines the enhancements needed to move the current workflow builder from a bare-bones internal tool into a stronger platform for larger Playwright testing workloads.

The main focus is the builder experience, execution reliability, reusable test data, and operational safety.

## Assumptions
- The application remains a FastAPI + MySQL + Playwright workflow builder.
- The current UI is useful for MVP workflows but needs stronger guardrails for larger tests.
- Larger testing means longer workflows, more repeated runs, more input presets, and eventual concurrent execution.
- Security, validation, and observability are part of the implementation, not optional follow-up work.

## Recommended Timeline

### Week 1 - Builder Guardrails
**Objective:** Make the builder harder to misuse.

Planned work:
- Add workflow definition validation before save and run.
- Validate required step arguments per step type.
- Show inline errors per step card instead of only JSON-level errors.
- Prevent invalid JSON from silently desynchronizing the visual builder and raw JSON.
- Add missing input detection for `{{inputs.*}}` placeholders.
- Add safer defaults for timeout and retry fields.

Deliverable:
- Builder blocks or clearly flags invalid workflows before execution.

Outcome:
- Users can build workflows with fewer broken runs.

### Week 2 - Step Type Metadata
**Objective:** Make step creation scalable.

Planned work:
- Expand `step_types` to store argument schema, required fields, examples, categories, and help text.
- Generate builder forms from step metadata instead of hard-coded frontend templates.
- Group steps by category:
  - navigation
  - form actions
  - assertions
  - waits
  - ticket actions
  - custom actions
- Add reusable common patterns such as login, search, create ticket, and submit form.

Deliverable:
- Schema-driven step configuration in the builder.

Outcome:
- Adding new step types no longer requires heavy frontend changes.

### Weeks 3-4 - Builder UX for Larger Tests
**Objective:** Make long workflows manageable.

Planned work:
- Add search and filter for steps.
- Add workflow sections or groups.
- Add collapse and expand by section.
- Add copy/paste for a step or group.
- Add duplicate workflow/version actions.
- Add annotations or comments per step.
- Add a dry-run validation button.
- Add basic version comparison: current revision vs previous revision.

Deliverable:
- Builder supports larger workflows without becoming difficult to scan or edit.

Outcome:
- Workflows with 50-100+ steps become manageable.

### Weeks 5-6 - Execution Reliability
**Objective:** Improve repeatability and failure diagnosis.

Planned work:
- Add per-step timeout controls.
- Add retry and backoff support for transient failures.
- Capture screenshots on failure.
- Store screenshot and artifact paths in `workflow_step_runs.screenshot_path`.
- Add run-level timeout.
- Guarantee browser/session cleanup after pass, fail, or cancellation.
- Add structured error categories:
  - selector missing
  - timeout
  - assertion failed
  - navigation failed
  - custom action failed

Deliverable:
- Run failures include enough context for users to diagnose from the UI/API.

Outcome:
- Failures become easier to debug and less flaky.

### Weeks 7-8 - Larger Test Runs
**Objective:** Support bigger execution volume.

Planned work:
- Reintroduce queue mode as a first-class execution option.
- Use Celery/Redis for background execution.
- Add max concurrent browser session controls.
- Add queued/running/completed run dashboard views.
- Add cancellation support.
- Add run tags, environment name, browser type, and headed/headless mode.
- Add batch run support for running the same workflow across multiple input presets.

Deliverable:
- Workflow execution can scale beyond one interactive API process.

Outcome:
- The application can run larger suites without blocking the UI/API.

### Weeks 9-10 - Test Data and Reusability
**Objective:** Make workflows reusable across brands, environments, and scenarios.

Planned work:
- Add test data set management.
- Link workflows to input presets or data sets.
- Add environment profiles:
  - local
  - staging
  - UAT
  - production-like
- Add template versioning.
- Add reusable workflow fragments such as:
  - Login
  - Open Ticket Page
  - Submit Ticket
  - Logout
- Add import/export for workflows and templates.

Deliverable:
- Workflows can be reused across multiple scenarios without cloning every step.

Outcome:
- One workflow can support many test cases through data and environment configuration.

### Weeks 11-12 - Security and Governance
**Objective:** Protect credentials, workflow changes, and run operations.

Planned work:
- Add authentication.
- Add role-based access:
  - viewer
  - editor
  - runner
  - admin
- Add secret references instead of raw credentials in workflow JSON.
- Add audit trail for workflow/version changes and run triggers.
- Add validation to block dangerous custom actions unless explicitly allowed.
- Add rate limits and request body limits.

Deliverable:
- Team usage is controlled, auditable, and safer for sensitive workflows.

Outcome:
- The application is better prepared for broader internal use.

## Priority Order
If delivery needs to be compressed, prioritize in this order:

1. Builder validation and step schemas.
2. Screenshot and artifact capture.
3. Per-step timeout and retry controls.
4. Queue and concurrency support.
5. Batch runs with input presets.
6. Secrets, authentication, and audit trail.
7. Reusable fragments and data sets.

## Main Builder Gap
The current visual editor is still too close to raw JSON. For larger testing, the most important builder improvement is schema-driven step forms with validation.

After that, the next major investments should be:
- diagnostics and artifacts
- queued execution
- batch runs
- reusable data sets and workflow fragments

## Suggested Milestones

### Milestone 1 - Safer Builder
Includes:
- workflow validation
- step argument validation
- missing input checks
- schema-driven step metadata

Exit criteria:
- A user can save and run only structurally valid workflows.

### Milestone 2 - Debuggable Runs
Includes:
- screenshots on failure
- timeout and retry controls
- structured failure categories
- cleaner run and step logs

Exit criteria:
- Most failures can be diagnosed from the run detail screen.

### Milestone 3 - Scaled Execution
Includes:
- queued execution
- concurrency controls
- cancellation
- batch runs

Exit criteria:
- Multiple workflows or input presets can run without blocking interactive use.

### Milestone 4 - Reusable Testing Platform
Includes:
- data sets
- environment profiles
- workflow fragments
- template versioning

Exit criteria:
- Teams can reuse workflows across brands, URLs, credentials, and scenarios.

### Milestone 5 - Governed Internal Use
Includes:
- authentication
- roles
- secret references
- audit logs
- rate limits

Exit criteria:
- The app is suitable for broader team access.
