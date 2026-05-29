const app = document.querySelector("#app");
const title = document.querySelector("#page-title");
const statusPill = document.querySelector("#status");
let currentView = "home";
let currentSessionId = null;
let latestStatus = { active: false };
let reviewFilter = "all";

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
  async delete(path) {
    const response = await fetch(path, { method: "DELETE" });
    return response.json();
  },
};

document.querySelectorAll(".sidebar button").forEach((button) => {
  button.addEventListener("click", () => render(button.dataset.view));
});

async function refreshStatus() {
  const status = await api.get("/api/status");
  latestStatus = status;
  statusPill.textContent = status.active ? `${status.mode} recording - ${status.event_count} screenshots` : "Idle";
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
  if (view === "home") {
    renderHome();
  } else if (view === "evidence") {
    await renderStartForm("evidence", "Evidence Capture");
  } else if (view === "observation") {
    await renderStartForm("observation", "Observation Mode");
  } else if (view === "sessions") {
    await renderSessions();
  } else {
    await renderSettings();
  }
  bindBannerStop();
  bindPauseResume();
}

function renderHome() {
  title.textContent = "Home";
  app.innerHTML = `
    ${renderActiveBanner()}
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

async function renderStartForm(mode, heading) {
  const settingsData = await api.get("/api/settings");
  const defaults = settingsData.settings;
  title.textContent = heading;
  const interval = mode === "observation"
    ? `<label>Screenshot interval seconds <input name="interval_seconds" type="number" min="5" value="${escapeAttr(defaults.observation_interval_seconds)}"></label>`
    : "";
  app.innerHTML = `
    ${renderActiveBanner()}
    <form class="form" id="start-form">
      <label>CYP initials <input name="cyp" autocomplete="off"></label>
      <label>Activity or project <input name="activity" autocomplete="off"></label>
      <label>Staff member <input name="staff" autocomplete="off"></label>
      <label>Evidence purpose
        <select name="purpose">
          ${renderPurposeOption("UAS evidence", defaults.default_evidence_purpose)}
          ${renderPurposeOption("Behaviour support", defaults.default_evidence_purpose)}
          ${renderPurposeOption("Project progress", defaults.default_evidence_purpose)}
          ${renderPurposeOption("General observation", defaults.default_evidence_purpose)}
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
    <section class="card fallback-controls ${latestStatus.hook_error ? "" : "hidden"}" id="manual-capture">
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
    const settings = {
      interval_seconds: Number(form.get("interval_seconds") || 60),
      marker: {
        shape: defaults.marker_shape,
        color: defaults.marker_color,
        size: defaults.marker_size,
        stroke: defaults.marker_stroke,
      },
    };
    await api.post("/api/record/start", { mode, metadata, settings });
    const status = await refreshStatus();
    latestStatus = status;
    const note = app.querySelector("#hook-note");
    if (note && status.hook_error) {
      note.textContent = `${status.hook_error}. Manual capture buttons are still available for testing.`;
      app.querySelector("#manual-capture")?.classList.remove("hidden");
    }
    await render(mode);
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
  bindBannerStop();
  bindPauseResume();
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
      <div class="row-actions">
        <button class="secondary" data-open="${session.id}">Review</button>
        <button class="danger" data-delete-session="${session.id}">Delete</button>
      </div>
    </div>
  `).join("");
  app.innerHTML = `<section class="card">${rows || "<p class='muted'>No sessions yet.</p>"}</section>`;
  app.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", async () => {
      await renderReview(button.dataset.open);
    });
  });
  app.querySelectorAll("[data-delete-session]").forEach((button) => {
    button.addEventListener("click", async () => deleteSession(button.dataset.deleteSession));
  });
}

function bindBannerStop() {
  const button = app.querySelector("#banner-stop");
  if (!button) {
    return;
  }
  button.addEventListener("click", async () => {
    await api.post("/api/record/stop");
    await render(currentView);
  });
}

function bindPauseResume() {
  const button = app.querySelector("#banner-pause");
  if (!button) {
    return;
  }
  button.addEventListener("click", async () => {
    await api.post(latestStatus.paused ? "/api/record/resume" : "/api/record/pause");
    await render(currentView);
  });
}

function renderActiveBanner() {
  if (!latestStatus.active) {
    return "";
  }
  const mode = latestStatus.mode === "observation" ? "Observation Mode" : "Evidence Capture";
  const elapsed = formatElapsed(latestStatus.elapsed_seconds || 0);
  const fallback = latestStatus.hook_error ? `<p class="muted">${escapeHtml(latestStatus.hook_error)}</p>` : "";
  const paused = latestStatus.paused ? "Paused" : "Active";
  const pauseButton = latestStatus.mode === "observation"
    ? `<button class="secondary" id="banner-pause">${latestStatus.paused ? "Resume" : "Pause"}</button>`
    : "";
  return `
    <section class="active-banner">
      <div>
        <h2>${escapeHtml(mode)} ${escapeHtml(paused)}</h2>
        <p>${escapeHtml(elapsed)} elapsed - ${escapeHtml(latestStatus.event_count || 0)} screenshots captured</p>
        ${fallback}
      </div>
      <div class="row-actions">
        ${pauseButton}
        <button class="danger" id="banner-stop">Stop recording</button>
      </div>
    </section>
  `;
}

function formatElapsed(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

async function renderReview(sessionId) {
  currentSessionId = sessionId;
  title.textContent = "Review";
  const data = await api.get(`/api/sessions/${sessionId}`);
  const session = data.session;
  const metadata = session.metadata || {};
  const events = session.events || [];
  const visibleEvents = reviewFilter === "highlights" ? events.filter((event) => event.highlight) : events;
  const eventCards = visibleEvents.map((event) => renderEventEditor(session.id, event)).join("");
  app.innerHTML = `
    <section class="card">
      <h2>${escapeHtml(metadata.activity || session.id)}</h2>
      <p class="muted">${escapeHtml(session.mode)} - ${escapeHtml(session.started)} - ${events.length} screenshots</p>
      <div class="actions">
        <button class="primary" id="export-session">Export HTML</button>
        <button class="secondary" id="export-pack">Export evidence pack</button>
        <button class="secondary" id="export-annotated-images">Export selected annotated images</button>
        <button class="secondary" id="export-original-images">Export selected clean images</button>
        <button class="secondary" id="export-both-images">Export both image versions</button>
        <button class="secondary" id="back-sessions">Back to sessions</button>
      </div>
    </section>
    <section class="review-toolbar">
      <button class="secondary ${reviewFilter === "all" ? "selected" : ""}" data-review-filter="all">All screenshots</button>
      <button class="secondary ${reviewFilter === "highlights" ? "selected" : ""}" data-review-filter="highlights">Highlights only</button>
      <button class="secondary" data-selection="all">Select all</button>
      <button class="secondary" data-selection="none">Select none</button>
      <button class="secondary" data-selection="highlights">Select highlights</button>
    </section>
    <section class="review-list">
      ${eventCards || "<p class='muted'>No screenshots match this filter.</p>"}
    </section>
  `;
  app.querySelector("#back-sessions").addEventListener("click", renderSessions);
  app.querySelector("#export-session").addEventListener("click", async () => {
    const result = await api.post(`/api/sessions/${sessionId}/export`);
    alert(`Exported HTML: ${result.html}\nExported PDF: ${result.pdf}`);
  });
  app.querySelector("#export-pack").addEventListener("click", async () => exportEvidencePack(sessionId));
  app.querySelector("#export-annotated-images").addEventListener("click", async () => exportImages(sessionId, "annotated"));
  app.querySelector("#export-original-images").addEventListener("click", async () => exportImages(sessionId, "original"));
  app.querySelector("#export-both-images").addEventListener("click", async () => exportImages(sessionId, "both"));
  app.querySelectorAll("[data-save-event]").forEach((button) => {
    button.addEventListener("click", async () => saveEvent(sessionId, button.dataset.saveEvent));
  });
  app.querySelectorAll("[data-update-marker]").forEach((button) => {
    button.addEventListener("click", async () => updateMarker(sessionId, button.dataset.updateMarker));
  });
  app.querySelectorAll("[data-delete-event]").forEach((button) => {
    button.addEventListener("click", async () => deleteEvent(sessionId, button.dataset.deleteEvent));
  });
  app.querySelectorAll("[data-redact-preset]").forEach((button) => {
    button.addEventListener("click", async () => redactPreset(sessionId, button.dataset.redactPreset, button.dataset.preset));
  });
  app.querySelectorAll("[data-redact-box]").forEach((button) => {
    button.addEventListener("click", async () => redactBox(sessionId, button.dataset.redactBox));
  });
  app.querySelectorAll("[data-restore-original]").forEach((button) => {
    button.addEventListener("click", async () => restoreOriginal(sessionId, button.dataset.restoreOriginal));
  });
  app.querySelectorAll("[data-review-filter]").forEach((button) => {
    button.addEventListener("click", async () => {
      reviewFilter = button.dataset.reviewFilter;
      await renderReview(sessionId);
    });
  });
  app.querySelectorAll("[data-selection]").forEach((button) => {
    button.addEventListener("click", async () => bulkSelectEvents(session, button.dataset.selection));
  });
}

function renderEventEditor(sessionId, event) {
  const tags = Array.isArray(event.tags) ? event.tags.join(", ") : "";
  const checked = event.highlight ? "checked" : "";
  const imageUrl = `/api/sessions/${encodeURIComponent(sessionId)}/screenshots/${encodeURIComponent(event.screenshot || "")}`;
  const redactionCount = Array.isArray(event.redactions) ? event.redactions.length : 0;
  const redactionLabel = redactionCount ? `<p class="redaction-count">${redactionCount} redaction${redactionCount === 1 ? "" : "s"} applied</p>` : "";
  const restoreButton = redactionCount ? `<button class="secondary" data-restore-original="${event.index}">Undo redactions</button>` : "";
  const selected = event.selected_for_export !== false ? "checked" : "";
  const markerEditor = event.type === "click" && Number.isFinite(Number(event.x)) && Number.isFinite(Number(event.y))
    ? renderEventMarkerEditor(event)
    : "";
  return `
    <article class="card event-editor">
      <div>
        <img class="event-thumb" src="${imageUrl}" alt="Screenshot ${escapeAttr(event.index || "")}">
        <p class="muted">${escapeHtml(event.type)} - ${escapeHtml(event.timestamp || "")}</p>
        ${redactionLabel}
      </div>
      <div class="form">
        <label>Title <input data-field="title" data-event="${event.index}" value="${escapeAttr(event.title || "")}"></label>
        <label>Staff note <textarea data-field="staff_note" data-event="${event.index}">${escapeHtml(event.staff_note || "")}</textarea></label>
        <label>CYP quote <textarea data-field="cyp_quote" data-event="${event.index}">${escapeHtml(event.cyp_quote || "")}</textarea></label>
        <label>Tags <input data-field="tags" data-event="${event.index}" value="${escapeAttr(tags)}"></label>
        <label class="check-row"><input type="checkbox" data-field="highlight" data-event="${event.index}" ${checked}> Mark as highlight</label>
        <label class="check-row"><input type="checkbox" data-field="selected_for_export" data-event="${event.index}" ${selected}> Include in export</label>
        ${renderRedactionHistory(event)}
        ${renderRedactionBoxEditor(event)}
        ${markerEditor}
        <div class="actions">
          <button class="primary" data-save-event="${event.index}">Save evidence note</button>
          ${restoreButton}
          <button class="danger" data-delete-event="${event.index}">Remove from report</button>
        </div>
      </div>
    </article>
  `;
}

function renderRedactionHistory(event) {
  const redactions = Array.isArray(event.redactions) ? event.redactions : [];
  if (!redactions.length) {
    return "";
  }
  const rows = redactions.map((redaction) => `
    <li>${escapeHtml(redaction.preset || "manual")} - x ${escapeHtml(redaction.x)}, y ${escapeHtml(redaction.y)}, ${escapeHtml(redaction.width)} x ${escapeHtml(redaction.height)}</li>
  `).join("");
  return `<ul class="redaction-history">${rows}</ul>`;
}

function renderRedactionBoxEditor(event) {
  return `
    <div class="redaction-editor">
      <button class="secondary" data-redact-preset="${event.index}" data-preset="top_strip" type="button">Top strip</button>
      <button class="secondary" data-redact-preset="${event.index}" data-preset="bottom_strip" type="button">Bottom strip</button>
      <button class="secondary" data-redact-preset="${event.index}" data-preset="left_strip" type="button">Left strip</button>
      <button class="secondary" data-redact-preset="${event.index}" data-preset="right_strip" type="button">Right strip</button>
      <label>X <input class="redaction-field" data-redaction-field="x" data-redaction-event="${event.index}" type="number" min="0" value="0"></label>
      <label>Y <input class="redaction-field" data-redaction-field="y" data-redaction-event="${event.index}" type="number" min="0" value="0"></label>
      <label>Width <input class="redaction-field" data-redaction-field="width" data-redaction-event="${event.index}" type="number" min="1" value="120"></label>
      <label>Height <input class="redaction-field" data-redaction-field="height" data-redaction-event="${event.index}" type="number" min="1" value="40"></label>
      <button class="secondary" data-redact-box="${event.index}" type="button">Apply redaction box</button>
    </div>
  `;
}

function renderEventMarkerEditor(event) {
  const marker = event.marker || {};
  const shape = marker.shape || "circle";
  const color = marker.color || "#ef233c";
  const size = marker.size || 32;
  const stroke = marker.stroke || 3;
  return `
    <div class="marker-editor">
      <label>Click marker shape
        <select data-marker-field="shape" data-marker-event="${event.index}">
          ${renderMarkerOption("circle", shape)}
          ${renderMarkerOption("square", shape)}
          ${renderMarkerOption("crosshair", shape)}
          ${renderMarkerOption("arrow", shape)}
        </select>
      </label>
      <label>Colour <input data-marker-field="color" data-marker-event="${event.index}" type="color" value="${escapeAttr(color)}"></label>
      <label>Size <input data-marker-field="size" data-marker-event="${event.index}" type="number" min="6" value="${escapeAttr(size)}"></label>
      <label>Stroke <input data-marker-field="stroke" data-marker-event="${event.index}" type="number" min="1" value="${escapeAttr(stroke)}"></label>
      <button class="secondary" data-update-marker="${event.index}" type="button">Update marker</button>
    </div>
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
    } else if (key === "selected_for_export") {
      payload.selected_for_export = field.checked;
    } else {
      payload[key] = field.value;
    }
  });
  await api.patch(`/api/sessions/${sessionId}/events/${eventIndex}`, payload);
  await renderReview(sessionId);
}

