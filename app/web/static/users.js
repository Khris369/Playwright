const $ = (id) => document.getElementById(id);
let availableRoles = [];
let usersById = new Map();

function setAlert(message, isError = false) {
  const alert = $("users-alert");
  alert.textContent = message;
  alert.classList.toggle("is-invalid", isError);
  alert.classList.toggle("is-valid", !isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.status === 401) {
    window.location.href = "/login";
    return null;
  }
  if (!response.ok) {
    throw new Error(body?.detail || `Request failed (${response.status})`);
  }
  return body;
}

async function loadCurrentUser() {
  const user = await api("/auth/me");
  if (!user) return null;
  console.info("[users] authenticated user", {
    id: user.id,
    username: user.username,
    roles: user.roles || [],
    permissions: user.permissions || [],
  });
  const actions = $("users-admin-actions");
  if (actions) {
    actions.hidden = false;
  }
  return user;
}

function field(label, input) {
  const wrapper = document.createElement("label");
  wrapper.append(label, input);
  return wrapper;
}

function textInput(value) {
  const input = document.createElement("input");
  input.value = value || "";
  return input;
}

function selectInput(value, options) {
  const select = document.createElement("select");
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option;
    item.textContent = option;
    item.selected = option === value;
    select.appendChild(item);
  });
  return select;
}

function renderUser(user) {
  const card = document.createElement("article");
  card.className = "user-card";

  const title = document.createElement("div");
  title.className = "user-card-title";
  const name = document.createElement("strong");
  name.textContent = user.display_name;
  const meta = document.createElement("small");
  meta.textContent = `#${user.id} • ${user.username}${user.email ? ` • ${user.email}` : ""}`;
  title.append(name, meta);

  const form = document.createElement("form");
  form.className = "user-card-form";
  const username = textInput(user.username);
  const email = textInput(user.email);
  const displayName = textInput(user.display_name);
  const status = selectInput(user.status, ["active", "inactive"]);
  form.append(
    field("Username", username),
    field("Email (optional)", email),
    field("Display name", displayName),
    field("Status", status),
  );

  const actions = document.createElement("div");
  actions.className = "user-card-actions";
  const save = document.createElement("button");
  save.type = "submit";
  save.className = "btn-secondary btn-sm";
  save.textContent = "Save";
  const resetPassword = document.createElement("button");
  resetPassword.type = "button";
  resetPassword.className = "btn-secondary btn-sm";
  resetPassword.textContent = "Reset password";
  actions.append(save, resetPassword);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await api(`/users/${user.id}`, {
      method: "PUT",
      body: JSON.stringify({
        username: username.value,
        email: email.value || null,
        display_name: displayName.value,
        status: status.value,
      }),
    });
    setAlert(`Updated ${displayName.value}`);
    await loadUsers();
  });

  resetPassword.addEventListener("click", async () => {
    const password = window.prompt("Enter a new password with at least 12 characters.");
    if (!password) return;
    await api(`/users/${user.id}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    setAlert(`Password reset for ${displayName.value}`);
  });

  card.append(title, form, actions);
  return card;
}

function renderRoleOptions(selectedRoles = []) {
  const list = $("role-options-list");
  list.replaceChildren();
  availableRoles.forEach((role) => {
    const label = document.createElement("label");
    label.className = "role-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = role.name;
    checkbox.checked = selectedRoles.includes(role.name);
    checkbox.addEventListener("change", updateEffectivePermissions);
    label.append(checkbox, document.createTextNode(role.name));
    list.appendChild(label);
  });
}

function selectedRoles() {
  return [...document.querySelectorAll("#role-options-list input:checked")].map((input) => input.value);
}

function updateEffectivePermissions() {
  const permissions = new Set();
  selectedRoles().forEach((roleName) => {
    const role = availableRoles.find((item) => item.name === roleName);
    (role?.permissions || []).forEach((permission) => permissions.add(permission));
  });
  const target = $("effective-permissions");
  target.replaceChildren();
  if (!permissions.size) {
    target.textContent = "No permissions selected.";
    return;
  }
  [...permissions].sort().forEach((permission) => {
    const item = document.createElement("span");
    item.className = "permission-chip";
    item.textContent = permission;
    target.appendChild(item);
  });
}

async function loadRoleEditor(userId) {
  const access = await api(`/users/${userId}/roles`);
  renderRoleOptions(access.roles || []);
  const permissions = $("effective-permissions");
  permissions.replaceChildren();
  (access.permissions || []).forEach((permission) => {
    const item = document.createElement("span");
    item.className = "permission-chip";
    item.textContent = permission;
    permissions.appendChild(item);
  });
}

async function loadRoleManagement(users) {
  const roleRows = await api("/users/roles");
  availableRoles = roleRows || [];
  const select = $("role-user-select");
  select.replaceChildren();
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = user.id;
    option.textContent = `${user.display_name} (${user.username})`;
    select.appendChild(option);
  });
  if (users.length) {
    await loadRoleEditor(users[0].id);
  }
}

async function loadUsers() {
  const users = await api("/users");
  if (!users) return;
  const list = $("users-list");
  list.replaceChildren();
  usersById = new Map(users.map((user) => [String(user.id), user]));
  if (!users.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No users yet.";
    list.appendChild(empty);
  } else {
    users.forEach((user) => list.appendChild(renderUser(user)));
  }
  setAlert(`${users.length} user${users.length === 1 ? "" : "s"} loaded.`);
  await loadRoleManagement(users);
}

$("role-user-select")?.addEventListener("change", (event) => loadRoleEditor(event.target.value).catch((error) => setAlert(error.message, true)));

$("role-management-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userId = $("role-user-select").value;
  await api(`/users/${userId}/roles`, {
    method: "PUT",
    body: JSON.stringify({ roles: selectedRoles() }),
  });
  setAlert("Role assignments saved.");
  await loadRoleEditor(userId);
});

$("create-user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/users", {
    method: "POST",
    body: JSON.stringify({
      username: $("create-username").value,
      email: $("create-email").value || null,
      display_name: $("create-name").value,
      status: $("create-status").value,
      password: $("create-password").value,
    }),
  });
  event.currentTarget.reset();
  setAlert("User created.");
  await loadUsers();
});

$("refresh-users").addEventListener("click", loadUsers);

$("logout-button")?.addEventListener("click", async () => {
  await api("/auth/logout", { method: "POST" });
  window.location.href = "/login";
});

loadCurrentUser()
  .then((user) => {
    if (user) {
      return loadUsers();
    }
    return null;
  })
  .catch((error) => setAlert(error.message, true));
