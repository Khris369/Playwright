const $ = (id) => document.getElementById(id);
const on = (id, event, handler) => {
  const el = $(id);
  if (el) {
    el.addEventListener(event, handler);
  }
};
const setValueIfPresent = (id, value) => {
  const el = $(id);
  if (el) {
    el.value = value;
  }
};

function estimateRowsFromContent(value, minRows = 3, maxRows = 24) {
  const text = String(value || "");
  const lines = text.split("\n");
  const wrappedRows = lines.reduce((sum, line) => {
    const len = Math.max(1, line.length);
    return sum + Math.ceil(len / 80);
  }, 0);
  return Math.max(minRows, Math.min(maxRows, wrappedRows));
}

function autoResizeTextarea(el, { minRows = 3, maxRows = 24 } = {}) {
  if (!el) {
    return;
  }
  el.rows = estimateRowsFromContent(el.value, minRows, maxRows);
  el.style.height = "auto";
  const lineHeight = parseFloat(window.getComputedStyle(el).lineHeight) || 22;
  const minHeightPx = Math.ceil(lineHeight * minRows) + 24;
  const maxHeightPx = Math.ceil(lineHeight * maxRows) + 24;
  const targetHeight = Math.max(minHeightPx, Math.min(el.scrollHeight, maxHeightPx));
  el.style.height = `${targetHeight}px`;
  syncRunInputLineNumbers();
}

function autoResizeById(id, options) {
  const el = $(id);
  if (!el) {
    return;
  }
  autoResizeTextarea(el, options);
  el.addEventListener("input", () => autoResizeTextarea(el, options));
}

function syncRunInputLineNumbers() {
  const input = $("run-inputs");
  const gutter = $("run-inputs-line-numbers");
  if (!input || !gutter) {
    return;
  }
  const lineCount = Math.max(1, String(input.value || "").split("\n").length);
  gutter.innerHTML = Array.from({ length: lineCount }, (_, index) => index + 1).join("<br>");
  gutter.style.height = input.style.height || `${input.offsetHeight}px`;
  gutter.scrollTop = input.scrollTop;
}

const defaultDefinition = {
  schema_version: 2,
  graph: {
    nodes: [{ id: "00000000-0000-4000-8000-000000000001", kind: "start", position: { x: 80, y: 160 } }],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 }
  }
};

const stepTemplates = {
  goto_url: { url: "{{inputs.base_url}}" },
  fill_input: { target: { strategy: "label", label: "Field" }, value: "" },
  click: { target: { strategy: "role", role: "button", name: "Submit" } },
  select_option: { target: { strategy: "label", label: "Field" }, option: { by: "label", value: "Option" } },
  wait_for_element: { target: { strategy: "text", text: "Ready" }, state: "visible" },
  wait_timeout: { timeout_ms: 1000 },
  assert_url_not_equal: { url: "" },
  assert_text_visible: { text: "" },
  ticket_select_scenario: { scenario_name: "{{inputs.scenario_name}}" },
  ticket_create_new_ticket: {},
  ticket_fill_fields: {
    fields: [
      { target: { strategy: "label", label: "Reference ID" }, control_type: "text", value: "AUTO-REF-001" },
      { target: { strategy: "label", label: "Description" }, control_type: "text", value: "Created by workflow builder." }
    ]
  },
  ticket_submit: {},
};
const defaultStepTypeKeys = Object.keys(stepTemplates);
let availableStepTypes = [...defaultStepTypeKeys];

function getDefaultArgsForStepType(stepType) {
  const template = stepTemplates[stepType];
  if (template && typeof template === "object") {
    return JSON.parse(JSON.stringify(template));
  }
  return {};
}