async function bulkSelectEvents(session, mode) {
  const events = session.events || [];
  for (const event of events) {
    const selected = mode === "all" || (mode === "highlights" && event.highlight);
    await api.patch(`/api/sessions/${session.id}/events/${event.index}`, { selected_for_export: selected });
  }
  await renderReview(session.id);
}

async function exportImages(sessionId, variant) {
  const result = await api.post(`/api/sessions/${sessionId}/export-images`, { variant });
  alert(`Exported image ZIP: ${result.zip}`);
}

async function exportEvidencePack(sessionId) {
  const result = await api.post(`/api/sessions/${sessionId}/export-pack`, {});
  alert(`Exported evidence pack: ${result.zip}`);
}

async function updateMarker(sessionId, eventIndex) {
  const fields = app.querySelectorAll(`[data-marker-event="${eventIndex}"]`);
  const payload = {};
  fields.forEach((field) => {
    const key = field.dataset.markerField;
    payload[key] = key === "size" || key === "stroke" ? Number(field.value) : field.value;
  });
  await api.post(`/api/sessions/${sessionId}/events/${eventIndex}/marker`, payload);
  await renderReview(sessionId);
}

async function deleteEvent(sessionId, eventIndex) {
  if (!confirm("Remove this screenshot from the report? The original image file stays in local storage for now.")) {
    return;
  }
  await api.delete(`/api/sessions/${sessionId}/events/${eventIndex}`);
  await renderReview(sessionId);
}

