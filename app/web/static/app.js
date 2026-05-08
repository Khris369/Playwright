const $ = (id) => document.getElementById(id);
const on = (id, event, handler) => {
  const el = $(id);
  if (el) {
    el.addEventListener(event, handler);
  }
};

const defaultDefinition = {
  steps: [
    { type: "goto_url", args: { url: "{{inputs.base_url}}" } },
    { type: "fill_input", args: { selector: "#username", value: "{{inputs.username}}" } },
    { type: "click", args: { selector: "button[type='submit']" } }
  ]
};

const stepTemplates = {
  goto_url: { url: "{{inputs.base_url}}" },
  fill_input: { selector: "", value: "" },
  click: { selector: "" },
  select_option: { selector: "", value: "" },
  wait_for_element: { selector: "" },
  assert_url_not_equal: { url: "" },
  assert_text_visible: { text: "" },
  run_custom_action: { action: "" },
};

let editorSteps = [];
let draggedStepIndex = null;

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

function syncJsonFromSteps() {
  const definition = parseDefinitionJson();
  definition.steps = editorSteps.map((step) => ({
    type: step.type,
    args: step.args || {},
  }));
  $("ver-definition").value = JSON.stringify(definition, null, 2);
}

function syncStepsFromJson() {
  const definition = parseDefinitionJson();
  editorSteps = (definition.steps || []).map((step) => ({
    type: String(step.type || "click"),
    args: step.args && typeof step.args === "object" ? step.args : {},
  }));
  renderStepBuilder();
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
    .map((step, index) => `
      <div class="step-card" draggable="true" data-step-index="${index}">
        <div class="step-card-header">
          <div class="step-card-title">Step ${index + 1}</div>
          <div class="step-drag" title="Drag to reorder">::</div>
        </div>
        <div class="grid2">
          <select data-field="type" data-step-index="${index}">
            ${Object.keys(stepTemplates)
              .map((type) => `<option value="${type}" ${type === step.type ? "selected" : ""}>${type}</option>`)
              .join("")}
          </select>
          <button class="step-remove" type="button" data-action="remove" data-step-index="${index}">Remove</button>
        </div>
        <textarea data-field="args" data-step-index="${index}" spellcheck="false">${JSON.stringify(step.args || {}, null, 2)}</textarea>
      </div>
    `)
    .join("");

  builder.querySelectorAll("[data-action='remove']").forEach((el) => {
    el.addEventListener("click", () => {
      const index = Number(el.getAttribute("data-step-index"));
      editorSteps.splice(index, 1);
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("select[data-field='type']").forEach((el) => {
    el.addEventListener("change", () => {
      const index = Number(el.getAttribute("data-step-index"));
      const nextType = el.value;
      editorSteps[index].type = nextType;
      if (!editorSteps[index].args || typeof editorSteps[index].args !== "object") {
        editorSteps[index].args = {};
      }
      if (Object.keys(editorSteps[index].args).length === 0 && stepTemplates[nextType]) {
        editorSteps[index].args = { ...stepTemplates[nextType] };
      }
      syncJsonFromSteps();
      renderStepBuilder();
    });
  });

  builder.querySelectorAll("textarea[data-field='args']").forEach((el) => {
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

  builder.querySelectorAll(".step-card").forEach((card) => {
    card.addEventListener("dragstart", () => {
      draggedStepIndex = Number(card.getAttribute("data-step-index"));
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      draggedStepIndex = null;
      card.classList.remove("dragging");
    });
    card.addEventListener("dragover", (event) => {
      event.preventDefault();
    });
    card.addEventListener("drop", () => {
      const dropIndex = Number(card.getAttribute("data-step-index"));
      if (draggedStepIndex === null || draggedStepIndex === dropIndex) {
        return;
      }
      const [moved] = editorSteps.splice(draggedStepIndex, 1);
      editorSteps.splice(dropIndex, 0, moved);
      syncJsonFromSteps();
      renderStepBuilder();
    });
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

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = isError ? "error" : "ok";
  setTimeout(() => (el.className = ""), 2400);
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
  return res.json();
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

function workflowRow(wf) {
  return `<div class="item clickable" data-workflow-id="${wf.id}">
    <div><strong>#${wf.id}</strong> ${wf.name || "(unnamed)"}</div>
    <div class="muted">status=${wf.status || ""} created=${wf.created_at || ""}</div>
  </div>`;
}

function templateRow(tpl) {
  return `<div class="item clickable" data-template-id="${tpl.id}" data-template-name="${tpl.name || "Template"}">
    <div><strong>#${tpl.id}</strong> ${tpl.name || "(unnamed template)"}</div>
    <div class="muted">key=${tpl.key || ""} category=${tpl.category || ""}</div>
  </div>`;
}

async function refreshWorkflows() {
  const items = await api("/workflows");
  $("workflow-list").innerHTML = items.length ? items.map(workflowRow).join("") : "<div class='muted'>No workflows yet.</div>";
  document.querySelectorAll("#workflow-list .item.clickable").forEach((el) => {
    el.addEventListener("click", () => {
      const workflowId = Number(el.getAttribute("data-workflow-id"));
      loadWorkflowDetails(workflowId);
    });
  });
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
  const workflow = await api(`/workflows/${workflowId}`);
  const versions = await api(`/workflows/${workflowId}/versions`);
  const latestVersion = versions.length ? versions[0] : null;
  $("selected-workflow-id").value = workflowId;
  $("workflow-details").textContent = JSON.stringify(workflow, null, 2);
  $("workflow-versions").textContent = JSON.stringify(versions, null, 2);
  $("ver-workflow-id").value = workflowId;
  if (latestVersion) {
    if ($("run-version-id")) {
      $("run-version-id").value = latestVersion.id;
    }
    $("ver-definition").value = JSON.stringify(latestVersion.definition_json || defaultDefinition, null, 2);
    $("ver-number").value = Number(latestVersion.version_number || 0) + 1;
  } else {
    $("ver-definition").value = JSON.stringify(defaultDefinition, null, 2);
    $("ver-number").value = 1;
  }
  syncStepsFromJson();
}

on("btn-create-workflow", "click", async () => {
  try {
    const payload = {
      name: $("wf-name").value.trim(),
      description: $("wf-description").value.trim() || null,
      status: $("wf-status").value.trim() || "active",
    };
    const created = await api("/workflows", { method: "POST", body: JSON.stringify(payload) });
    toast(`Workflow created: #${created.id}`);
    $("ver-workflow-id").value = created.id;
    $("selected-workflow-id").value = created.id;
    $("ver-definition").value = JSON.stringify(defaultDefinition, null, 2);
    $("ver-number").value = 1;
    syncStepsFromJson();
    await refreshWorkflows();
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
    $("selected-workflow-id").value = imported.workflow.id;
    $("ver-workflow-id").value = imported.workflow.id;
    $("run-version-id").value = imported.version.id;
    await refreshWorkflows();
    await loadWorkflowDetails(imported.workflow.id);
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

on("btn-create-version", "click", async () => {
  try {
    const workflowId = Number($("ver-workflow-id").value);
    syncJsonFromSteps();
    const definition = JSON.parse($("ver-definition").value);
    const payload = {
      version_number: Number($("ver-number").value),
      is_published: $("ver-published").checked,
      definition_json: definition,
    };
    const created = await api(`/workflows/${workflowId}/versions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(`Version created: #${created.id}`);
    if ($("run-version-id")) {
      $("run-version-id").value = created.id;
    }
    await loadWorkflowDetails(workflowId);
    setActiveTab("runs");
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-add-step", "click", () => {
  const stepType = $("step-type-select").value;
  editorSteps.push({
    type: stepType,
    args: { ...(stepTemplates[stepType] || {}) },
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

on("ver-definition", "change", () => {
  try {
    syncStepsFromJson();
  } catch (err) {
    toast(`Invalid workflow JSON: ${err.message}`, true);
  }
});

on("btn-trigger-run", "click", async () => {
  try {
    const payload = {
      workflow_version_id: Number($("run-version-id").value),
      inputs: JSON.parse($("run-inputs").value || "{}"),
    };
    const run = await api("/workflow-runs", { method: "POST", body: JSON.stringify(payload) });
    $("run-created").textContent = `Created run #${run.id} status=${run.status}`;
    $("monitor-run-id").value = run.id;
    toast(`Run queued: #${run.id}`);
  } catch (err) {
    toast(err.message, true);
  }
});

on("btn-monitor-run", "click", async () => {
  try {
    const runId = Number($("monitor-run-id").value);
    const run = await api(`/workflow-runs/${runId}`);
    const steps = await api(`/workflow-runs/${runId}/steps`);
    $("run-details").textContent = JSON.stringify(run, null, 2);
    $("step-details").textContent = JSON.stringify(steps, null, 2);
    toast(`Loaded run #${runId}`);
  } catch (err) {
    toast(err.message, true);
  }
});

checkApi();
if ($("workflow-list")) {
  refreshWorkflows();
}
if ($("template-list")) {
  refreshTemplates();
}
if ($("step-builder")) {
  syncStepsFromJson();
}
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.getAttribute("data-tab")));
});
