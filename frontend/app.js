const app = document.querySelector("#app");
const title = document.querySelector("#page-title");
const statusPill = document.querySelector("#status");
let currentView = "home";

const api = {
  async get(path) {
    const response = await fetch(path);
    return response.json();
  },
  async post(path, body = {}) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return response.json();
  },
};

document.querySelectorAll(".sidebar button").forEach((button) => {
  button.addEventListener("click", () => render(button.dataset.view));
});

async function refreshStatus() {
  const status = await api.get("/api/status");
  statusPill.textContent = status.active ? `${status.mode} recording` : "Idle";
  statusPill.classList.toggle("active", status.active);
}

function setActive(view) {
  currentView = view;
  document.querySelectorAll(".sidebar button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
}

async function render(view) {
  setActive(view);
  await refreshStatus();
  if (view === "home") return renderHome();
  if (view === "evidence") return renderStartForm("evidence", "Evidence Capture");
  if (view === "observation") return renderStartForm("observation", "Observation Mode");
  if (view === "sessions") return renderSessions();
  return renderSettings();
}

function renderHome() {
  title.textContent = "Home";
  app.innerHTML = `
    <div class="grid">
      <section class="card">
        <h2>Evidence Capture</h2>
        <p class="muted">Use this when staff need direct evidence now: clicks, marked screenshots, and notes.</p>
        <button class="primary" data-go="evidence">Start evidence capture</button>
      </section>
      <section class="card">
        <h2>Observation Mode</h2>
        <p class="muted">Use this for passive local screenshots across a longer session.</p>
        <button class="primary" data-go="observation">Start observation</button>
      </section>
    </div>
  `;
  app.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => render(button.dataset.go));
  });
}

function renderStartForm(mode, heading) {
  title.textContent = heading;
  const interval = mode === "observation"
    ? `<label>Screenshot interval seconds <input name="interval_seconds" type="number" min="5" value="60"></label>`
    : "";
  app.innerHTML = `
    <form class="form" id="start-form">
      <label>CYP initials <input name="cyp" autocomplete="off"></label>
      <label>Activity or project <input name="activity" autocomplete="off"></label>
      <label>Staff member <input name="staff" autocomplete="off"></label>
      <label>Evidence purpose
        <select name="purpose">
          <option>UAS evidence</option>
          <option>Behaviour support</option>
          <option>Project progress</option>
          <option>General observation</option>
        </select>
      </label>
      <label>Privacy note <textarea name="privacy_note"></textarea></label>
      ${interval}
      <div class="actions">
        <button class="primary" type="submit">Start</button>
        <button class="danger" type="button" id="stop">Stop active recording</button>
      </div>
    </form>
    <section class="card" id="manual-capture">
      <h2>Manual capture controls</h2>
      <p class="muted">Temporary MVP controls until global mouse hooks are wired in.</p>
      <div class="actions">
        <button class="secondary" id="fake-click">Capture click at 100, 200</button>
        <button class="secondary" id="periodic">Capture observation screenshot</button>
      </div>
    </section>
  `;
  app.querySelector("#start-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const metadata = Object.fromEntries(["cyp", "activity", "staff", "purpose", "privacy_note"].map((key) => [key, form.get(key)]));
    const settings = { interval_seconds: Number(form.get("interval_seconds") || 60) };
    await api.post("/api/record/start", { mode, metadata, settings });
    await refreshStatus();
  });
  app.querySelector("#stop").addEventListener("click", async () => {
    await api.post("/api/record/stop");
    await refreshStatus();
    await renderSessions();
  });
  app.querySelector("#fake-click").addEventListener("click", async () => {
    await api.post("/api/capture/click", { x: 100, y: 200 });
    await refreshStatus();
  });
  app.querySelector("#periodic").addEventListener("click", async () => {
    await api.post("/api/capture/periodic");
    await refreshStatus();
  });
}

async function renderSessions() {
  title.textContent = "Sessions";
  const data = await api.get("/api/sessions");
  const rows = data.sessions.map((session) => `
    <div class="session-row">
      <div>
        <strong>${escapeHtml(session.title)}</strong>
        <div class="muted">${session.mode} - ${session.started} - ${session.event_count} screenshots</div>
      </div>
      <button class="secondary" data-export="${session.id}">Export HTML</button>
    </div>
  `).join("");
  app.innerHTML = `<section class="card">${rows || "<p class='muted'>No sessions yet.</p>"}</section>`;
  app.querySelectorAll("[data-export]").forEach((button) => {
    button.addEventListener("click", async () => {
      const result = await api.post(`/api/sessions/${button.dataset.export}/export`);
      alert(`Exported: ${result.html}`);
    });
  });
}

function renderSettings() {
  title.textContent = "Settings";
  app.innerHTML = `
    <section class="card">
      <h2>Settings</h2>
      <p class="muted">Storage, hotkeys, retention, and redaction defaults will live here next.</p>
    </section>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

render(currentView);