async function redactPreset(sessionId, eventIndex, preset) {
  if (!confirm("Apply this black redaction preset to the screenshot? A backup of the original is kept locally.")) {
    return;
  }
  await api.post(`/api/sessions/${sessionId}/events/${eventIndex}/redact`, { preset });
  await renderReview(sessionId);
}

async function redactBox(sessionId, eventIndex) {
  const fields = app.querySelectorAll(`[data-redaction-event="${eventIndex}"]`);
  const rect = {};
  fields.forEach((field) => {
    rect[field.dataset.redactionField] = Number(field.value);
  });
  if (!Number.isFinite(rect.x) || !Number.isFinite(rect.y) || !Number.isFinite(rect.width) || !Number.isFinite(rect.height)) {
    alert("Redaction box needs valid numbers.");
    return;
  }
  if (rect.width < 1 || rect.height < 1) {
    alert("Redaction box width and height must be at least 1.");
    return;
  }
  if (!confirm("Apply this black redaction box to the screenshot? A backup of the original is kept locally.")) {
    return;
  }
  await api.post(`/api/sessions/${sessionId}/events/${eventIndex}/redact`, { rect });
  await renderReview(sessionId);
}

async function restoreOriginal(sessionId, eventIndex) {
  if (!confirm("Undo all redactions on this screenshot by restoring the locally saved original?")) {
    return;
  }
  await api.post(`/api/sessions/${sessionId}/events/${eventIndex}/restore-original`, {});
  await renderReview(sessionId);
}

