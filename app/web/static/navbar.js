(() => {
  const mount = document.querySelector("[data-app-navbar]");
  if (!mount) return;

  const menuItems = [
    { label: "Dashboard", href: "/ui", button: true },
    { label: "User Management", href: "/ui/users", adminOnly: true },
  ];
  const currentPath = window.location.pathname;
  const pageTitle = mount.dataset.navbarTitle || "Workflow Builder";
  const pageSubtitle = mount.dataset.navbarSubtitle || "";

  const nav = document.createElement("nav");
  nav.className = "app-navbar";
  nav.setAttribute("aria-label", "Primary navigation");
  const inner = document.createElement("div");
  inner.className = "app-navbar-inner";

  const brand = document.createElement("a");
  brand.className = "app-navbar-brand";
  brand.href = "/ui";
  brand.innerHTML = '<span class="app-navbar-mark" aria-hidden="true">WB</span>';
  const brandText = document.createElement("span");
  brandText.textContent = "Workflow Builder";
  brand.appendChild(brandText);
  inner.appendChild(brand);

  const heading = document.createElement("div");
  heading.className = "app-navbar-heading";
  const title = document.createElement("strong");
  title.textContent = pageTitle;
  heading.appendChild(title);
  if (pageSubtitle) {
    const subtitle = document.createElement("span");
    subtitle.textContent = pageSubtitle;
    heading.appendChild(subtitle);
  }
  inner.appendChild(heading);

  const toggle = document.createElement("button");
  toggle.className = "app-navbar-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "app-navbar-menu");
  toggle.setAttribute("aria-label", "Open navigation menu");
  toggle.innerHTML = "<span></span><span></span><span></span>";
  inner.appendChild(toggle);

  const menu = document.createElement("div");
  menu.className = "app-navbar-menu";
  menu.id = "app-navbar-menu";
  const links = document.createElement("div");
  links.className = "app-navbar-links";
  const linkElements = new Map();
  for (const item of menuItems) {
    const link = document.createElement(item.button ? "button" : "a");
    link.className = "app-navbar-link";
    if (item.button) {
      link.type = "button";
      link.addEventListener("click", () => { window.location.href = item.href; });
    } else {
      link.href = item.href;
    }
    link.textContent = item.label;
    if (item.adminOnly) {
      link.hidden = true;
      link.dataset.adminOnly = "true";
    }
    if (currentPath === item.href || (item.href === "/ui" && currentPath === "/ui/")) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
    links.appendChild(link);
    linkElements.set(item.label, link);
  }
  menu.appendChild(links);

  const account = document.createElement("div");
  account.className = "app-navbar-account";
  const userLabel = document.createElement("span");
  userLabel.className = "app-navbar-user";
  userLabel.hidden = true;
  account.appendChild(userLabel);

  const changePassword = document.createElement("button");
  changePassword.className = "app-navbar-action";
  changePassword.type = "button";
  changePassword.textContent = "Change Password";
  account.appendChild(changePassword);

  const logout = document.createElement("button");
  logout.className = "app-navbar-action app-navbar-action-muted";
  logout.type = "button";
  logout.textContent = "Logout";
  account.appendChild(logout);
  menu.appendChild(account);
  inner.appendChild(menu);
  nav.appendChild(inner);

  const modal = document.createElement("div");
  modal.className = "app-navbar-modal-backdrop";
  modal.hidden = true;
  modal.innerHTML = `
    <section class="app-navbar-modal" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
      <div class="app-navbar-modal-header">
        <h2 id="change-password-title">Change Password</h2>
        <button class="app-navbar-modal-close" type="button" aria-label="Close Change Password">&times;</button>
      </div>
      <form class="app-navbar-password-form">
        <label>Current password
          <input name="current_password" type="password" autocomplete="current-password" required maxlength="128">
        </label>
        <label>New password
          <input name="new_password" type="password" autocomplete="new-password" required minlength="4" maxlength="128">
        </label>
        <label>Confirm new password
          <input name="confirm_password" type="password" autocomplete="new-password" required minlength="4" maxlength="128">
        </label>
        <div class="app-navbar-form-status" role="status" aria-live="polite"></div>
        <div class="app-navbar-modal-actions">
          <button class="btn-secondary btn-sm" type="button" data-navbar-cancel>Cancel</button>
          <button class="btn-primary btn-sm" type="submit">Update Password</button>
        </div>
      </form>
    </section>`;
  mount.replaceChildren(nav, modal);

  const closeModal = () => {
    modal.hidden = true;
    modal.querySelector("form").reset();
    modal.querySelector(".app-navbar-form-status").textContent = "";
  };
  const openModal = () => {
    nav.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    modal.hidden = false;
    modal.querySelector('input[name="current_password"]').focus();
  };

  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
  });
  changePassword.addEventListener("click", openModal);
  modal.querySelector(".app-navbar-modal-close").addEventListener("click", closeModal);
  modal.querySelector("[data-navbar-cancel]").addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });

  logout.addEventListener("click", async () => {
    logout.disabled = true;
    try {
      await fetch("/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  });

  modal.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const status = form.querySelector(".app-navbar-form-status");
    const submit = form.querySelector('button[type="submit"]');
    const values = Object.fromEntries(new FormData(form).entries());
    if (values.new_password !== values.confirm_password) {
      status.textContent = "New passwords do not match.";
      status.className = "app-navbar-form-status is-invalid";
      return;
    }
    submit.disabled = true;
    status.textContent = "Updating password...";
    status.className = "app-navbar-form-status";
    try {
      const response = await fetch("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: values.current_password, new_password: values.new_password }),
      });
      const body = response.status === 204 ? null : await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || "Unable to change password.");
      status.textContent = "Password updated.";
      status.className = "app-navbar-form-status is-valid";
      window.setTimeout(closeModal, 700);
    } catch (error) {
      status.textContent = error.message || "Unable to change password.";
      status.className = "app-navbar-form-status is-invalid";
    } finally {
      submit.disabled = false;
    }
  });

  fetch("/auth/me")
    .then(async (response) => {
      if (response.status === 401) {
        window.location.href = "/login";
        return null;
      }
      if (!response.ok) throw new Error("Unable to load account details.");
      return response.json();
    })
    .then((user) => {
      if (!user) return;
      userLabel.textContent = user.display_name || user.username || "Account";
      userLabel.hidden = false;
      if (user.role === "admin") linkElements.get("User Management").hidden = false;
    })
    .catch(() => { userLabel.hidden = true; });
})();
