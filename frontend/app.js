const app = document.querySelector("#app");
const title = document.querySelector("#page-title");
const statusPill = document.querySelector("#status");
let currentView = "home";
let currentSessionId = null;

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
  async patch(path, body = {}) {
    const response = await fetch(path, {
      method: "PATCH",
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
  if (status.hook_error) {
    statusPill.textContent += " - manual fallback";
  }
  statusPill.classList.toggle("active", status.active);
  return status;
}

function setActive(view) {
  currentView = view;
  document.querySelectorAll(".sidebar button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
}

async function render(view) {
  setActive(view);
  const status = await refreshStatus();
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
      <p class="muted" id="hook-note"></p>
      <div class="actions">
        <button class="primary" type="submit">Start</button>
        <button class="danger" type="button" id="stop">Stop active recording</button>
      </div>
    </form>
    <section class="card fallback-controls" id="manual-capture">
      <h2>Fallback capture controls</h2>
      <p class="muted">Use these only if global capture is unavailable or for local testing.</p>
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
    const status = await refreshStatus();
    const note = app.querySelector("#hook-note");
    if (note && status.hook_error) {
      note.textContent = `${status.hook_error}. Manual capture buttons are still available for testing.`;
    }
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
      <button class="secondary" data-open="${session.id}">Review</button>
    </div>
  `).join("");
  app.innerHTML = `<section class="card">${rows || "<p class='muted'>No sessions yet.</p>"}</section>`;
  app.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", async () => {
      await renderReview(button.dataset.open);
    });
  });
}

async function renderReview(sessionId) {
  currentSessionId = sessionId;
  title.textContent = "Review";
  const data = await api.get(`/api/sessions/${sessionId}`);
  const session = data.session;
  const metadata = session.metadata || {};
  const events = session.events || [];
  const eventCards = events.map((event) => renderEventEditor(session.id, event)).join("");
  app.innerHTML = `
    <section class="card">
      <h2>${escapeHtml(metadata.activity || session.id)}</h2>
      <p class="muted">${escapeHtml(session.mode)} - ${escapeHtml(session.started)} - ${events.length} screenshots</p>
      <div class="actions">
        <button class="primary" id="export-session">Export HTML</button>
        <button class="secondary" id="back-sessions">Back to sessions</button>
      </div>
    </section>
    <section class="review-list">
      ${eventCards || "<p class='muted'>No screenshots captured for this session yet.</p>"}
    </section>
  `;
  app.querySelector("#back-sessions").addEventListener("click", renderSessions);
  app.querySelector("#export-session").addEventListener("click", async () => {
    const result = await api.post(`/api/sessions/${sessionId}/export`);
    alert(`Exported: ${result.html}`);
  });
  app.querySelectorAll("[data-save-event]").forEach((button) => {
    button.addEventListener("click", async () => saveEvent(sessionId, button.dataset.saveEvent));
  });
}

function renderEventEditor(sessionId, event) {
  const tags = Array.isArray(event.tags) ? event.tags.join(", ") : "";
  const checked = event.highlight ? "checked" : "";
  const imageUrl = `/api/sessions/${encodeURIComponent(sessionId)}/screenshots/${encodeURIComponent(event.screenshot || "")}`;
  return `
    <article class="card event-editor">
      <div>
        <img class="event-thumb" src="${imageUrl}" alt="Screenshot ${escapeAttr(event.index || "")}">
        <p class="muted">${escapeHtml(event.type)} - ${escapeHtml(event.timestamp || "")}</p>
      </div>
      <div class="form">
        <label>Title <input data-field="title" data-event="${event.index}" value="${escapeAttr(event.title || "")}"></label>
        <label>Staff note <textarea data-field="staff_note" data-event="${event.index}">${escapeHtml(event.staff_note || "")}</textarea></label>
        <label>CYP quote <textarea data-field="cyp_quote" data-event="${event.index}">${escapeHtml(event.cyp_quote || "")}</textarea></label>
        <label>Tags <input data-field="tags" data-event="${event.index}" value="${escapeAttr(tags)}"></label>
        <label class="check-row"><input type="checkbox" data-field="highlight" data-event="${event.index}" ${checked}> Mark as highlight</label>
        <div class="actions">
          <button class="primary" data-save-event="${event.index}">Save evidence note</button>
        </div>
      </div>
    </article>
  `;
}

async function saveEvent(sessionId, eventIndex) {
  const fields = app.querySelectorAll(`[data-event="${eventIndex}"]`);
  const payload = {};
  fields.forEach((field) => {
    const key = field.dataset.field;
    if (key === "tags") {
      payload.tags = field.value.split(",").map((tag) => tag.trim()).filter(Boolean);
    } else if (key === "highlight") {
      payload.highlight = field.checked;
    } else {
      payload[key] = field.value;
    }
  });
  await api.patch(`/api/sessions/${sessionId}/events/${eventIndex}`, payload);
  await renderReview(sessionId);
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

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

render(currentView);
