const API = "/api";
let registerMode = false;
let pollTimer = null;

const $ = (id) => document.getElementById(id);

function token() { return localStorage.getItem("token"); }

function setView() {
  const loggedIn = Boolean(token());
  $("auth-panel").classList.toggle("hidden", loggedIn);
  $("app-panel").classList.toggle("hidden", !loggedIn);
  $("user-box").classList.toggle("hidden", !loggedIn);
  if (loggedIn) {
    $("whoami").textContent = localStorage.getItem("username") || "";
    loadHistory();
    loadContexts();
  }
}

async function loadContexts() {
  try {
    const data = await api("/contexts");
    const select = $("cluster-context");
    select.length = 1;
    for (const name of data.contexts || []) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    }
  } catch (err) {
    console.warn("Could not load kubeconfig contexts:", err.message);
  }
}

async function api(path, options = {}) {
  options.headers = Object.assign(
    { "Content-Type": "application/json" },
    token() ? { Authorization: "Bearer " + token() } : {},
                                  options.headers || {}
  );
  const resp = await fetch(API + path, options);
  if (resp.status === 401) {
    localStorage.clear();
    setView();
    throw new Error("Session expired, log in again");
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed with " + resp.status);
  }
  return resp.json();
}

$("auth-toggle").addEventListener("click", (e) => {
  e.preventDefault();
  registerMode = !registerMode;
  $("auth-title").textContent = registerMode ? "Register" : "Log in";
  $("auth-submit").textContent = registerMode ? "Register" : "Log in";
  $("auth-toggle").textContent = registerMode
  ? "Have an account? Log in"
  : "Need an account? Register";
});

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("auth-error").classList.add("hidden");
  try {
    const data = await api(registerMode ? "/auth/register" : "/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value,
                           password: $("password").value,
      }),
    });
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("username", $("username").value);
    setView();
  } catch (err) {
    $("auth-error").textContent = err.message;
    $("auth-error").classList.remove("hidden");
  }
});

$("logout-btn").addEventListener("click", () => {
  localStorage.clear();
  if (pollTimer) clearInterval(pollTimer);
  setView();
});

$("investigate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const inv = await api("/investigations", {
    method: "POST",
    body: JSON.stringify({
      namespace: $("namespace").value,
                         deployment: $("deployment").value || null,
                         cluster_context: $("cluster-context").value || null,
    }),
  });
  showProgress(inv);
  pollTimer = setInterval(() => poll(inv.id), 2000);
});

function showProgress(inv) {
  $("progress").classList.remove("hidden");
  $("result").classList.add("hidden");
  $("result-error").classList.add("hidden");
  $("current-id").textContent = "#" + inv.id;
  $("current-status").textContent = inv.status;
}

async function poll(id) {
  const inv = await api("/investigations/" + id);
  $("current-status").textContent = inv.status;
  if (inv.status === "done") {
    clearInterval(pollTimer);
    $("result").classList.remove("hidden");
    $("result-pattern").textContent = inv.failure_pattern || "-";
    $("result-confidence").textContent = (inv.confidence ?? "-") + "%";
    $("result-cause").textContent = inv.root_cause || "-";
    $("result-commands").textContent = (inv.fix_commands || []).join("\n") || "none";
    loadHistory();
  } else if (inv.status === "failed") {
    clearInterval(pollTimer);
    $("result-error").textContent = "Investigation failed: " + (inv.error || "unknown error");
    $("result-error").classList.remove("hidden");
    loadHistory();
  }
}

async function loadHistory() {
  const items = await api("/investigations");
  const list = $("history");
  list.innerHTML = "";
  for (const inv of items) {
    const li = document.createElement("li");
    const summary = document.createElement("div");
    summary.className = "history-row";
    summary.textContent =
    "#" + inv.id + "  " + inv.namespace +
    (inv.deployment ? "/" + inv.deployment : "") +
    (inv.cluster_context ? "  @" + inv.cluster_context : "") +
    "  [" + inv.status + "]" +
    (inv.failure_pattern ? "  " + inv.failure_pattern : "");
    const detail = document.createElement("pre");
    detail.className = "hidden";
    detail.textContent =
    "Root cause: " + (inv.root_cause || "-") +
    "\nConfidence: " + (inv.confidence ?? "-") +
    (inv.analysis_duration_seconds ? "\nAnalysis took: " + inv.analysis_duration_seconds + "s" : "") +
    "\nFix commands:\n" + ((inv.fix_commands || []).join("\n") || "none");
    summary.addEventListener("click", () => detail.classList.toggle("hidden"));
    li.appendChild(summary);
    li.appendChild(detail);
    list.appendChild(li);
  }
}

setView();