function toTitleCaseFromSnake(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function summarizeStep(step) {
  const stepType = String(step?.type || "");
  const args = step?.args && typeof step.args === "object" ? step.args : {};
  const selector = args.selector || args.scope_selector || args.target || "";
  const value = args.value || args.text || args.url || args.action || "";

  if (stepType === "fill_input") {
    return {
      sentence: selector && value ? `Sets ${selector} to ${value}` : "Fills an input field",
      target: selector || "-",
      value: value || "-",
    };
  }
  if (stepType === "click") {
    return {
      sentence: selector ? `Clicks ${selector}` : "Performs a click action",
      target: selector || "-",
      value: "-",
    };
  }
  if (stepType === "goto_url") {
    return {
      sentence: value ? `Navigates to ${value}` : "Navigates to a URL",
      target: "-",
      value: value || "-",
    };
  }
  return {
    sentence: `${toTitleCaseFromSnake(stepType)} step`,
    target: selector || "-",
    value: value || "-",
  };
}

let editorSteps = [];
let draggedStepIndex = null;
let dropPlaceholderIndex = null;
let currentWorkflowVersions = [];
let currentWorkflows = [];
let runTriggerCooldownUntil = 0;
const isDedicatedEditorPage = window.location.pathname === "/ui/editor";

function editorUrlFor(workflowId) {
  return `/ui/editor?workflow_id=${encodeURIComponent(workflowId)}`;
}

function updateCurrentWorkflowIndicator(workflow) {
  const el = $("editor-current-workflow");
  if (!el) {
    return;
  }
  if (!workflow || !workflow.id) {
    el.textContent = "No workflow selected";
    el.classList.remove("is-active");
    return;
  }
  const name = workflow.name || "(unnamed)";
  el.textContent = `Currently editing: #${workflow.id} ${name}`;
  el.classList.add("is-active");
}

if ($("ver-definition")) {
  $("ver-definition").value = JSON.stringify(defaultDefinition, null, 2);
}
if ($("run-inputs")) {
  $("run-inputs").value = JSON.stringify({ base_url: "https://example.com/login", username: "tester" }, null, 2);
}

function parseDefinitionJson() {
  const parsed = JSON.parse($("ver-definition").value || "{}");
  if (!parsed || typeof parsed !== "object") {
    return { steps: [] };
  }
  if (!Array.isArray(parsed.steps)) {
    parsed.steps = [];
  }
  return parsed;
}

function getStepTypeOptionsHtml(selectedType) {
  const known = new Set(availableStepTypes);
  const options = [...availableStepTypes];
  if (selectedType && !known.has(selectedType)) {
    options.push(selectedType);
  }
  return options
    .map((type) => `<option value="${type}" ${type === selectedType ? "selected" : ""}>${type}</option>`)
    .join("");
}

function populateStepTypePalette() {
  const select = $("step-type-select");
  if (!select) {
    return;
  }
  const current = select.value;
  select.innerHTML = availableStepTypes
    .map((type) => `<option value="${type}" ${type === current ? "selected" : ""}>${type}</option>`)
    .join("");
  if (!select.value && availableStepTypes.length) {
    select.value = availableStepTypes[0];
  }
}

async function refreshStepTypes() {
  try {
    const rows = await api("/step-types");
    const keys = (rows || [])
      .map((row) => String(row.key || "").trim())
      .filter((key) => key.length > 0);
    if (keys.length) {
      availableStepTypes = keys;
    } else {
      availableStepTypes = [...defaultStepTypeKeys];
    }
  } catch (err) {
    availableStepTypes = [...defaultStepTypeKeys];
  }
  populateStepTypePalette();
}

function syncJsonFromSteps() {
  const definition = parseDefinitionJson();
  definition.steps = editorSteps.map((step) => ({
    type: step.type,
    args: step.args || {},
  }));
  $("ver-definition").value = JSON.stringify(definition, null, 2);
  autoResizeTextarea($("ver-definition"), { minRows: 12, maxRows: 70 });
}

function syncStepsFromJson() {
  const definition = parseDefinitionJson();
  editorSteps = (definition.steps || []).map((step) => ({
    type: String(step.type || "click"),
    args: step.args && typeof step.args === "object" ? step.args : {},
  }));
  renderStepBuilder();
}

function updateWorkflowInfoPanel(latestVersion, workflowId) {
  const versionEl = $("wf-info-version-id");
  const workflowEl = $("wf-info-workflow-id");
  const revisionEl = $("wf-info-revision");
  if (versionEl) {
    versionEl.textContent = latestVersion?.id ? String(latestVersion.id) : "-";
  }
  if (workflowEl) {
    workflowEl.textContent = workflowId ? String(workflowId) : "-";
  }
  if (revisionEl) {
    revisionEl.textContent = latestVersion?.version_number
      ? String(latestVersion.version_number)
      : "-";
  }
}

function updateVersionPrimaryActions() {
  const saveBtn = $("btn-save-version");
  if (!saveBtn) {
    return;
  }
  saveBtn.style.display = "";
}

function populateRevisionDropdown(versions, selectedVersionId = null) {
  const select = $("ver-revision-id");
  if (!select) {
    return;
  }
  const rows = Array.isArray(versions) ? versions : [];
  if (!rows.length) {
    select.innerHTML = `<option value="">No revisions found</option>`;
    return;
  }
  select.innerHTML = rows
    .map(
      (v) =>
        `<option value="${v.id}">Revision ${v.version_number} (${v.is_published ? "published" : "draft"})</option>`
    )
    .join("");
  if (selectedVersionId) {
    select.value = String(selectedVersionId);
  } else {
    select.value = String(rows[0].id);
  }
}

function loadVersionIntoEditor(version, workflowId) {
  if (!version) {
    return;
  }
  setValueIfPresent("ver-current-version-id", version.id);
  setValueIfPresent("ver-workflow-id", workflowId);
  if ($("ver-revision-id")) {
    setValueIfPresent("ver-revision-id", version.id);
  }
  if ($("ver-published")) {
    $("ver-published").checked = Boolean(version.is_published);
  }
  if ($("ver-definition")) {
    $("ver-definition").value = JSON.stringify(version.definition_json || defaultDefinition, null, 2);
    autoResizeTextarea($("ver-definition"), { minRows: 12, maxRows: 70 });
  }
  updateWorkflowInfoPanel(version, workflowId);
  updateVersionPrimaryActions();
  if ($("step-builder")) {
    syncStepsFromJson();
  }
}

function renderStepBuilder() {
  const builder = $("step-builder");
  if (!builder) {
    return;
  }
  if (!editorSteps.length) {
    builder.innerHTML = "<div class='step-empty'>No steps yet. Add one from the dropdown above.</div>";
    return;
  }
  builder.innerHTML = editorSteps
    .map((step, index) => {
      const summary = summarizeStep(step);
      return `
      <div class="step-card" data-step-index="${index}">
        <details class="step-collapse">
          <summary class="step-collapse-summary">
            <div class="step-summary-main">
              <div class="step-card-title">Step ${index + 1} — ${escapeHtml(toTitleCaseFromSnake(step.type))}</div>
              <div class="step-summary-row"><span class="step-summary-label">Target:</span> <span>${escapeHtml(summary.target)}</span></div>
              <div class="step-summary-row"><span class="step-summary-label">Value:</span> <span>${escapeHtml(summary.value)}</span></div>
              <div class="step-summary-text">Summary: ${escapeHtml(summary.sentence)}</div>
            </div>
            <div class="step-card-controls">
              <div class="step-menu-wrap">
                <button class="step-secondary step-menu-trigger" type="button" data-action="open-menu" data-step-index="${index}" title="More actions">⋯</button>
                <div class="step-menu" data-menu="${index}">
                  <button class="step-menu-item" type="button" data-action="insert-above" data-step-index="${index}">Insert Above</button>
                  <button class="step-menu-item" type="button" data-action="insert-below" data-step-index="${index}">Insert Below</button>
                  <button class="step-menu-item" type="button" data-action="duplicate" data-step-index="${index}">Duplicate</button>
                </div>
              </div>
              <div class="step-drag" draggable="true" data-drag-handle="true" data-step-index="${index}" title="Drag to reorder">::</div>
            </div>
          </summary>
          <div class="step-collapse-body">
            <div class="grid2">
              <select data-field="type" data-step-index="${index}">
                ${getStepTypeOptionsHtml(step.type)}
              </select>
              <button class="step-default" type="button" data-action="default-args" data-step-index="${index}">Default Args</button>
            </div>
            <div class="step-args-title">Arguments JSON</div>
            <div class="step-actions">
              <button class="step-remove" type="button" data-action="remove" data-step-index="${index}">Remove</button>
            </div>
            <textarea data-field="args" data-step-index="${index}" spellcheck="false">${JSON.stringify(step.args || {}, null, 2)}</textarea>
          </div>
        </details>
      </div>
    `;
    })
    .join("");
  const placeholder = document.createElement("div");
  placeholder.className = "step-drop-placeholder";
  placeholder.style.display = "none";
  builder.appendChild(placeholder);

  builder.querySelectorAll("[data-action='remove']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      editorSteps.splice(index, 1);
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("[data-action='insert-above']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const sourceType = editorSteps[index]?.type || "click";
      editorSteps.splice(index, 0, {
        type: sourceType,
        args: getDefaultArgsForStepType(sourceType),
      });
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("[data-action='insert-below']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const sourceType = editorSteps[index]?.type || "click";
      editorSteps.splice(index + 1, 0, {
        type: sourceType,
        args: getDefaultArgsForStepType(sourceType),
      });
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("[data-action='duplicate']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const currentStep = editorSteps[index];
      if (!currentStep) {
        return;
      }
      editorSteps.splice(index + 1, 0, JSON.parse(JSON.stringify(currentStep)));
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("[data-action='open-menu']").forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const stepIndex = Number(el.getAttribute("data-step-index"));
      const menu = builder.querySelector(`.step-menu[data-menu='${stepIndex}']`);
      if (!menu) {
        return;
      }
      builder.querySelectorAll(".step-menu").forEach((m) => m.classList.remove("is-open"));
      menu.classList.toggle("is-open");
    });
  });

  builder.querySelectorAll(".step-menu-item").forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
  });

  builder.onclick = () => {
    builder.querySelectorAll(".step-menu").forEach((m) => m.classList.remove("is-open"));
  };

  builder.querySelectorAll("select[data-field='type']").forEach((el) => {
    el.addEventListener("change", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const nextType = el.value;
      editorSteps[index].type = nextType;
      editorSteps[index].args = getDefaultArgsForStepType(nextType);
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("[data-action='default-args']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const stepType = editorSteps[index]?.type || "click";
      editorSteps[index].args = getDefaultArgsForStepType(stepType);
      syncJsonFromSteps();
      renderStepBuilder();
      toast(`Reset args to defaults for step ${index + 1}`);
    });
  });

  builder.querySelectorAll("textarea[data-field='args']").forEach((el) => {
    autoResizeTextarea(el, { minRows: 4, maxRows: 20 });
    el.addEventListener("input", () => autoResizeTextarea(el, { minRows: 4, maxRows: 20 }));
    el.addEventListener("change", () => {
      const index = Number(el.getAttribute("data-step-index"));
      try {
        const parsedArgs = JSON.parse(el.value || "{}");
        if (!parsedArgs || typeof parsedArgs !== "object" || Array.isArray(parsedArgs)) {
          throw new Error("args must be a JSON object");
        }
        editorSteps[index].args = parsedArgs;
        syncJsonFromSteps();
      } catch (err) {
        toast(`Invalid args JSON on step ${index + 1}: ${err.message}`, true);
      }
    });
  });

  builder.querySelectorAll("[data-drag-handle='true']").forEach((handle) => {
    handle.addEventListener("dragstart", () => {
      const stepIndex = Number(handle.getAttribute("data-step-index"));
      draggedStepIndex = stepIndex;
      dropPlaceholderIndex = stepIndex;
      const card = builder.querySelector(`.step-card[data-step-index='${stepIndex}']`);
      if (card) {
        card.classList.add("dragging");
      }
      placeholder.style.display = "";
    });
    handle.addEventListener("dragend", () => {
      const stepIndex = Number(handle.getAttribute("data-step-index"));
      draggedStepIndex = null;
      dropPlaceholderIndex = null;
      const card = builder.querySelector(`.step-card[data-step-index='${stepIndex}']`);
      if (card) {
        card.classList.remove("dragging");
      }
      placeholder.style.display = "none";
    });
  });

  builder.querySelectorAll(".step-card").forEach((card) => {
    card.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (draggedStepIndex === null) {
        return;
      }
      const rect = card.getBoundingClientRect();
      const cardIndex = Number(card.getAttribute("data-step-index"));
      const insertBefore = event.clientY < rect.top + rect.height / 2;
      dropPlaceholderIndex = insertBefore ? cardIndex : cardIndex + 1;

      if (insertBefore) {
        builder.insertBefore(placeholder, card);
      } else {
        builder.insertBefore(placeholder, card.nextSibling);
      }
      placeholder.style.display = "";
    });
    card.addEventListener("drop", () => {
      if (draggedStepIndex === null || dropPlaceholderIndex === null) {
        return;
      }
      let insertIndex = dropPlaceholderIndex;
      const [moved] = editorSteps.splice(draggedStepIndex, 1);
      if (insertIndex > draggedStepIndex) {
        insertIndex -= 1;
      }
      editorSteps.splice(insertIndex, 0, moved);
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.addEventListener("dragleave", (event) => {
    if (!builder.contains(event.relatedTarget) && draggedStepIndex !== null) {
      placeholder.style.display = "none";
    }
  });

  builder.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (draggedStepIndex === null) {
      return;
    }
    const cards = [...builder.querySelectorAll(".step-card")];
    if (!cards.length) {
      return;
    }
    const lastCard = cards[cards.length - 1];
    const rect = lastCard.getBoundingClientRect();
    if (event.clientY > rect.bottom) {
      dropPlaceholderIndex = cards.length;
      builder.appendChild(placeholder);
      placeholder.style.display = "";
    }
  });
}

  function setActiveTab(tabName) {
    document.querySelectorAll(".tab").forEach((tab) => {
      const active = tab.getAttribute("data-tab") === tabName;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
  });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.getAttribute("data-panel") === tabName);
    });
  }

  function setActiveMonitorTab(tabName) {
    document.querySelectorAll(".monitor-tab").forEach((tab) => {
      const active = tab.getAttribute("data-monitor-tab") === tabName;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".monitor-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.getAttribute("data-monitor-panel") === tabName);
    });
  }

  function getInitialQueryState() {
    const params = new URLSearchParams(window.location.search);
    const workflowId = Number(params.get("run_workflow_id"));
    const versionId = Number(params.get("run_version_id"));
    const tab = params.get("tab");
    const returnToEditor = params.get("return_to_editor");
    const normalizedWorkflowId =
      Number.isFinite(workflowId) && workflowId > 0 ? workflowId : null;
    return {
      tab,
      workflowId: normalizedWorkflowId,
      versionId: Number.isFinite(versionId) && versionId > 0 ? versionId : null,
      returnToEditor:
        typeof returnToEditor === "string" && returnToEditor.startsWith("/ui/editor")
          ? returnToEditor
          : normalizedWorkflowId
            ? editorUrlFor(normalizedWorkflowId)
            : null,
    };
  }

function updateRunsBackLink(returnToEditor) {
  const backLink = $("runs-back-to-editor");
  if (!backLink) {
    return;
  }
  const workflowId = Number(($("run-workflow-id") || {}).value);
  const fallbackHref =
    Number.isFinite(workflowId) && workflowId > 0 ? editorUrlFor(workflowId) : null;
  const href = returnToEditor || fallbackHref;
  if (href) {
    backLink.href = href;
    backLink.hidden = false;
    return;
  }
  backLink.hidden = true;
}

