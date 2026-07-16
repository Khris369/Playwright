const $ = (id) => document.getElementById(id);

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
  if (user.role !== "admin") {
    window.location.href = "/ui";
    return null;
  }
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
  const role = selectInput(user.role, ["user", "admin"]);
  const status = selectInput(user.status, ["active", "inactive"]);
  form.append(
    field("Username", username),
    field("Email (optional)", email),
    field("Display name", displayName),
    field("Role", role),
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
        role: role.value,
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

async function loadUsers() {
  const users = await api("/users");
  if (!users) return;
  const list = $("users-list");
  list.replaceChildren();
  if (!users.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No users yet.";
    list.appendChild(empty);
  } else {
    users.forEach((user) => list.appendChild(renderUser(user)));
  }
  setAlert(`${users.length} user${users.length === 1 ? "" : "s"} loaded.`);
}

$("create-user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/users", {
    method: "POST",
    body: JSON.stringify({
      username: $("create-username").value,
      email: $("create-email").value || null,
      display_name: $("create-name").value,
      role: $("create-role").value,
      status: $("create-status").value,
      password: $("create-password").value,
    }),
  });
  event.currentTarget.reset();
  setAlert("User created.");
  await loadUsers();
});

$("refresh-users").addEventListener("click", loadUsers);

$("logout-button").addEventListener("click", async () => {
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