async function deleteSession(sessionId) {
  if (!confirm("Delete this session and its local screenshots? This cannot be undone.")) {
    return;
  }
  await api.delete(`/api/sessions/${sessionId}`);
  await renderSessions();
}

async function renderSettings() {
  title.textContent = "Settings";
  const data = await api.get("/api/settings");
  const storageData = await api.get("/api/storage");
  const settings = data.settings;
  const storage = storageData.storage;
  const warningClass = storage.warning ? "storage-warning active-warning" : "storage-warning";
  const warningText = storage.warning
    ? `Storage is above the ${storage.warning_mb} MB warning threshold.`
    : `Storage is below the ${storage.warning_mb} MB warning threshold.`;
  app.innerHTML = `
    <section class="card ${warningClass}">
      <h2>Local Storage</h2>
      <p><strong>${escapeHtml(storage.total_mb)} MB</strong> across ${escapeHtml(storage.session_count)} session${storage.session_count === 1 ? "" : "s"}.</p>
      <p class="muted">${escapeHtml(warningText)}</p>
      <p class="muted">${escapeHtml(storage.root)}</p>
      <div class="actions">
        <button class="danger" id="cleanup-retention">Delete sessions older than retention period</button>
      </div>
    </section>
    <form class="card form" id="settings-form">
      <h2>Settings</h2>
      <label>Observation screenshot interval seconds <input name="observation_interval_seconds" type="number" min="5" value="${escapeAttr(settings.observation_interval_seconds)}"></label>
      <label>Retention days <input name="retention_days" type="number" min="1" value="${escapeAttr(settings.retention_days)}"></label>
      <label>Storage warning MB <input name="storage_warning_mb" type="number" min="1" value="${escapeAttr(settings.storage_warning_mb)}"></label>
      <label>Default evidence purpose
        <select name="default_evidence_purpose">
          ${renderPurposeOption("UAS evidence", settings.default_evidence_purpose)}
          ${renderPurposeOption("Behaviour support", settings.default_evidence_purpose)}
          ${renderPurposeOption("Project progress", settings.default_evidence_purpose)}
          ${renderPurposeOption("General observation", settings.default_evidence_purpose)}
        </select>
      </label>
      <label>Click marker shape
        <select name="marker_shape">
          ${renderMarkerOption("circle", settings.marker_shape)}
          ${renderMarkerOption("square", settings.marker_shape)}
          ${renderMarkerOption("crosshair", settings.marker_shape)}
          ${renderMarkerOption("arrow", settings.marker_shape)}
        </select>
      </label>
      <label>Click marker colour <input name="marker_color" type="color" value="${escapeAttr(settings.marker_color)}"></label>
      <label>Click marker size <input name="marker_size" type="number" min="6" value="${escapeAttr(settings.marker_size)}"></label>
      <label>Click marker stroke <input name="marker_stroke" type="number" min="1" value="${escapeAttr(settings.marker_stroke)}"></label>
      <div class="actions">
        <button class="primary" type="submit">Save settings</button>
      </div>
    </form>
  `;
  app.querySelector("#settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.patch("/api/settings", {
      observation_interval_seconds: Number(form.get("observation_interval_seconds")),
      retention_days: Number(form.get("retention_days")),
      storage_warning_mb: Number(form.get("storage_warning_mb")),
      default_evidence_purpose: form.get("default_evidence_purpose"),
      marker_shape: form.get("marker_shape"),
      marker_color: form.get("marker_color"),
      marker_size: Number(form.get("marker_size")),
      marker_stroke: Number(form.get("marker_stroke")),
    });
    await renderSettings();
  });
  app.querySelector("#cleanup-retention").addEventListener("click", async () => {
    if (!confirm(`Delete sessions older than ${settings.retention_days} days? This removes local screenshots and exports.`)) {
      return;
    }
    const result = await api.post("/api/retention/cleanup", {});
    alert(`Deleted ${result.deleted.length} old session${result.deleted.length === 1 ? "" : "s"}.`);
    await renderSettings();
  });
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

function renderPurposeOption(value, selectedValue) {
  const selected = value === selectedValue ? "selected" : "";
  return `<option ${selected}>${escapeHtml(value)}</option>`;
}

function renderMarkerOption(value, selectedValue) {
  const selected = value === selectedValue ? "selected" : "";
  return `<option value="${escapeAttr(value)}" ${selected}>${escapeHtml(value)}</option>`;
}

setInterval(async () => {
  await refreshStatus();
}, 5000);

render(currentView).then(bindBannerStop);