function collectInputPaths(value, outputSet) {
  if (typeof value === "string") {
    const matches = value.matchAll(/\{\{\s*inputs\.([a-zA-Z0-9_.]+)\s*\}\}/g);
    for (const match of matches) {
      if (match[1]) {
        outputSet.add(match[1]);
      }
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectInputPaths(item, outputSet));
    return;
  }
  if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectInputPaths(item, outputSet));
  }
}

function setNestedValue(target, dottedPath, value) {
  const parts = dottedPath.split(".");
  let current = target;
  for (let i = 0; i < parts.length - 1; i += 1) {
    const part = parts[i];
    if (!current[part] || typeof current[part] !== "object") {
      current[part] = {};
    }
    current = current[part];
  }
  current[parts[parts.length - 1]] = value;
}

function updateRunControlsState() {
  const hasVersion = Number(($("run-version-id") || {}).value) > 0;
  const triggerBtn = $("btn-trigger-run");
  const generateBtn = $("btn-generate-run-inputs");
  if (triggerBtn) {
    triggerBtn.disabled = !hasVersion || Date.now() < runTriggerCooldownUntil;
  }
  if (generateBtn) {
    generateBtn.disabled = !hasVersion;
  }
  const loadPresetBtn = $("btn-load-run-preset");
  const deletePresetBtn = $("btn-delete-run-preset");
  const hasPreset = Number(($("run-preset-id") || {}).value) > 0;
  if (loadPresetBtn) {
    loadPresetBtn.disabled = !hasPreset;
  }
  if (deletePresetBtn) {
    deletePresetBtn.disabled = !hasPreset;
  }
  updateRunnerContext();
  updateRunJsonStatus();
}

function setRunTriggerButtonState({ label, disabled, cooldownMs = 0 } = {}) {
  const triggerBtn = $("btn-trigger-run");
  if (!triggerBtn) {
    return;
  }

  if (!triggerBtn.dataset.defaultLabel) {
    triggerBtn.dataset.defaultLabel = triggerBtn.textContent || "Trigger Run";
  }

  if (label) {
    triggerBtn.textContent = label;
  }

  if (cooldownMs > 0) {
    runTriggerCooldownUntil = Date.now() + cooldownMs;
    triggerBtn.disabled = true;
    window.setTimeout(() => {
      runTriggerCooldownUntil = 0;
      triggerBtn.textContent = triggerBtn.dataset.defaultLabel || "Trigger Run";
      updateRunControlsState();
    }, cooldownMs);
    return;
  }

  if (typeof disabled === "boolean") {
    triggerBtn.disabled = disabled;
  }
}

function updateRunnerContext() {
  const workflowId = Number(($("run-workflow-id") || {}).value);
  const versionId = Number(($("run-version-id") || {}).value);
  const el = $("runner-context");
  if (!el) {
    return;
  }
  if (workflowId && versionId) {
    el.textContent = `Workflow #${workflowId} - Version #${versionId}`;
  } else if (workflowId) {
    el.textContent = `Workflow #${workflowId} - Select a version`;
  } else {
    el.textContent = "Select a workflow and version.";
  }
}

function updateRunJsonStatus() {
  const el = $("run-json-status");
  const input = $("run-inputs");
  if (!el || !input) {
    return;
  }
  try {
    const parsed = JSON.parse(input.value || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Input variables must be a JSON object");
    }
    el.textContent = "Valid JSON";
    el.className = "json-status is-valid";
  } catch (err) {
    el.textContent = `Invalid JSON: ${err.message}`;
    el.className = "json-status is-invalid";
  }
}

function buildRunInputsPayload() {
  const inputs = JSON.parse(($("run-inputs") || {}).value || "{}");
  if (!inputs || typeof inputs !== "object" || Array.isArray(inputs)) {
    throw new Error("Input Variables JSON must be an object");
  }
  const browserMode = String(($("run-browser-mode") || {}).value || "");
  delete inputs.headless;
  delete inputs.headed;
  if (browserMode === "headless") {
    inputs.headless = true;
  } else if (browserMode === "headed") {
    inputs.headed = true;
  }
  const captureStepScreenshots = $("run-capture-step-screenshots");
  if (captureStepScreenshots) {
    inputs.capture_step_screenshots = captureStepScreenshots.checked;
  }
  return inputs;
}

function runPresetOption(preset) {
  const scope =
    preset.workflow_version_id
      ? `v:${preset.workflow_version_id}`
      : preset.workflow_id
        ? `wf:${preset.workflow_id}`
        : "global";
  return `<option value="${preset.id}">#${preset.id} ${preset.name} (${scope})</option>`;
}

async function refreshRunArgPresets() {
  const select = $("run-preset-id");
  if (!select) {
    return;
  }
  const workflowId = Number(($("run-workflow-id") || {}).value);
  const versionId = Number(($("run-version-id") || {}).value);
  let query = "";
  if (versionId) {
    query = `?workflow_version_id=${versionId}`;
  } else if (workflowId) {
    query = `?workflow_id=${workflowId}`;
  }
  const rows = await api(`/run-arg-presets${query}`);
  select.innerHTML = `<option value="">Select saved preset...</option>${rows
    .map(runPresetOption)
    .join("")}`;
  updateRunControlsState();
}

