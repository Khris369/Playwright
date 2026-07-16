const $ = (id) => document.getElementById(id);

function setAlert(message, isError = false) {
  const alert = $("login-alert");
  alert.textContent = message;
  alert.classList.toggle("is-invalid", isError);
  alert.classList.toggle("is-valid", !isError);
}

function setLoginFormStatus(message = "", isError = false) {
  const el = $("login-form-status");
  if (!el) return;
  el.textContent = message || "Enter your username and password.";
  el.classList.toggle("is-invalid", isError);
  el.classList.toggle("is-valid", !isError && Boolean(message));
}

function clearLoginFieldErrors() {
  $("login-username")?.classList.remove("input-invalid");
  $("login-password")?.classList.remove("input-invalid");
  setLoginFormStatus();
}

function setBootstrapPasswordStatus(message = "", isError = false) {
  const el = $("bootstrap-password-status");
  if (!el) return;
  el.textContent = message || "Password must be at least 12 characters.";
  el.classList.toggle("is-invalid", isError);
  el.classList.toggle("is-valid", !isError && Boolean(message));
}

function clearBootstrapPasswordStatus() {
  const el = $("bootstrap-password-status");
  if (!el) return;
  el.textContent = "Password must be at least 12 characters.";
  el.classList.remove("is-invalid", "is-valid");
}

function extractValidationMessage(detail) {
  if (typeof detail === "string" && detail) {
    return detail;
  }
  if (!Array.isArray(detail)) {
    return null;
  }
  for (const issue of detail) {
    if (!issue || typeof issue !== "object") continue;
    const path = Array.isArray(issue.loc) ? issue.loc.map(String) : [];
    if (path.includes("password")) {
      if (typeof issue.msg === "string" && issue.msg) {
        return issue.msg;
      }
      if (issue.type === "string_too_short") {
        return "Password must be at least 12 characters.";
      }
    }
  }
  return null;
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
  if (!response.ok) {
    const error = new Error(extractValidationMessage(body?.detail) || body?.detail || `Request failed (${response.status})`);
    error.status = response.status;
    error.detail = body?.detail || null;
    throw error;
  }
  return body;
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearLoginFieldErrors();
  try {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("login-username").value,
        password: $("login-password").value,
      }),
    });
    window.location.href = "/ui";
  } catch (error) {
    if (error.status === 401) {
      $("login-username")?.classList.add("input-invalid");
      $("login-password")?.classList.add("input-invalid");
      setLoginFormStatus("Invalid username or password.", true);
    }
    setAlert(error.message, true);
  }
});

$("bootstrap-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearBootstrapPasswordStatus();
  const password = $("bootstrap-password");
  if (!password.reportValidity()) {
    setBootstrapPasswordStatus("Password must be at least 12 characters.", true);
    return;
  }
  try {
    await api("/auth/bootstrap-admin", {
      method: "POST",
      body: JSON.stringify({
        username: $("bootstrap-username").value,
        email: $("bootstrap-email").value || null,
        display_name: $("bootstrap-name").value,
        password: password.value,
        role: "admin",
        status: "active",
      }),
    });
    window.location.href = "/ui/users";
  } catch (error) {
    if (error.status === 422) {
      const message = extractValidationMessage(error.detail) || "Password must be at least 12 characters.";
      setBootstrapPasswordStatus(message, true);
    }
    setAlert(error.message, true);
  }
});

$("bootstrap-password")?.addEventListener("input", () => {
  const password = $("bootstrap-password");
  if (!password) return;
  if (password.validity.valid) {
    clearBootstrapPasswordStatus();
  }
});

$("login-username")?.addEventListener("input", clearLoginFieldErrors);
$("login-password")?.addEventListener("input", clearLoginFieldErrors);