async function saveRunArgPreset(isNew = false) {
  const name = String(($("run-preset-name") || {}).value || "").trim();
  if (!name) {
    throw new Error("Preset name is required");
  }
  const inputs = buildRunInputsPayload();
  const workflowId = Number(($("run-workflow-id") || {}).value) || null;
  const versionId = Number(($("run-version-id") || {}).value) || null;
  const selectedPresetId = Number(($("run-preset-id") || {}).value) || null;
  const payload = {
    name,
    workflow_id: workflowId,
    workflow_version_id: versionId,
    inputs_json: inputs,
  };
  if (selectedPresetId && !isNew) {
    return api(`/run-arg-presets/${selectedPresetId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }
  return api("/run-arg-presets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function loadRunArgPreset() {
  const presetId = Number(($("run-preset-id") || {}).value);
  if (!presetId) {
    throw new Error("Select a preset first");
  }
  const presets = await api("/run-arg-presets");
  const preset = (presets || []).find((item) => Number(item.id) === presetId);
  if (!preset) {
    throw new Error("Preset not found");
  }
  $("run-inputs").value = JSON.stringify(preset.inputs_json || {}, null, 2);
  autoResizeTextarea($("run-inputs"), { minRows: 6, maxRows: 24 });
  updateRunJsonStatus();
  const captureStepScreenshots = $("run-capture-step-screenshots");
  if (captureStepScreenshots) {
    captureStepScreenshots.checked = Boolean(preset.inputs_json?.capture_step_screenshots);
  }
  setValueIfPresent("run-preset-name", preset.name || "");
}

async function deleteRunArgPreset() {
  const presetId = Number(($("run-preset-id") || {}).value);
  if (!presetId) {
    throw new Error("Select a preset first");
  }
  await api(`/run-arg-presets/${presetId}`, { method: "DELETE" });
}

async function generateRunInputsTemplate() {
  const versionId = Number(($("run-version-id") || {}).value);
  if (!versionId) {
    throw new Error("Enter Workflow Version ID first");
  }

  const version = await api(`/workflows/versions/${versionId}`);
  const definition = version.definition_json || {};
  const inputPaths = new Set();
  collectInputPaths(definition, inputPaths);

  const generated = {};
  [...inputPaths].sort().forEach((path) => {
    setNestedValue(generated, path, "");
  });
  $("run-inputs").value = JSON.stringify(generated, null, 2);
  autoResizeTextarea($("run-inputs"), { minRows: 6, maxRows: 24 });
  updateRunJsonStatus();
}

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = isError ? "error" : "ok";
  setTimeout(() => (el.className = ""), 2400);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderTroubleshootStructured(result) {
  const container = $("troubleshoot-structured");
  if (!container) {
    return;
  }
  const data = result?.analysis_structured || {};
  const fixes = Array.isArray(data.fixes) ? data.fixes : [];
  const fallbacks = Array.isArray(data.fallback_selectors) ? data.fallback_selectors : [];
  const checklist = Array.isArray(data.verification_checklist) ? data.verification_checklist : [];
  const correctedSteps = Array.isArray(data.corrected_steps) ? data.corrected_steps : [];

  container.innerHTML = `
    <h4>Root Cause</h4>
    <div>${escapeHtml(data.root_cause || "No root cause provided")}</div>
    <h4>Fix Suggestions</h4>
    <ul>${fixes.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No suggestions provided</li>"}</ul>
    <h4>Fallback Selectors</h4>
    <ul>${fallbacks.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No fallback selectors provided</li>"}</ul>
    <h4>Corrected Step JSON</h4>
    <pre>${escapeHtml(JSON.stringify(correctedSteps, null, 2))}</pre>
    <h4>Verification Checklist</h4>
    <ul>${checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No checklist provided</li>"}</ul>
  `;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText} :: ${body}`);
  }
  if (res.status === 204) {
    return null;
  }
  const text = await res.text();
  if (!text) {
    return null;
  }
  return JSON.parse(text);
}

async function checkApi() {
  try {
    const health = await api("/health");
    $("api-status").textContent = `API: ${health.status}`;
    $("api-status").classList.add("ok");
  } catch (err) {
    $("api-status").textContent = "API: offline";
    $("api-status").classList.add("error");
  }
}

async function loadCurrentUser() {
  try {
    const user = await api("/auth/me");
    const adminActions = $("dashboard-admin-actions");
    if (adminActions) {
      adminActions.hidden = String(user?.role || "") !== "admin";
    }
    return user;
  } catch (err) {
    if (String(err.message || "").startsWith("401 ")) {
      window.location.href = "/login";
      return null;
    }
    throw err;
  }
}

function ensureWorkflowLayout() {
  const workflowsPanel = document.querySelector('.tab-panel[data-panel="workflows"]');
  if (!workflowsPanel || workflowsPanel.dataset.workflowsEnhanced === "true") {
    return;
  }

  const sections = Array.from(workflowsPanel.querySelectorAll(":scope > section"));
  const createSection = sections.find((section) => section.querySelector("#create-workflow-panel"));
  const listSection = sections.find((section) => section.querySelector("#workflow-list"));
  if (!createSection || !listSection) {
    return;
  }

  const createPanel = createSection.querySelector("#create-workflow-panel");
  const createSummary = createPanel?.querySelector("summary");
  const createBody = createPanel?.querySelector(".create-workflow-body");
  const createButton = createPanel?.querySelector("#btn-create-workflow");
  const refreshButton = listSection.querySelector("#btn-refresh-workflows");
  const workflowList = listSection.querySelector("#workflow-list");
  const selectedWorkflowInput = listSection.querySelector("#selected-workflow-id");
  const editButton = listSection.querySelector("#btn-edit-workflow");
  const deleteButton = listSection.querySelector("#btn-delete-workflow");

  if (!createPanel || !createBody || !createButton || !refreshButton || !workflowList || !selectedWorkflowInput || !editButton || !deleteButton) {
    return;
  }

  if (createSummary) {
    createSummary.hidden = true;
  }

  const header = document.createElement("div");
  header.className = "workflows-header";
  header.innerHTML = `
    <div class="workflows-header-copy">
      <h2>Workflows</h2>
      <p class="hint">Manage workflow definitions and open the graph editor.</p>
    </div>
  `;

  const toolbar = document.createElement("div");
  toolbar.className = "workflows-toolbar";

  const openCreateButton = document.createElement("button");
  openCreateButton.id = "btn-open-create-workflow";
  openCreateButton.type = "button";
  openCreateButton.className = "btn-primary";
  openCreateButton.textContent = "+ New Workflow";

  refreshButton.classList.add("btn-secondary");
  toolbar.append(openCreateButton, refreshButton);
  header.appendChild(toolbar);

  const controls = document.createElement("div");
  controls.className = "workflow-controls";
  controls.innerHTML = '<input id="workflow-search" type="search" placeholder="Search workflows..." aria-label="Search workflows">';

  const listShell = document.createElement("div");
  listShell.className = "workflow-list-shell";
  workflowList.className = "workflow-table";
  listShell.appendChild(workflowList);

  const hiddenActions = document.createElement("div");
  hiddenActions.className = "workflow-selection-actions";
  hiddenActions.hidden = true;
  hiddenActions.append(editButton, deleteButton);

  createPanel.classList.add("workflow-create-panel");

  const card = document.createElement("section");
  card.className = "card card-primary workflows-card";
  card.append(header, createPanel, controls, listShell, selectedWorkflowInput, hiddenActions);

  workflowsPanel.replaceChildren(card);
  workflowsPanel.dataset.workflowsEnhanced = "true";
}

function openWorkflowCreatePanel() {
  const panel = $("create-workflow-panel");
  if (!panel) {
    return;
  }
  panel.open = true;
  const nameInput = $("wf-name");
  if (nameInput) {
    nameInput.focus();
  }
}

function formatWorkflowDateTime(value) {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return escapeHtml(value);
  }
  return escapeHtml(parsed.toLocaleString());
}

function workflowRow(wf) {
  return `
    <div class="workflow-row item clickable" data-workflow-id="${wf.id}" role="row" tabindex="0">
      <div class="workflow-cell workflow-cell-id" role="cell">#${escapeHtml(wf.id)}</div>
      <div class="workflow-cell workflow-cell-name" role="cell">${escapeHtml(wf.name || "(unnamed)")}</div>
      <div class="workflow-cell workflow-cell-status" role="cell">
        <span class="workflow-status-badge">${escapeHtml(wf.status || "unknown")}</span>
      </div>
      <div class="workflow-cell workflow-cell-created" role="cell">${formatWorkflowDateTime(wf.updated_at || wf.created_at || "")}</div>
      <div class="workflow-cell workflow-cell-actions" role="cell">
        <button type="button" class="btn-link-inline" data-action="edit" data-workflow-id="${wf.id}">Edit</button>
        <button type="button" class="btn-danger-outline" data-action="delete" data-workflow-id="${wf.id}">Delete</button>
      </div>
    </div>
  `;
}

function workflowOption(wf) {
  return `<option value="${wf.id}">#${wf.id} ${wf.name || "(unnamed)"}</option>`;
}

function setSelectedWorkflowListItem(workflowId) {
  document.querySelectorAll("#workflow-list .workflow-row").forEach((el) => {
    const rowWorkflowId = Number(el.getAttribute("data-workflow-id"));
    el.classList.toggle("is-selected", rowWorkflowId === workflowId);
  });
}

function renderWorkflowList() {
  const workflowListEl = $("workflow-list");
  if (!workflowListEl) {
    return;
  }

  const searchValue = String(($("workflow-search") || {}).value || "").trim().toLowerCase();
  const filteredWorkflows = currentWorkflows.filter((wf) => {
    if (!searchValue) {
      return true;
    }
    const haystack = [wf.id, wf.name || "", wf.status || ""].join(" ").toLowerCase();
    return haystack.includes(searchValue);
  });

  if (!filteredWorkflows.length) {
    workflowListEl.innerHTML = searchValue
      ? '<div class="workflow-empty muted">No workflows match your search.</div>'
      : '<div class="workflow-empty muted">No workflows yet.</div>';
    return;
  }

  workflowListEl.innerHTML = `
    <div class="workflow-table-head" role="rowgroup">
      <div class="workflow-row workflow-row-head" role="row">
        <div class="workflow-cell workflow-cell-id" role="columnheader">ID</div>
        <div class="workflow-cell workflow-cell-name" role="columnheader">Workflow name</div>
        <div class="workflow-cell workflow-cell-status" role="columnheader">Status</div>
        <div class="workflow-cell workflow-cell-created" role="columnheader">Updated</div>
        <div class="workflow-cell workflow-cell-actions" role="columnheader">Actions</div>
      </div>
    </div>
    <div class="workflow-table-body" role="rowgroup">
      ${filteredWorkflows.map(workflowRow).join("")}
    </div>
  `;

  const selectedWorkflowId = Number(($("selected-workflow-id") || {}).value || 0);
  setSelectedWorkflowListItem(selectedWorkflowId || null);
}

function goToWorkflowEditor(workflowId) {
  if (!workflowId) {
    toast("Load a workflow first", true);
    return;
  }
  window.location.href = editorUrlFor(workflowId);
}

async function selectWorkflow(workflowId) {
  if (!workflowId) {
    return;
  }

  setValueIfPresent("selected-workflow-id", workflowId);
  setValueIfPresent("run-workflow-id", workflowId);
  setValueIfPresent("editor-workflow-id", workflowId);
  setSelectedWorkflowListItem(workflowId);

  const shouldLoadDetails = Boolean($("selected-workflow-id") && $("workflow-details"));
  if (shouldLoadDetails) {
    await loadWorkflowDetails(workflowId);
    return;
  }

  await refreshRunVersionsForWorkflow(workflowId, null);
}

async function deleteWorkflowById(workflowId) {
  if (!workflowId) {
    throw new Error("Select a workflow first");
  }

  const workflow = currentWorkflows.find((item) => Number(item.id) === Number(workflowId));
  const label = workflow?.name ? `${workflow.name} (#${workflow.id})` : `workflow #${workflowId}`;
  if (!window.confirm(`Delete ${label}? This will mark it inactive.`)) {
    return false;
  }

  await api(`/workflows/${workflowId}`, { method: "DELETE" });
  setValueIfPresent("editor-workflow-id", "");
  setValueIfPresent("selected-workflow-id", "");
  setValueIfPresent("ver-workflow-id", "");
  setValueIfPresent("ver-current-version-id", "");
  if ($("ver-revision-id")) {
    setValueIfPresent("ver-revision-id", "");
  }
  currentWorkflowVersions = [];
  populateRevisionDropdown([]);
  updateWorkflowInfoPanel(null, null);
  updateVersionPrimaryActions();
  setValueIfPresent("run-workflow-id", "");
  setValueIfPresent("run-version-id", "");
  clearRunMonitorPreview();
  setSelectedWorkflowListItem(null);
  if ($("workflow-details")) {
    $("workflow-details").textContent = "";
  }
  updateCurrentWorkflowIndicator(null);
  await refreshWorkflows();
  toast(`Workflow #${workflowId} set to inactive`);
  return true;
}

function templateRow(tpl) {
  return `<div class="item clickable" data-template-id="${tpl.id}" data-template-name="${tpl.name || "Template"}">
    <div><strong>#${tpl.id}</strong> ${tpl.name || "(unnamed template)"}</div>
    <div class="muted">key=${tpl.key || ""} category=${tpl.category || ""}</div>
  </div>`;
}

async function refreshWorkflows() {
  const items = await api("/workflows?active_only=true");
  currentWorkflows = Array.isArray(items) ? items : [];
  renderWorkflowList();

  const runWorkflowSelect = $("run-workflow-id");
  const editorWorkflowSelect = $("editor-workflow-id");
  if (runWorkflowSelect) {
    const currentValue = runWorkflowSelect.value;
    runWorkflowSelect.innerHTML = `<option value="">Select workflow...</option>${currentWorkflows.map(workflowOption).join("")}`;
    if (currentValue && currentWorkflows.some((item) => String(item.id) === String(currentValue))) {
      runWorkflowSelect.value = currentValue;
    }
  }
  if (editorWorkflowSelect) {
    const currentValue = editorWorkflowSelect.value;
    editorWorkflowSelect.innerHTML = `<option value="">Select workflow...</option>${currentWorkflows.map(workflowOption).join("")}`;
    if (currentValue && currentWorkflows.some((item) => String(item.id) === String(currentValue))) {
      editorWorkflowSelect.value = currentValue;
    }
  }

  updateRunControlsState();

  const selectedId = Number(($("selected-workflow-id") || {}).value || 0);
  if (selectedId && !currentWorkflows.some((item) => Number(item.id) === selectedId)) {
    setValueIfPresent("selected-workflow-id", "");
  }
  setSelectedWorkflowListItem(Number(($("selected-workflow-id") || {}).value || 0) || null);
}

async function refreshRunVersionsForWorkflow(workflowId, preferredVersionId = null) {
    const runVersionSelect = $("run-version-id");
    if (!runVersionSelect) {
      return;
    }
  if (!workflowId) {
    runVersionSelect.innerHTML = `<option value="">Select version...</option>`;
    updateRunControlsState();
    await refreshRunArgPresets();
    return;
  }

  const versions = await api(`/workflows/${workflowId}/versions`);
  runVersionSelect.innerHTML = versions.length
    ? versions
        .map(
          (v) =>
            `<option value="${v.id}">v${v.version_number} (${v.is_published ? "published" : "draft"}) - id ${v.id}</option>`
        )
        .join("")
    : `<option value="">No versions found</option>`;
  updateRunControlsState();

    if (versions.length) {
      const selectedVersion = preferredVersionId && versions.some((version) => version.id === preferredVersionId)
        ? preferredVersionId
        : versions[0].id;
      runVersionSelect.value = String(selectedVersion);
      updateRunControlsState();
      try {
        await generateRunInputsTemplate();
      } catch (_err) {
      // keep UI usable even if template generation fails
    }
  }
  await refreshRunArgPresets();
}

function clearRunMonitorPreview() {
  stopRunMonitorPolling();
  if ($("monitor-run-id")) {
    $("monitor-run-id").value = "";
  }
    if ($("run-details")) {
      $("run-details").textContent = "";
    }
    if ($("run-summary")) {
      $("run-summary").innerHTML = "<div class='muted'>Load a run to see the summary.</div>";
    }
    if ($("run-failure-banner")) {
      $("run-failure-banner").style.display = "none";
      $("run-failure-banner").innerHTML = "";
    }
    if ($("step-details")) {
      $("step-details").textContent = "";
    }
    if ($("step-summary")) {
      $("step-summary").innerHTML = "<div class='muted'>Load a run to see step results.</div>";
    }
    if ($("run-artifacts")) {
      $("run-artifacts").innerHTML = "<div class='muted'>Load a run to see artifacts.</div>";
    }
  }

  function formatDateTime(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString();
  }

  function statusClass(status) {
    const normalized = String(status || "").toLowerCase();
    if (["passed", "completed", "success"].includes(normalized)) {
      return "is-passed";
    }
    if (["failed", "error"].includes(normalized)) {
      return "is-failed";
    }
    if (["cancelled", "canceled"].includes(normalized)) {
      return "is-cancelled";
    }
    if (["running", "queued"].includes(normalized)) {
      return "is-running";
    }
    return "";
  }

function statusBadge(status) {
  const label = String(status || "unknown");
  return `<span class="status-pill ${statusClass(label)}">${escapeHtml(label)}</span>`;
}

let stepMonitorFilter = "all";
let stepMonitorSearch = "";

function normalizedStepStatus(step) {
  return String(step?.status || "unknown").toLowerCase();
}

function stepSearchText(step) {
  return [
    Number(step.step_index) + 1,
    step.step_type,
    formatStepArgs(step.args_json),
    step.step_id,
    step.status,
    step.error_text,
    step.log_text,
  ].filter((value) => value !== undefined && value !== null).join(" ").toLowerCase();
}

function bindStepMonitorControls(container) {
  container.querySelectorAll("[data-step-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      stepMonitorFilter = button.getAttribute("data-step-filter") || "all";
      applyStepFilters(container);
    });
  });

  const search = container.querySelector("[data-step-search]");
  if (search) {
    search.addEventListener("input", () => {
      stepMonitorSearch = search.value || "";
      applyStepFilters(container);
    });
  }

  const list = container.querySelector("[data-step-list]");
  container.querySelector("[data-step-action='collapse-all']")?.addEventListener("click", () => {
    list?.querySelectorAll(".step-result[open]").forEach((step) => {
      step.open = false;
    });
  });
  container.querySelector("[data-step-action='expand-failed']")?.addEventListener("click", () => {
    list?.querySelectorAll(".step-result[data-step-status='failed']").forEach((step) => {
      step.open = true;
    });
  });
  container.querySelector("[data-step-action='jump-failed']")?.addEventListener("click", () => {
    const failed = list?.querySelector(".step-result[data-step-status='failed']:not([hidden])")
      || list?.querySelector(".step-result[data-step-status='failed']");
    if (!failed) {
      toast("No failed steps found", true);
      return;
    }
    failed.open = true;
    failed.scrollIntoView({ behavior: "smooth", block: "center" });
    failed.classList.add("is-jump-target");
    setTimeout(() => failed.classList.remove("is-jump-target"), 1400);
  });
}

function applyStepFilters(container) {
  const search = stepMonitorSearch.trim().toLowerCase();
  const rows = [...container.querySelectorAll(".step-result")];
  let visible = 0;

  rows.forEach((row) => {
    const status = row.dataset.stepStatus || "";
    const statusMatches = stepMonitorFilter === "all" || status === stepMonitorFilter;
    const searchMatches = !search || (row.dataset.searchText || "").includes(search);
    const show = statusMatches && searchMatches;
    row.hidden = !show;
    if (show) visible += 1;
  });

  container.querySelectorAll("[data-step-filter]").forEach((button) => {
    const active = button.getAttribute("data-step-filter") === stepMonitorFilter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });

  const empty = container.querySelector("[data-step-empty]");
  if (empty) {
    empty.hidden = visible > 0;
  }
}

  function renderRunSummary(run, steps) {
    const container = $("run-summary");
    if (!container) {
      return;
    }
    const total = steps.length;
    const passed = steps.filter((step) => step.status === "passed").length;
    const failed = steps.filter((step) => step.status === "failed").length;
  const inputs = run.inputs_json && Object.keys(run.inputs_json).length
    ? Object.keys(run.inputs_json).join(", ")
    : "None";
  const activeNote = isActiveRunStatus(run.status)
    ? "<span class=\"run-live-note\">Auto-refreshing while run is active</span>"
    : "";
  const stopAction = isActiveRunStatus(run.status)
    ? `<button id="btn-stop-run" type="button" class="btn-danger btn-sm">Stop Run</button>`
    : "";
  container.innerHTML = `
    <div class="run-summary-bar">
      <div class="run-summary-main">
          ${statusBadge(run.status)}
          <strong>Run #${escapeHtml(run.id)}</strong>
          <span>Workflow #${escapeHtml(run.workflow_id)}</span>
          <span>Version #${escapeHtml(run.workflow_version_id)}</span>
        </div>
        <div class="run-summary-meta">
          <span>${total} steps</span>
          <span>${passed} passed</span>
          <span>${failed} failed</span>
          <span>Started ${escapeHtml(formatDateTime(run.started_at))}</span>
        <span>Finished ${escapeHtml(formatDateTime(run.finished_at))}</span>
        <span>Inputs: ${escapeHtml(inputs)}</span>
        ${activeNote}
      </div>
      <div class="run-summary-actions">${stopAction}</div>
    </div>
  `;
  container.querySelector("#btn-stop-run")?.addEventListener("click", async () => {
    try {
      await api(`/workflow-runs/${run.id}/stop`, { method: "POST" });
      toast(`Stop requested for run #${run.id}`);
      await loadRunMonitor(run.id);
    } catch (err) {
      toast(err.message, true);
    }
  });
}

  function renderFailureBanner(run, steps) {
    const container = $("run-failure-banner");
    if (!container) {
      return;
    }
    const failedStep = steps.find((step) => step.status === "failed");
    if (run.status !== "failed" && !failedStep && !run.error_summary) {
      container.style.display = "none";
      container.innerHTML = "";
      return;
    }
    const stepLabel = failedStep
      ? `Run failed at Step ${Number(failedStep.step_index) + 1}: ${failedStep.step_type}`
      : "Run failed";
    const target = failedStep ? formatStepArgs(failedStep.args_json) : "-";
    const rawError = failedStep?.error_text || run.error_summary || "No error message recorded.";
    const reason = rawError.split(/\r?\n/)[0].slice(0, 240);
    container.innerHTML = `
      <strong>${escapeHtml(stepLabel)}</strong>
      <div>Target: ${escapeHtml(target)}</div>
      <div>Reason: ${escapeHtml(reason)}</div>
      <small>${escapeHtml(rawError)}</small>
    `;
    container.style.display = "";
  }

  function formatStepArgs(args) {
    if (!args || typeof args !== "object") {
      return "-";
    }
    if (typeof args.url === "string") {
      return args.url;
    }
    if (typeof args.text === "string") {
      return args.text;
    }
    if (typeof args.value === "string") {
      return args.value;
    }
    if (args.target && typeof args.target === "object") {
      const target = args.target;
      return target.name || target.label || target.text || target.selector || target.strategy || "-";
    }
    return JSON.stringify(args).slice(0, 160);
  }

function renderStepSummary(steps) {
  const container = $("step-summary");
  if (!container) {
    return;
  }
  if (!steps.length) {
    container.innerHTML = "<div class='muted'>No step logs recorded for this run.</div>";
    return;
  }

  const counts = steps.reduce((summary, step) => {
    const status = normalizedStepStatus(step);
    summary.total += 1;
    summary[status] = (summary[status] || 0) + 1;
    return summary;
  }, { total: 0 });
  const filterStatuses = ["all", "failed", "passed", "running", "skipped", "warning"]
    .filter((status) => ["all", "failed", "passed"].includes(status) || counts[status]);
  const countSummary = `${counts.total} steps • ${counts.passed || 0} passed • ${counts.failed || 0} failed`;
  const filters = filterStatuses.map((status) => `
    <button type="button" class="step-filter ${status === stepMonitorFilter ? "is-active" : ""}" data-step-filter="${status}" aria-pressed="${status === stepMonitorFilter ? "true" : "false"}">
      ${escapeHtml(status.charAt(0).toUpperCase() + status.slice(1))}
    </button>
  `).join("");
  const rows = steps.map((step) => {
    const status = normalizedStepStatus(step);
    const target = formatStepArgs(step.args_json);
    const stepNumber = Number(step.step_index) + 1;
    const searchText = escapeHtml(stepSearchText(step));
    return `
      <details
        class="step-result ${statusClass(step.status)}"
        ${status === "failed" ? "open" : ""}
        data-step-status="${escapeHtml(status)}"
        data-step-name="${escapeHtml(step.step_type || "")}"
        data-step-target="${escapeHtml(target)}"
        data-node-id="${escapeHtml(step.step_id || "")}"
        data-error="${escapeHtml(step.error_text || "")}"
        data-search-text="${searchText}"
      >
        <summary class="step-result-header">
          <div class="step-result-title">
            <strong>Step ${stepNumber}: ${escapeHtml(step.step_type)}</strong>
            <small>${step.step_id ? `Node ${escapeHtml(step.step_id)}` : "No node ID"}</small>
          </div>
          ${statusBadge(step.status)}
        </summary>
        <div class="step-result-body">
          <div><span>Target/Input</span><strong>${escapeHtml(target)}</strong></div>
          <div><span>Node ID</span><strong>${step.step_id ? escapeHtml(step.step_id) : "None"}</strong></div>
          <div><span>Started</span><strong>${escapeHtml(formatDateTime(step.started_at))}</strong></div>
          <div><span>Finished</span><strong>${escapeHtml(formatDateTime(step.finished_at))}</strong></div>
        </div>
        ${step.log_text ? `<p class="step-log">${escapeHtml(step.log_text)}</p>` : ""}
        ${step.error_text ? `<p class="step-error">${escapeHtml(step.error_text)}</p>` : ""}
      </details>
    `;
  }).join("");

  container.innerHTML = `
    <div class="steps-toolbar" aria-label="Step controls">
      <div class="steps-toolbar-summary">${escapeHtml(countSummary)}</div>
      <div class="steps-toolbar-controls">
        <div class="step-filter-group" aria-label="Step status filters">${filters}</div>
        <input class="step-search" type="search" data-step-search placeholder="Search steps, targets, node IDs, errors..." value="${escapeHtml(stepMonitorSearch)}">
        <div class="step-actions">
          <button type="button" class="btn-secondary btn-sm" data-step-action="collapse-all">Collapse all</button>
          <button type="button" class="btn-secondary btn-sm" data-step-action="expand-failed">Expand failed</button>
          <button type="button" class="btn-secondary btn-sm" data-step-action="jump-failed">Jump to failed</button>
        </div>
      </div>
    </div>
    <div class="step-list-scroll" data-step-list>${rows}</div>
    <div class="step-empty-state" data-step-empty hidden>No steps match this filter.</div>
  `;
  bindStepMonitorControls(container);
  applyStepFilters(container);
}

  function artifactLabel(artifact) {
    const labels = {
      trace: "Trace",
      final_screenshot: "Final screenshot",
      failure_screenshot: "Failure screenshot",
      step_screenshot: "Step screenshot",
      video: "Video",
      console_log: "Console log",
      network_log: "Network log",
    };
    return labels[artifact.artifact_type] || artifact.artifact_type;
  }

  function artifactActionLabel(artifact) {
    if (artifact.artifact_type === "trace") {
      return "Open trace";
    }
    if (String(artifact.mime_type || "").startsWith("image/")) {
      return "Open image";
    }
    if (String(artifact.mime_type || "").startsWith("video/")) {
      return "Open video";
    }
    return "Download";
  }

  function artifactLink(artifact) {
    const sizeKb = Math.max(1, Math.round(Number(artifact.size_bytes || 0) / 1024));
    const isTrace = artifact.artifact_type === "trace";
    const actionHtml = isTrace
      ? `
        <button class="btn-secondary btn-sm" type="button" data-action="open-trace" data-run-id="${Number(artifact.workflow_run_id)}" data-artifact-id="${Number(artifact.id)}">
          ${escapeHtml(artifactActionLabel(artifact))}
        </button>
        <a class="btn-secondary btn-sm" href="${escapeHtml(artifact.download_url)}" target="_blank" rel="noopener">Download</a>
      `
      : `
        <a class="btn-secondary btn-sm" href="${escapeHtml(artifact.download_url)}" target="_blank" rel="noopener">
          ${escapeHtml(artifactActionLabel(artifact))}
        </a>
      `;
    return `
      <div class="artifact-item">
        <div>
          <strong>${escapeHtml(artifactLabel(artifact))}</strong>
          <small>${escapeHtml(artifact.mime_type || "application/octet-stream")} · ${sizeKb} KB</small>
        </div>
        <div class="artifact-actions">${actionHtml}</div>
      </div>
    `;
  }

  function bindArtifactActions(container) {
    container.querySelectorAll("[data-action='open-trace']").forEach((button) => {
      button.addEventListener("click", async () => {
        const runId = Number(button.getAttribute("data-run-id"));
        const artifactId = Number(button.getAttribute("data-artifact-id"));
        if (!runId || !artifactId) {
          toast("Trace artifact is missing an ID", true);
          return;
        }
        button.disabled = true;
        try {
          await api(`/workflow-runs/${runId}/artifacts/${artifactId}/open-trace`, { method: "POST" });
          toast("Trace viewer opened");
        } catch (err) {
          toast(err.message, true);
        } finally {
          button.disabled = false;
        }
      });
    });
  }

function renderRunArtifacts(artifacts, steps = []) {
    const container = $("run-artifacts");
    if (!container) {
      return;
    }
    if (!artifacts.length) {
      container.innerHTML = "<div class='muted'>No artifacts captured for this run.</div>";
      return;
    }
    const runArtifacts = artifacts.filter((artifact) => !artifact.step_run_id);
    const stepArtifacts = artifacts.filter((artifact) => artifact.step_run_id);
    const stepById = new Map(steps.map((step) => [Number(step.id), step]));
    const groups = new Map();
    for (const artifact of stepArtifacts) {
      const key = Number(artifact.step_run_id);
      groups.set(key, [...(groups.get(key) || []), artifact]);
    }
    const runHtml = runArtifacts.length
      ? `<div class="artifact-group"><h4>Run artifacts</h4>${runArtifacts.map(artifactLink).join("")}</div>`
      : "";
    const stepHtml = [...groups].map(([stepRunId, items]) => {
      const step = stepById.get(stepRunId);
      const label = step
        ? `Step ${Number(step.step_index) + 1}: ${step.step_type}`
        : `Step run #${stepRunId}`;
      return `<div class="artifact-group"><h4>${escapeHtml(label)}</h4>${items.map(artifactLink).join("")}</div>`;
    }).join("");
    container.innerHTML = runHtml + stepHtml;
  bindArtifactActions(container);
}

let runMonitorPollTimer = null;
let runMonitorPollingRunId = null;

function isActiveRunStatus(status) {
  return ["queued", "running"].includes(String(status || "").toLowerCase());
}

function stopRunMonitorPolling() {
  if (runMonitorPollTimer) {
    window.clearTimeout(runMonitorPollTimer);
  }
  runMonitorPollTimer = null;
  runMonitorPollingRunId = null;
}

function scheduleRunMonitorPoll(runId) {
  stopRunMonitorPolling();
  runMonitorPollingRunId = runId;
  runMonitorPollTimer = window.setTimeout(async () => {
    try {
      const result = await loadRunMonitor(runId, { autoPoll: true });
      if (isActiveRunStatus(result?.run?.status) && runMonitorPollingRunId === runId) {
        scheduleRunMonitorPoll(runId);
      } else {
        stopRunMonitorPolling();
      }
    } catch (err) {
      toast(err.message, true);
      stopRunMonitorPolling();
    }
  }, 2500);
}

async function loadRunMonitor(runId, options = {}) {
  const run = await api(`/workflow-runs/${runId}`);
  const steps = await api(`/workflow-runs/${runId}/steps`);
  const artifacts = await api(`/workflow-runs/${runId}/artifacts`);
    renderRunSummary(run, steps || []);
    renderFailureBanner(run, steps || []);
    renderStepSummary(steps || []);
    $("run-details").textContent = JSON.stringify(run, null, 2);
  $("step-details").textContent = JSON.stringify(steps, null, 2);
  renderRunArtifacts(artifacts || [], steps || []);
  if (!options.autoPoll) {
    if (isActiveRunStatus(run.status)) {
      scheduleRunMonitorPoll(runId);
    } else {
      stopRunMonitorPolling();
    }
  }
  return { run, steps, artifacts };
}

async function refreshTemplates() {
  const items = await api("/workflow-templates");
  $("template-list").innerHTML = items.length ? items.map(templateRow).join("") : "<div class='muted'>No templates yet.</div>";
  document.querySelectorAll("#template-list .item.clickable").forEach((el) => {
    el.addEventListener("click", () => {
      const templateId = Number(el.getAttribute("data-template-id"));
      $("tpl-id").value = templateId;
      if (!$("tpl-workflow-name").value.trim()) {
        const name = el.getAttribute("data-template-name") || "Template";
        $("tpl-workflow-name").value = `Imported ${name}`;
      }
    });
  });
}

async function loadWorkflowDetails(workflowId) {
  if (!$("selected-workflow-id") || !$("workflow-details")) {
    return;
  }
  const workflow = await api(`/workflows/${workflowId}`);
  const versions = await api(`/workflows/${workflowId}/versions`);
  currentWorkflowVersions = versions;
  const latestVersion = versions.length ? versions[0] : null;
  $("selected-workflow-id").value = workflowId;
  setSelectedWorkflowListItem(workflowId);
  $("workflow-details").textContent = JSON.stringify(workflow, null, 2);
  if ($("workflow-versions")) {
    $("workflow-versions").textContent = JSON.stringify(versions, null, 2);
  }
  setValueIfPresent("ver-workflow-id", workflowId);
  setValueIfPresent("run-workflow-id", workflowId);
  if (latestVersion) {
    populateRevisionDropdown(versions, latestVersion.id);
    loadVersionIntoEditor(latestVersion, workflowId);
    await refreshRunVersionsForWorkflow(workflowId, latestVersion.id);
  } else {
    populateRevisionDropdown([]);
    setValueIfPresent("ver-current-version-id", "");
    if ($("ver-definition")) {
      $("ver-definition").value = JSON.stringify(defaultDefinition, null, 2);
      autoResizeTextarea($("ver-definition"), { minRows: 12, maxRows: 70 });
    }
    if ($("ver-revision-id")) {
      setValueIfPresent("ver-revision-id", "");
    }
    if ($("ver-published")) {
      $("ver-published").checked = true;
    }
    updateWorkflowInfoPanel(null, workflowId);
    if ($("step-builder")) {
      syncStepsFromJson();
    }
    await refreshRunVersionsForWorkflow(workflowId, null);
  }
  updateCurrentWorkflowIndicator(workflow);
}

ensureWorkflowLayout();
const workflowListElement = $("workflow-list");
if (workflowListElement && !workflowListElement.dataset.bound) {
  workflowListElement.dataset.bound = "true";
  workflowListElement.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-action][data-workflow-id]");
    if (actionButton) {
      const workflowId = Number(actionButton.getAttribute("data-workflow-id"));
      if (actionButton.getAttribute("data-action") === "edit") {
        goToWorkflowEditor(workflowId);
      }
      if (actionButton.getAttribute("data-action") === "delete") {
        try {
          await deleteWorkflowById(workflowId);
        } catch (err) {
          toast(err.message, true);
        }
      }
      return;
    }

    const row = event.target.closest(".workflow-row[data-workflow-id]");
    if (!row) {
      return;
    }
    const workflowId = Number(row.getAttribute("data-workflow-id"));
    try {
      await selectWorkflow(workflowId);
    } catch (err) {
      toast(err.message, true);
    }
  });
  workflowListElement.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    const row = event.target.closest(".workflow-row[data-workflow-id]");
    if (!row) {
      return;
    }
    event.preventDefault();
    try {
      await selectWorkflow(Number(row.getAttribute("data-workflow-id")));
    } catch (err) {
      toast(err.message, true);
    }
  });
}
const workflowSearchInput = $("workflow-search");
if (workflowSearchInput && !workflowSearchInput.dataset.bound) {
  workflowSearchInput.dataset.bound = "true";
  workflowSearchInput.addEventListener("input", () => renderWorkflowList());
}
on("btn-open-create-workflow", "click", () => {
  openWorkflowCreatePanel();
});

on("btn-create-workflow", "click", async () => {
  try {
    const payload = {
      name: $("wf-name").value.trim(),
      description: $("wf-description").value.trim() || null,
      status: $("wf-status").value.trim() || "active",
    };
    const created = await api("/workflows", { method: "POST", body: JSON.stringify(payload) });
    toast(`Workflow created: #${created.id}`);
    setValueIfPresent("ver-workflow-id", created.id);
    setValueIfPresent("selected-workflow-id", created.id);
    setValueIfPresent("editor-workflow-id", created.id);
    if ($("ver-definition")) {
      $("ver-definition").value = JSON.stringify(defaultDefinition, null, 2);
      autoResizeTextarea($("ver-definition"), { minRows: 12, maxRows: 70 });
    }
    setValueIfPresent("ver-current-version-id", "");
    populateRevisionDropdown([]);
    if ($("ver-revision-id")) {
      setValueIfPresent("ver-revision-id", "");
    }
    updateVersionPrimaryActions();
    if ($("step-builder")) {
      syncStepsFromJson();
    }
    await refreshWorkflows();
    setValueIfPresent("editor-workflow-id", created.id);
    await loadWorkflowDetails(created.id);
    clearRunMonitorPreview();
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-refresh-workflows", "click", async () => {
  try {
    await refreshWorkflows();
    toast("Workflows refreshed");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-seed-templates", "click", async () => {
  try {
    const seeded = await api("/workflow-templates/seed-defaults", { method: "POST" });
    await refreshTemplates();
    toast(`Seeded templates: ${seeded.length}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-refresh-templates", "click", async () => {
  try {
    await refreshTemplates();
    toast("Templates refreshed");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-import-template", "click", async () => {
  try {
    const templateId = Number($("tpl-id").value);
    const payload = {
      workflow_name: $("tpl-workflow-name").value.trim(),
      workflow_description: $("tpl-workflow-description").value.trim() || null,
      workflow_status: $("tpl-workflow-status").value.trim() || "active",
      version_number: Number($("tpl-version-number").value),
      is_published: $("tpl-published").checked,
    };
    const imported = await api(`/workflow-templates/${templateId}/import`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("template-import-result").textContent = JSON.stringify(imported, null, 2);
    setValueIfPresent("selected-workflow-id", imported.workflow.id);
    setValueIfPresent("ver-workflow-id", imported.workflow.id);
    setValueIfPresent("run-workflow-id", imported.workflow.id);
    setValueIfPresent("run-version-id", imported.version.id);
    await refreshWorkflows();
    await loadWorkflowDetails(imported.workflow.id);
    clearRunMonitorPreview();
    toast(`Imported template #${templateId} -> workflow #${imported.workflow.id}`);
    setActiveTab("workflows");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-load-workflow", "click", async () => {
  try {
    const workflowId = Number($("selected-workflow-id").value);
    await loadWorkflowDetails(workflowId);
    toast(`Loaded workflow #${workflowId}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-edit-workflow", "click", (event) => {
  const workflowId = Number(($("selected-workflow-id") || {}).value);
  if (!workflowId) {
    event.preventDefault();
    toast("Load a workflow first", true);
    return;
  }
  goToWorkflowEditor(workflowId);
});

  on("btn-delete-workflow", "click", async () => {
  try {
    const workflowId = Number(($("editor-workflow-id") || $("selected-workflow-id") || {}).value);
    await deleteWorkflowById(workflowId);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-create-version", "click", async () => {
  try {
    const workflowId = Number($("ver-workflow-id").value);
    const currentVersionId = Number(($("ver-current-version-id") || {}).value);
    if (!workflowId || !currentVersionId) {
      throw new Error("Load a workflow version first before creating the next version");
    }
    syncJsonFromSteps();
    const definition = JSON.parse($("ver-definition").value);
    const nextRevision =
      Math.max(0, ...currentWorkflowVersions.map((v) => Number(v.version_number) || 0)) + 1;
    const payload = {
      version_number: nextRevision,
      is_published: $("ver-published").checked,
      definition_json: definition,
    };
    const created = await api(`/workflows/${workflowId}/versions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(`Created next version: #${created.id}`);
    currentWorkflowVersions = [created, ...currentWorkflowVersions];
    currentWorkflowVersions.sort(
      (a, b) => Number(b.version_number || 0) - Number(a.version_number || 0)
    );
    populateRevisionDropdown(currentWorkflowVersions, created.id);
    loadVersionIntoEditor(created, workflowId);
    if ($("run-version-id")) {
      $("run-version-id").value = created.id;
    }
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-save-version", "click", async () => {
  try {
    const versionId = Number(($("ver-current-version-id") || {}).value);
    if (!versionId) {
      throw new Error("No current version selected to save");
    }
    syncJsonFromSteps();
    const definition = JSON.parse($("ver-definition").value);
    const payload = {
      is_published: Boolean(($("ver-published") || {}).checked),
      definition_json: definition,
    };
    const updated = await api(`/workflows/versions/${versionId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    toast(`Saved current version: #${updated.id}`);
    updateVersionPrimaryActions();
    const idx = currentWorkflowVersions.findIndex((item) => Number(item.id) === Number(updated.id));
    if (idx >= 0) {
      currentWorkflowVersions[idx] = { ...currentWorkflowVersions[idx], ...updated };
    }
    loadVersionIntoEditor(updated, Number(($("ver-workflow-id") || {}).value) || null);
    const workflowId = Number(($("ver-workflow-id") || {}).value);
    if (workflowId) {
      populateRevisionDropdown(currentWorkflowVersions, updated.id);
      if ($("workflow-versions")) {
        $("workflow-versions").textContent = JSON.stringify(currentWorkflowVersions, null, 2);
      }
    }
  } catch (err) {
    toast(err.message, true);
  }
});

on("ver-revision-id", "change", async () => {
  try {
    const versionId = Number(($("ver-revision-id") || {}).value);
    const workflowId = Number(($("ver-workflow-id") || {}).value);
    if (!versionId || !workflowId) {
      return;
    }
    const local = currentWorkflowVersions.find((v) => Number(v.id) === versionId);
    if (local) {
      loadVersionIntoEditor(local, workflowId);
      return;
    }
    const version = await api(`/workflows/versions/${versionId}`);
    loadVersionIntoEditor(version, workflowId);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-add-step", "click", () => {
  const stepType = $("step-type-select").value;
  editorSteps.push({
    type: stepType,
    args: getDefaultArgsForStepType(stepType),
  });
  syncJsonFromSteps();
  renderStepBuilder();
});

on("btn-sync-from-json", "click", () => {
  try {
    syncStepsFromJson();
    toast("Loaded steps from JSON");
  } catch (err) {
    toast(`Invalid workflow JSON: ${err.message}`, true);
  }
});

on("btn-expand-all-steps", "click", () => {
  const builder = $("step-builder");
  if (!builder) {
    return;
  }
  builder.querySelectorAll(".step-collapse").forEach((el) => {
    el.open = true;
  });
});

on("btn-retract-all-steps", "click", () => {
  const builder = $("step-builder");
  if (!builder) {
    return;
  }
  builder.querySelectorAll(".step-collapse").forEach((el) => {
    el.open = false;
  });
});

on("ver-definition", "change", () => {
  try {
    syncStepsFromJson();
  } catch (err) {
    toast(`Invalid workflow JSON: ${err.message}`, true);
  }
});

on("btn-trigger-run", "click", async () => {
  try {
    setRunTriggerButtonState({ label: "Starting run...", disabled: true });
    const payload = {
      workflow_version_id: Number($("run-version-id").value),
      inputs: buildRunInputsPayload(),
    };
    const run = await api("/workflow-runs", { method: "POST", body: JSON.stringify(payload) });
    $("run-created").textContent = `Created run #${run.id} status=${run.status}`;
    $("monitor-run-id").value = run.id;
    await loadRunMonitor(run.id);
    setRunTriggerButtonState({ label: `Run #${run.id} started`, disabled: true, cooldownMs: 1000 });
    toast(`Run queued: #${run.id}`);
  } catch (err) {
    runTriggerCooldownUntil = 0;
    const triggerBtn = $("btn-trigger-run");
    if (triggerBtn && triggerBtn.dataset.defaultLabel) {
      triggerBtn.textContent = triggerBtn.dataset.defaultLabel;
    }
    updateRunControlsState();
    toast(err.message, true);
  }
});

on("run-workflow-id", "change", async () => {
  try {
    const workflowId = Number(($("run-workflow-id") || {}).value);
    updateRunsBackLink(
      Number.isFinite(workflowId) && workflowId > 0 ? editorUrlFor(workflowId) : null
    );
    await refreshRunVersionsForWorkflow(workflowId);
    await refreshRunArgPresets();
  } catch (err) {
    toast(err.message, true);
  }
});

on("editor-workflow-id", "change", async () => {
  try {
    const workflowId = Number(($("editor-workflow-id") || {}).value);
    if (!workflowId) {
      updateCurrentWorkflowIndicator(null);
      return;
    }
    setValueIfPresent("selected-workflow-id", workflowId);
    await loadWorkflowDetails(workflowId);
    toast(`Loaded workflow #${workflowId}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("run-version-id", "change", async () => {
  updateRunControlsState();
  try {
    await refreshRunArgPresets();
    if (Number(($("run-version-id") || {}).value) > 0) {
      await generateRunInputsTemplate();
      toast("Inputs template refreshed for selected version");
    }
  } catch (err) {
    toast(err.message, true);
  }
});

on("run-inputs", "input", () => {
  updateRunJsonStatus();
  syncRunInputLineNumbers();
});

on("run-inputs", "scroll", () => {
  syncRunInputLineNumbers();
});

on("run-preset-id", "change", () => {
  updateRunControlsState();
});

on("btn-save-run-preset", "click", async () => {
  try {
    const saved = await saveRunArgPreset(false);
    setValueIfPresent("run-preset-name", saved.name || "");
    await refreshRunArgPresets();
    setValueIfPresent("run-preset-id", saved.id);
    updateRunControlsState();
    toast(`Saved preset: #${saved.id}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-save-new-run-preset", "click", async () => {
  try {
    const saved = await saveRunArgPreset(true);
    setValueIfPresent("run-preset-name", saved.name || "");
    await refreshRunArgPresets();
    setValueIfPresent("run-preset-id", saved.id);
    updateRunControlsState();
    toast(`Saved new preset: #${saved.id}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-load-run-preset", "click", async () => {
  try {
    await loadRunArgPreset();
    toast("Loaded preset into run inputs");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-delete-run-preset", "click", async () => {
  try {
    await deleteRunArgPreset();
    setValueIfPresent("run-preset-id", "");
    await refreshRunArgPresets();
    setValueIfPresent("run-preset-name", "");
    toast("Deleted preset");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-generate-run-inputs", "click", async () => {
  try {
    await generateRunInputsTemplate();
    toast("Generated inputs template from workflow version");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-monitor-run", "click", async () => {
  try {
    const runId = Number($("monitor-run-id").value);
    await loadRunMonitor(runId);
    toast(`Loaded run #${runId}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-troubleshoot-run", "click", async () => {
  const loadingEl = $("troubleshoot-loading");
  const troubleshootBtn = $("btn-troubleshoot-run");
  try {
    const runId = Number(($("monitor-run-id") || {}).value);
    if (!runId) {
      throw new Error("Enter or load a Run ID first");
    }
    if (loadingEl) {
      loadingEl.style.display = "block";
    }
    if (troubleshootBtn) {
      troubleshootBtn.disabled = true;
    }
    const payload = {
      model: String(($("troubleshoot-model") || {}).value || "").trim() || null,
      temperature: 0.2,
      extra_prompt: String(($("troubleshoot-extra-prompt") || {}).value || "").trim() || null,
    };
    const result = await api(`/workflow-runs/${runId}/troubleshoot`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderTroubleshootStructured(result);
    toast("Troubleshooting analysis generated");
  } catch (err) {
    toast(err.message, true);
  } finally {
    if (loadingEl) {
      loadingEl.style.display = "none";
    }
    if (troubleshootBtn) {
      troubleshootBtn.disabled = false;
    }
  }
});

on("dashboard-logout-button", "click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } finally {
    window.location.href = "/login";
  }
});

on("btn-editor-assistant-ask", "click", async () => {
  const loadingEl = $("editor-assistant-loading");
  const askBtn = $("btn-editor-assistant-ask");
  try {
    const question = String(($("editor-assistant-question") || {}).value || "").trim();
    if (!question) {
      throw new Error("Please enter a question");
    }
    const payload = {
      question,
      html_snippet: String(($("editor-assistant-html") || {}).value || "").trim() || null,
      workflow_id: Number(($("selected-workflow-id") || {}).value) || null,
      workflow_version_id: Number(($("ver-current-version-id") || {}).value) || null,
      current_definition_json: $("ver-definition")
        ? JSON.parse($("ver-definition").value || "{}")
        : null,
      model: String(($("editor-assistant-model") || {}).value || "").trim() || null,
      temperature: 0.2,
    };
    if (loadingEl) {
      loadingEl.style.display = "block";
    }
    if (askBtn) {
      askBtn.disabled = true;
    }
    const result = await api("/editor-assistant", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if ($("editor-assistant-answer")) {
      $("editor-assistant-answer").textContent = result.answer || "";
    }
    toast("Assistant response ready");
  } catch (err) {
    toast(err.message, true);
  } finally {
    if (loadingEl) {
      loadingEl.style.display = "none";
    }
    if (askBtn) {
      askBtn.disabled = false;
    }
  }
});

loadCurrentUser().catch((err) => toast(err.message, true));
checkApi();
if ($("workflow-list") || $("editor-workflow-id") || $("run-workflow-id")) {
  refreshWorkflows().then(async () => {
    const initial = getInitialQueryState();
    if (initial.tab) {
      setActiveTab(initial.tab);
    }
    updateRunsBackLink(initial.returnToEditor);
    if (initial.workflowId && $("run-workflow-id")) {
      setValueIfPresent("run-workflow-id", initial.workflowId);
      await refreshRunVersionsForWorkflow(initial.workflowId, initial.versionId);
    }
  });
}
if ($("run-preset-id")) {
  refreshRunArgPresets();
}
if ($("template-list")) {
  refreshTemplates();
}
if ($("step-type-select")) {
  refreshStepTypes();
}
if ($("step-builder")) {
  syncStepsFromJson();
}
autoResizeById("ver-definition", { minRows: 12, maxRows: 70 });
autoResizeById("run-inputs", { minRows: 6, maxRows: 24 });
autoResizeById("editor-assistant-question", { minRows: 3, maxRows: 12 });
autoResizeById("editor-assistant-html", { minRows: 6, maxRows: 20 });
autoResizeById("troubleshoot-extra-prompt", { minRows: 2, maxRows: 10 });
updateRunControlsState();
updateVersionPrimaryActions();
if (isDedicatedEditorPage) {
  const params = new URLSearchParams(window.location.search);
  const workflowId = Number(params.get("workflow_id"));
  if (workflowId) {
    setValueIfPresent("editor-workflow-id", workflowId);
    loadWorkflowDetails(workflowId).catch((err) => toast(err.message, true));
  } else if ($("workflow-details")) {
    updateCurrentWorkflowIndicator(null);
    $("workflow-details").textContent = JSON.stringify(
      {
        info: "No workflow selected yet.",
        next_step: "Load a workflow by ID or open this page from Dashboard > Edit Workflow.",
      },
      null,
      2
    );
  }
}
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.getAttribute("data-tab")));
});
document.querySelectorAll(".monitor-tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveMonitorTab(tab.getAttribute("data-monitor-tab")));
});

// Floating Editor Assistant logic
on("btn-toggle-assistant", "click", () => {
  const win = $("floating-assistant");
  if (win) {
    if (win.style.display === "none") {
      win.style.display = "flex";
      const q = $("editor-assistant-question");
      if (q) q.focus();
    } else {
      win.style.display = "none";
    }
  }
});

on("btn-close-assistant", "click", () => {
  const win = $("floating-assistant");
  if (win) win.style.display = "none";
});

function openJsonSidebar() {
  document.body.classList.add("json-sidebar-open");
}

function closeJsonSidebar() {
  document.body.classList.remove("json-sidebar-open");
}

on("btn-open-json-sidebar", "click", () => {
  if ($("ver-definition")) {
    openJsonSidebar();
    autoResizeTextarea($("ver-definition"), { minRows: 12, maxRows: 70 });
  }
});

on("btn-close-json-sidebar", "click", () => {
  closeJsonSidebar();
});

on("json-sidebar-overlay", "click", () => {
  closeJsonSidebar();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeJsonSidebar();
  }
});

