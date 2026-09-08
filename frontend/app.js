const app = document.querySelector("#app");
const title = document.querySelector("#page-title");
const statusPill = document.querySelector("#status");
let currentView = "home";
let currentSessionId = null;
let latestStatus = { active: false };
let reviewFilter = "all";
let reviewSearch = "";
let isRendering = false;
let settingsFeedback = "";
let dataLocationFeedback = "";
let reviewSession = null;
const reviewDrafts = new Map();
const sessionFilters = { query: "", from: "", to: "" };

async function apiRequest(path, method = "GET", body) {
  const response = await fetch(path, {
    method,
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(`Panoptix returned an unreadable response (${response.status}).`);
  }
  if (!response.ok || result.error) {
    throw new Error(result.error || `Request failed (${response.status}).`);
  }
  return result;
}

const api = {
  get: (path) => apiRequest(path),
  post: (path, body = {}) => apiRequest(path, "POST", body),
  patch: (path, body = {}) => apiRequest(path, "PATCH", body),
  delete: (path) => apiRequest(path, "DELETE"),
};

window.addEventListener("unhandledrejection", (event) => {
  event.preventDefault();
  alert(event.reason?.message || "The operation failed. Please try again.");
});

function draftKey(sessionId, screenshot) {
  return `${sessionId}/${screenshot}`;
}

function rememberReviewDrafts() {
  if (currentView !== "review" || !reviewSession) return;
  const visible = new Map();
  app.querySelectorAll("[data-event][data-field]").forEach((field) => {
    const saved = reviewSession.events.find((event) => String(event.index) === field.dataset.event);
    if (!saved) return;
    const key = draftKey(reviewSession.id, saved.screenshot);
    if (!visible.has(key)) visible.set(key, {});
    const name = field.dataset.field;
    const value = name === "tags" ? field.value.split(",").map((tag) => tag.trim()).filter(Boolean)
      : field.type === "checkbox" ? field.checked : field.value;
    const original = name === "selected_for_export" ? saved[name] !== false
      : name === "highlight" ? Boolean(saved[name]) : saved[name] || (name === "tags" ? [] : "");
    if (JSON.stringify(value) !== JSON.stringify(original)) visible.get(key)[name] = value;
  });
  visible.forEach((draft, key) => {
    if (Object.keys(draft).length) reviewDrafts.set(key, draft);
    else reviewDrafts.delete(key);
  });
  updateDraftIndicator();
}

function updateDraftIndicator() {
  const count = [...reviewDrafts.keys()].filter((key) => key.startsWith(`${currentSessionId}/`)).length;
  const label = app.querySelector("#draft-status");
  if (label) label.textContent = count ? `${count} screenshot${count === 1 ? " has" : "s have"} unsaved changes` : "All changes saved";
  const button = app.querySelector("#save-all-notes");
  if (button) button.disabled = count === 0;
}

window.addEventListener("beforeunload", (event) => {
  rememberReviewDrafts();
  if (reviewDrafts.size) {
    event.preventDefault();
    event.returnValue = "";
  }
});
app.addEventListener("input", rememberReviewDrafts);
app.addEventListener("change", rememberReviewDrafts);

document.querySelectorAll(".sidebar button").forEach((button) => {
  button.addEventListener("click", () => render(button.dataset.view));
});

async function refreshStatus() {
  const previousSignature = statusSignature(latestStatus);
  const status = await api.get("/api/status");
  latestStatus = status;
  statusPill.textContent = status.active ? `${status.mode} recording - ${status.event_count} screenshots` : "Idle";
  if (status.active && status.mode === "background" && status.skipped_unchanged) {
    statusPill.textContent += ` - ${status.skipped_unchanged} skipped`;
  }
  if (status.hook_error) {
    statusPill.textContent += " - manual fallback";
  }
  if (status.capture_error) statusPill.textContent = status.capture_error;
  else if (status.storage_error) statusPill.textContent = `Storage unavailable: ${status.storage_error}`;
  else if (status.paused) statusPill.textContent += " - paused";
  statusPill.classList.toggle("active", status.active);
  updateLiveStatusDisplay(status);
  if (!isRendering && !["sessions", "review", "settings", "trash"].includes(currentView) && previousSignature !== statusSignature(status)) {
    await render(currentView);
  }
  return status;
}

function statusSignature(status) {
  return [
    status.active ? "active" : "idle",
    status.session_id || "",
    status.mode || "",
    status.paused ? "paused" : "running",
    status.capture_error || "",
  ].join("|");
}

function updateLiveStatusDisplay(status) {
  document.querySelectorAll("[data-live-event-count]").forEach((element) => {
    element.textContent = String(status.event_count || 0);
  });
  document.querySelectorAll("[data-live-elapsed]").forEach((element) => {
    element.textContent = formatElapsed(status.elapsed_seconds || 0);
  });
  document.querySelectorAll("[data-live-skipped]").forEach((element) => {
    element.textContent = String(status.skipped_unchanged || 0);
  });
  document.querySelectorAll("[data-system-skipped]").forEach((element) => {
    element.textContent = String(status.skipped_unchanged || 0);
  });
}

function setActive(view) {
  currentView = view;
  document.querySelectorAll(".sidebar button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
}

async function render(view) {
  rememberReviewDrafts();
  isRendering = true;
  setActive(view);
  try {
    await refreshStatus();
    if (view === "home") {
      renderHome();
    } else if (view === "evidence") {
      await renderStartForm("evidence", "Evidence Capture");
    } else if (view === "observation") {
      await renderStartForm("observation", "Observation Mode");
    } else if (view === "sessions") {
      await renderSessions();
    } else if (view === "review") {
      await renderReview(currentSessionId);
    } else if (view === "trash") {
      await renderTrash();
    } else {
      await renderSettings();
    }
    bindBannerStop();
    bindPauseResume();
  } finally {
    isRendering = false;
  }
}

function renderHome() {
  title.textContent = "Home";
  app.innerHTML = `
    ${renderActiveBanner()}
    ${renderSystemStatus()}
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
}

async function renderSessions() {
  rememberReviewDrafts();
  setActive("sessions");
  title.textContent = "Sessions";
  const data = await api.get("/api/sessions");
  app.innerHTML = `<section class="card">
    <div class="session-filters">
      <label>Search sessions <input id="session-search" type="search" placeholder="Activity, mode or session ID" value="${escapeAttr(sessionFilters.query)}"></label>
      <label>From <input id="session-from" type="date" value="${escapeAttr(sessionFilters.from)}"></label>
      <label>To <input id="session-to" type="date" value="${escapeAttr(sessionFilters.to)}"></label>
      <button class="secondary" id="clear-session-filters">Clear filters</button>
      <button class="secondary" id="show-trash">Deleted sessions</button>
    </div>
    <p id="session-count" class="muted" role="status"></p><div id="session-rows"></div>
  </section>`;
  const updateRows = () => {
    sessionFilters.query = app.querySelector("#session-search").value;
    sessionFilters.from = app.querySelector("#session-from").value;
    sessionFilters.to = app.querySelector("#session-to").value;
    const terms = sessionFilters.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    const sessions = data.sessions.filter((session) => {
      const date = session.started.slice(0, 10);
      const text = `${session.title} ${session.mode} ${session.id}`.toLowerCase();
      return terms.every((term) => text.includes(term)) && (!sessionFilters.from || date >= sessionFilters.from) && (!sessionFilters.to || date <= sessionFilters.to);
    });
    app.querySelector("#session-count").textContent = sessionFilters.from && sessionFilters.to && sessionFilters.from > sessionFilters.to
      ? "From date must be on or before To date." : `${sessions.length} of ${data.sessions.length} sessions shown`;
    const rows = sessions.map((session) => `
    <div class="session-row">
      <div>
        <strong>${escapeHtml(session.title)}</strong>
        <div class="muted">${escapeHtml(session.mode)} - ${escapeHtml(session.started)} - ${session.event_count} screenshots</div>
      </div>
      <div class="row-actions">
        <button class="secondary" data-open="${escapeAttr(session.id)}">Review</button>
        <button class="danger" data-delete-session="${escapeAttr(session.id)}">Move to deleted</button>
      </div>
    </div>
    `).join("");
    app.querySelector("#session-rows").innerHTML = rows || "<p class='muted'>No sessions match these filters.</p>";
    app.querySelectorAll("[data-open]").forEach((button) => {
      button.addEventListener("click", async () => {
        await renderReview(button.dataset.open);
      });
    });
    app.querySelectorAll("[data-delete-session]").forEach((button) => {
      button.addEventListener("click", async () => deleteSession(button.dataset.deleteSession));
    });
  };
  for (const id of ["session-search", "session-from", "session-to"]) app.querySelector(`#${id}`).addEventListener("input", updateRows);
  app.querySelector("#clear-session-filters").onclick = () => {
    for (const id of ["session-search", "session-from", "session-to"]) app.querySelector(`#${id}`).value = "";
    updateRows();
  };
  app.querySelector("#show-trash").onclick = renderTrash;
  updateRows();
}

function bindBannerStop() {
  const button = app.querySelector("#banner-stop");
  if (!button) {
    return;
  }
  button.onclick = async () => {
    button.disabled = true;
    try {
      await api.post("/api/record/stop");
      await render(currentView);
    } finally { button.disabled = false; }
  };
}

function bindPauseResume() {
  const button = app.querySelector("#banner-pause");
  if (!button) {
    return;
  }
  button.onclick = async () => {
    button.disabled = true;
    try {
      await api.post(latestStatus.paused ? "/api/record/resume" : "/api/record/pause");
      await render(currentView);
    } finally { button.disabled = false; }
  };
}

function renderActiveBanner() {
  if (!latestStatus.active) {
    return "";
  }
  const mode = latestStatus.mode === "observation"
    ? "Observation Mode"
    : latestStatus.mode === "background"
      ? "Background Capture"
      : "Evidence Capture";
  const elapsed = formatElapsed(latestStatus.elapsed_seconds || 0);
  const fallback = latestStatus.hook_error ? `<p class="muted">${escapeHtml(latestStatus.hook_error)}</p>` : "";
  const skipped = latestStatus.mode === "background"
    ? `<p class="muted">Skipped unchanged frames: <span data-live-skipped>${escapeHtml(latestStatus.skipped_unchanged || 0)}</span></p>`
    : "";
  const paused = latestStatus.paused ? "Paused" : "Active";
  const pauseButton = `<button class="secondary" id="banner-pause">${latestStatus.paused ? "Resume" : "Pause"}</button>`;
  return `
    <section class="active-banner">
      <div>
        <h2>${escapeHtml(mode)} ${escapeHtml(paused)}</h2>
        <p><span data-live-elapsed>${escapeHtml(elapsed)}</span> elapsed - <span data-live-event-count>${escapeHtml(latestStatus.event_count || 0)}</span> screenshots captured</p>
        ${skipped}
        ${fallback}
      </div>
      <div class="row-actions">
        ${pauseButton}
        <button class="danger" id="banner-stop">Stop recording</button>
      </div>
    </section>
  `;
}

function renderSystemStatus() {
  const background = latestStatus.background || {};
  const hotkey = latestStatus.hotkey || {};
  const startup = latestStatus.startup || {};
  const exportDestination = latestStatus.export_destination || {};
  const backgroundState = background.enabled
    ? (background.window_active ? "Scheduled capture block is active" : "Waiting for next scheduled block")
    : "Disabled";
  const changeDetection = background.change_detection ? "skipping unchanged frames" : "saving every frame";
  const exportWarning = exportDestination.warning
    ? `<p class="status-warning"><strong>Export folder warning</strong>: ${escapeHtml(exportDestination.warning)}</p>`
    : `<p class="muted">Export folder: ${escapeHtml(exportDestination.path || "Panoptix local exports")}</p>`;
  const dataLocation = latestStatus.data_location || {};
  const dataWarning = dataLocation.warning
    ? `<p class="status-warning"><strong>Screenshot folder warning</strong>: ${escapeHtml(dataLocation.warning)}</p>`
    : `<p class="muted">Screenshot folder: ${escapeHtml(dataLocation.active_path || dataLocation.path || "Panoptix local storage")}</p>`;
  const hotkeyStatus = hotkey.enabled
    ? `${hotkey.shortcut || "not set"}${hotkey.error ? ` - ${hotkey.error}` : ""}`
    : "Disabled";
  return `
    <section class="card system-status">
      <h2>Background Status</h2>
      <div class="status-grid">
        <div>
          <strong>Scheduled passive capture</strong>
          <p class="muted">${escapeHtml(backgroundState)} - ${escapeHtml(background.window || "daily window not set")} - ${escapeHtml(background.interval_seconds || 5)}s, ${escapeHtml(changeDetection)}</p>
        </div>
        <div>
          <strong>Skipped unchanged frames</strong>
          <p class="muted" data-system-skipped>${escapeHtml(latestStatus.skipped_unchanged || 0)}</p>
        </div>
        <div>
          <strong>Manual hotkey</strong>
          <p class="muted">${escapeHtml(hotkeyStatus)}</p>
        </div>
        <div>
          <strong>Windows startup</strong>
          <p class="muted">${startup.requested ? "Requested" : "Off"} - ${startup.installed ? "installed" : "not installed"}</p>
        </div>
      </div>
      ${exportWarning}
      ${dataWarning}
      ${latestStatus.capture_error ? `<p class="status-warning">${escapeHtml(latestStatus.capture_error)}</p>` : ""}
      ${background.error ? `<p class="status-warning">Schedule error: ${escapeHtml(background.error)}</p>` : ""}
    </section>
  `;
}

function formatElapsed(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

async function renderReview(sessionId, preserveVisible = true) {
  if (preserveVisible) rememberReviewDrafts();
  setActive("review");
  currentSessionId = sessionId;
  title.textContent = "Review";
  const data = await api.get(`/api/sessions/${sessionId}`);
  const session = data.session;
  reviewSession = session;
  const metadata = session.metadata || {};
  const events = (session.events || []).map((event) => ({ ...event, ...reviewDrafts.get(draftKey(sessionId, event.screenshot)) }));
  const visibleEvents = PanoptixReviewFilters.filterReviewEvents(events, reviewFilter, reviewSearch);
  const selectedImageCount = events.filter((event) => event.selected_for_export !== false).length;
  const eventCards = visibleEvents.map((event) => renderEventEditor(session.id, event)).join("");
  const searchFeedback = reviewSearch
    ? `<p class="review-feedback">Search active: ${escapeHtml(reviewSearch)} <button class="secondary compact" id="clear-review-search">Clear search</button></p>`
    : "";
  app.innerHTML = `
    <section class="card">
      <h2>${escapeHtml(metadata.activity || session.id)}</h2>
      <p class="muted">${escapeHtml(session.mode)} - ${escapeHtml(session.started)} - ${events.length} screenshots - ${selectedImageCount} selected for export</p>
      <label class="check-row privacy-check">
        <input id="privacy-review-confirmed" type="checkbox">
        Personal data check: I have checked selected screenshots for personal data before submission.
      </label>
      <label class="check-row">
        <input id="pack-include-originals" type="checkbox">
        Include unredacted originals in the evidence pack (reveals data hidden by redactions).
      </label>
      <p class="muted">Unsaved notes and selections stay in this tab when you filter or navigate. Export saves these edits.</p>
      <p id="draft-status" role="status" aria-live="polite"></p>
      <div class="actions">
        <button class="primary" id="save-all-notes">Save all notes</button>
        <button class="secondary" id="open-export-folder">Open export folder</button>
        <button class="primary" id="export-session">Export HTML / PDF</button>
        <button class="secondary" id="export-pack">Export evidence pack</button>
        <button class="secondary" id="verify-pack">Verify evidence pack</button>
        <button class="secondary" id="export-annotated-images">Export selected annotated images</button>
        <button class="secondary" id="export-original-images">Export selected unredacted originals</button>
        <button class="secondary" id="export-both-images">Export both image versions</button>
        <button class="secondary" id="back-sessions">Back to sessions</button>
      </div>
    </section>
    <section class="review-toolbar">
      <label class="review-search">Search evidence
        <input id="review-search" type="search" value="${escapeAttr(reviewSearch)}" placeholder="Search notes, quotes, tags, type">
      </label>
      <button class="secondary" id="apply-review-search">Apply search</button>
      <button class="secondary ${reviewFilter === "all" ? "selected" : ""}" data-review-filter="all">All screenshots</button>
      <button class="secondary ${reviewFilter === "highlights" ? "selected" : ""}" data-review-filter="highlights">Highlights only</button>
      <button class="secondary ${reviewFilter === "selected" ? "selected" : ""}" data-review-filter="selected">Selected</button>
      <button class="secondary ${reviewFilter === "unselected" ? "selected" : ""}" data-review-filter="unselected">Not selected</button>
      <button class="secondary ${reviewFilter === "redacted" ? "selected" : ""}" data-review-filter="redacted">Redacted</button>
      <button class="secondary ${reviewFilter === "clicks" ? "selected" : ""}" data-review-filter="clicks">Clicks</button>
      <button class="secondary ${reviewFilter === "observations" ? "selected" : ""}" data-review-filter="observations">Observations</button>
      <button class="secondary" data-selection="all">Select all</button>
      <button class="secondary" data-selection="none">Select none</button>
      <button class="secondary" data-selection="highlights">Select highlights</button>
    </section>
    ${searchFeedback}
    <p class="muted review-count">${visibleEvents.length} of ${events.length} screenshots shown</p>
    <section class="review-list">
      ${eventCards || "<p class='muted'>No screenshots match this filter.</p>"}
    </section>
  `;
  app.querySelector("#back-sessions").addEventListener("click", renderSessions);
  app.querySelector("#open-export-folder").onclick = () => api.post("/api/exports/open-folder", { session_id: sessionId });
  app.querySelector("#save-all-notes").onclick = async (event) => {
    event.currentTarget.disabled = true;
    try {
      await saveReviewDrafts(sessionId);
      await renderReview(sessionId, false);
    } finally { updateDraftIndicator(); }
  };
  app.querySelectorAll("[data-zoom-event]").forEach((button) => {
    button.onclick = () => openScreenshotViewer(sessionId, session.events.find((event) => String(event.index) === button.dataset.zoomEvent));
  });
  updateDraftIndicator();
  app.querySelector("#export-session").addEventListener("click", async () => exportSession(sessionId));
  app.querySelector("#export-pack").addEventListener("click", async () => exportEvidencePack(sessionId));
  app.querySelector("#verify-pack").addEventListener("click", async () => verifyEvidencePack(sessionId));
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
  app.querySelector("#apply-review-search").addEventListener("click", async () => {
    reviewSearch = app.querySelector("#review-search").value;
    await renderReview(sessionId);
  });
  app.querySelector("#clear-review-search")?.addEventListener("click", async () => {
    reviewSearch = "";
    await renderReview(sessionId);
  });
  app.querySelector("#review-search").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
      return;
    }
    reviewSearch = event.target.value;
    await renderReview(sessionId);
  });
  app.querySelectorAll("[data-selection]").forEach((button) => {
    button.addEventListener("click", async () => bulkSelectEvents(session, button.dataset.selection));
  });
}

function renderEventEditor(sessionId, event) {
  const tags = Array.isArray(event.tags) ? event.tags.join(", ") : "";
  const checked = event.highlight ? "checked" : "";
  const cacheKey = screenshotVersion(event);
  const imageUrl = `/api/sessions/${encodeURIComponent(sessionId)}/screenshots/${encodeURIComponent(event.screenshot || "")}?v=${encodeURIComponent(cacheKey)}`;
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
        <button class="secondary" data-zoom-event="${event.index}">Zoom / drag to redact</button>
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

function screenshotVersion(event) {
  const marker = event.marker ? JSON.stringify(event.marker) : "";
  const redactionCount = Array.isArray(event.redactions) ? event.redactions.length : 0;
  return [event.screenshot || "", marker, redactionCount].join("-");
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
  rememberReviewDrafts();
  const event = reviewSession.events.find((item) => String(item.index) === String(eventIndex));
  await persistReviewDraft(sessionId, event.screenshot);
  await renderReview(sessionId, false);
}

async function persistReviewDraft(sessionId, screenshot) {
  const key = draftKey(sessionId, screenshot);
  const draft = { ...reviewDrafts.get(key) };
  if (!Object.keys(draft).length) return;
  const latest = (await api.get(`/api/sessions/${sessionId}`)).session;
  const event = latest.events.find((item) => item.screenshot === screenshot);
  if (!event) throw new Error("This screenshot was removed elsewhere. Your unsaved note is still in this tab.");
  const result = await api.patch(`/api/sessions/${sessionId}/events/${event.index}`, { ...draft, expected_screenshot: screenshot });
  // Keep edits typed while the save was in flight.
  const remaining = { ...reviewDrafts.get(key) };
  Object.keys(draft).forEach((field) => {
    if (JSON.stringify(remaining[field]) === JSON.stringify(draft[field])) delete remaining[field];
  });
  if (Object.keys(remaining).length) reviewDrafts.set(key, remaining);
  else reviewDrafts.delete(key);
  reviewSession = result.session;
  updateDraftIndicator();
}

async function saveReviewDrafts(sessionId) {
  rememberReviewDrafts();
  for (const key of [...reviewDrafts.keys()]) {
    if (key.startsWith(`${sessionId}/`)) await persistReviewDraft(sessionId, key.slice(sessionId.length + 1));
  }
  reviewSession = (await api.get(`/api/sessions/${sessionId}`)).session;
}

async function bulkSelectEvents(session, mode) {
  rememberReviewDrafts();
  const events = session.events || [];
  for (const event of events) {
    const selected = mode === "all" || (mode === "highlights" && event.highlight);
    await api.patch(`/api/sessions/${session.id}/events/${event.index}`, { selected_for_export: Boolean(selected), expected_screenshot: event.screenshot });
    const key = draftKey(session.id, event.screenshot);
    const draft = reviewDrafts.get(key);
    if (draft) {
      delete draft.selected_for_export;
      if (!Object.keys(draft).length) reviewDrafts.delete(key);
    }
  }
  await renderReview(session.id, false);
}

function requirePrivacyReview() {
  const checkbox = app.querySelector("#privacy-review-confirmed");
  if (checkbox?.checked) {
    return true;
  }
  alert("Before exporting, check selected screenshots for personal data and tick the Personal data check box.");
  checkbox?.focus();
  return false;
}

function requireSelectedScreenshots() {
  const selectedCount = (reviewSession?.events || []).filter((event) => event.selected_for_export !== false).length;
  if (selectedCount > 0) {
    return true;
  }
  alert("No screenshots are currently selected for export.");
  return false;
}

async function exportSession(sessionId) {
  if (!requirePrivacyReview()) {
    return;
  }
  await saveReviewDrafts(sessionId);
  if (!requireSelectedScreenshots()) return;
  const result = await api.post(`/api/sessions/${sessionId}/export`);
  alert(`Exported HTML: ${result.html}\nExported PDF: ${result.pdf}`);
}

async function exportImages(sessionId, variant) {
  if (!requirePrivacyReview()) {
    return;
  }
  if (variant !== "annotated" && !confirmOriginalExport()) return;
  await saveReviewDrafts(sessionId);
  if (!requireSelectedScreenshots()) {
    return;
  }
  const result = await api.post(`/api/sessions/${sessionId}/export-images`, { variant });
  alert(`Exported image ZIP: ${result.zip}`);
}

async function exportEvidencePack(sessionId) {
  if (!requirePrivacyReview()) {
    return;
  }
  const includeOriginals = app.querySelector("#pack-include-originals")?.checked === true;
  if (includeOriginals && !confirmOriginalExport()) return;
  await saveReviewDrafts(sessionId);
  if (!requireSelectedScreenshots()) return;
  const result = await api.post(`/api/sessions/${sessionId}/export-pack`, { include_originals: includeOriginals });
  alert(`Exported evidence pack: ${result.zip}`);
}

function confirmOriginalExport() {
  return confirm("This export includes UNREDACTED originals. Personal data hidden by black boxes will be visible to recipients. Include these originals?");
}

async function verifyEvidencePack(sessionId) {
  const result = await api.post(`/api/sessions/${sessionId}/verify-pack`, {});
  const message = result.ok
    ? `Evidence pack verified: ${result.checked} files checked.`
    : `Evidence pack failed verification: ${result.failure_count} issue${result.failure_count === 1 ? "" : "s"}.`;
  alert(message);
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
  rememberReviewDrafts();
  const screenshot = reviewSession.events.find((event) => String(event.index) === String(eventIndex))?.screenshot;
  await api.delete(`/api/sessions/${sessionId}/events/${eventIndex}`);
  reviewDrafts.delete(draftKey(sessionId, screenshot));
  await renderReview(sessionId, false);
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
  if (!confirm("Move this session and its local screenshots/exports to Deleted sessions? You can restore saved evidence there. Unsaved drafts for this session will be discarded. Reports exported to other folders stay where they are.")) {
    return;
  }
  await api.delete(`/api/sessions/${sessionId}`);
  for (const key of reviewDrafts.keys()) if (key.startsWith(`${sessionId}/`)) reviewDrafts.delete(key);
  await renderSessions();
}

function showDialog(contents, className = "") {
  const dialog = document.createElement("dialog");
  dialog.className = `app-dialog ${className}`;
  dialog.setAttribute("aria-labelledby", "dialog-title");
  dialog.innerHTML = contents;
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.querySelector("[data-close-dialog]").onclick = () => dialog.close();
  document.body.append(dialog);
  dialog.showModal();
  return dialog;
}

async function renderTrash() {
  rememberReviewDrafts();
  setActive("trash");
  title.textContent = "Deleted sessions";
  const data = await api.get("/api/trash");
  app.innerHTML = `<section class="card">
    <h2>Restore deleted sessions</h2>
    <p class="muted">Sessions, screenshots and local exports are kept here until restored. They still use disk space; there is no automatic permanent deletion. Reports exported to other folders are unaffected.</p>
    <button class="secondary" id="back-sessions">Back to sessions</button>
    ${data.sessions.map((entry) => `<div class="session-row">
      <div><strong>${escapeHtml(entry.title)}</strong><p class="muted">Deleted ${escapeHtml(entry.deleted_at)}</p></div>
      <button class="primary" data-restore-session="${escapeAttr(entry.trash_id)}">Restore</button>
    </div>`).join("") || "<p>No deleted sessions.</p>"}
  </section>`;
  app.querySelector("#back-sessions").onclick = renderSessions;
  app.querySelectorAll("[data-restore-session]").forEach((button) => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        await api.post(`/api/trash/${button.dataset.restoreSession}/restore`);
        await renderTrash();
      } finally { button.disabled = false; }
    };
  });
}

async function previewRetention() {
  const preview = await api.get("/api/retention/preview");
  const dialog = showDialog(`<h2 id="dialog-title">Retention cleanup preview</h2>
    <p>${preview.sessions.length} session${preview.sessions.length === 1 ? "" : "s"} started before ${escapeHtml(preview.cutoff)} (${preview.retention_days} days).</p>
    <p>These will move to Deleted sessions and can be restored. Disk space is retained. The active recording is protected.</p>
    <div class="cleanup-list">${preview.sessions.map((session) => `<p><strong>${escapeHtml(session.title)}</strong><br>${escapeHtml(session.started)} · ${session.event_count} screenshots</p>`).join("") || "<p>No sessions are eligible.</p>"}</div>
    <div class="actions"><button class="danger" id="confirm-cleanup" ${preview.sessions.length ? "" : "disabled"}>Move ${preview.sessions.length} sessions to deleted</button><button class="secondary" data-close-dialog>Cancel</button></div>`);
  let cleaning = false;
  dialog.addEventListener("cancel", (event) => { if (cleaning) event.preventDefault(); });
  dialog.querySelector("#confirm-cleanup").onclick = async (event) => {
    const button = event.currentTarget;
    cleaning = true;
    button.disabled = true;
    dialog.querySelector("[data-close-dialog]").disabled = true;
    try {
      await api.post("/api/retention/cleanup", { session_ids: preview.sessions.map((session) => session.id) });
      dialog.close();
      await renderTrash();
    } finally {
      cleaning = false;
      button.disabled = false;
      dialog.querySelector("[data-close-dialog]").disabled = false;
    }
  };
}

function openScreenshotViewer(sessionId, event) {
  const url = `/api/sessions/${encodeURIComponent(sessionId)}/screenshots/${encodeURIComponent(event.screenshot)}`;
  const dialog = showDialog(`<h2 id="dialog-title">Screenshot ${event.index}</h2>
    <div class="actions viewer-tools">
      <label>Zoom <select id="image-zoom"><option value="fit">Fit</option><option value="1">100%</option><option value="1.5">150%</option><option value="2">200%</option><option value="4">400%</option></select></label>
      <button class="danger" id="apply-drag-redaction" disabled>Apply redaction</button>
      <button class="secondary" id="clear-drag-selection">Clear selection</button>
      <button class="secondary" data-close-dialog>Close</button>
    </div>
    <p id="selection-status" role="status">Drag over the image to select a black redaction box. Zoom in and scroll for detail, or use the coordinate fields in Review.</p>
    <div class="image-viewport"><div class="image-stage"><img class="zoom-image" alt="Screenshot ${event.index}" draggable="false"><div class="drag-selection" hidden></div></div></div>`, "image-dialog");
  const image = dialog.querySelector(".zoom-image");
  const viewport = dialog.querySelector(".image-viewport");
  const overlay = dialog.querySelector(".drag-selection");
  const apply = dialog.querySelector("#apply-drag-redaction");
  const feedback = dialog.querySelector("#selection-status");
  let start = null, selection = null, scale = 1, modified = false, busy = false;
  const drawSelection = () => {
    overlay.hidden = !selection;
    if (selection) Object.assign(overlay.style, { left: `${selection.x * scale}px`, top: `${selection.y * scale}px`, width: `${selection.width * scale}px`, height: `${selection.height * scale}px` });
    apply.disabled = !selection || busy;
    dialog.querySelector("[data-close-dialog]").disabled = busy;
    dialog.querySelector("#image-zoom").disabled = busy;
    dialog.querySelector("#clear-drag-selection").disabled = busy;
  };
  const zoom = () => {
    if (!image.naturalWidth) return;
    const value = dialog.querySelector("#image-zoom").value;
    scale = value === "fit" ? Math.min(1, (viewport.clientWidth - 16) / image.naturalWidth, window.innerHeight * 0.6 / image.naturalHeight) : Number(value);
    image.style.width = `${image.naturalWidth * scale}px`;
    image.style.height = `${image.naturalHeight * scale}px`;
    drawSelection();
  };
  const point = (pointer) => {
    const bounds = image.getBoundingClientRect();
    return { x: Math.max(0, Math.min(image.naturalWidth, (pointer.clientX - bounds.left) * image.naturalWidth / bounds.width)), y: Math.max(0, Math.min(image.naturalHeight, (pointer.clientY - bounds.top) * image.naturalHeight / bounds.height)) };
  };
  image.onload = zoom;
  image.onerror = () => { feedback.textContent = "The screenshot could not be loaded."; apply.disabled = true; };
  image.src = `${url}?v=${Date.now()}`;
  dialog.querySelector("#image-zoom").onchange = zoom;
  image.onpointerdown = (pointer) => {
    if (busy || pointer.button !== 0 || !image.naturalWidth) return;
    pointer.preventDefault();
    start = point(pointer);
    selection = null;
    image.setPointerCapture(pointer.pointerId);
    drawSelection();
  };
  image.onpointermove = (pointer) => {
    if (!start) return;
    const end = point(pointer);
    const x = Math.floor(Math.min(start.x, end.x)), y = Math.floor(Math.min(start.y, end.y));
    const width = Math.ceil(Math.max(start.x, end.x)) - x, height = Math.ceil(Math.max(start.y, end.y)) - y;
    selection = width > 0 && height > 0 ? { x, y, width, height } : null;
    drawSelection();
    if (selection) feedback.textContent = `Selected x ${x}, y ${y}, width ${width}, height ${height} pixels. Apply redaction to save it.`;
  };
  image.onpointerup = (pointer) => {
    if (!start) return;
    image.onpointermove(pointer);
    start = null;
    if (image.hasPointerCapture(pointer.pointerId)) image.releasePointerCapture(pointer.pointerId);
  };
  image.onpointercancel = () => { start = null; selection = null; drawSelection(); };
  dialog.querySelector("#clear-drag-selection").onclick = () => {
    start = null; selection = null; drawSelection();
    feedback.textContent = "Selection cleared. Drag to select another area.";
  };
  apply.onclick = async () => {
    if (!selection || busy) return;
    busy = true; drawSelection();
    try {
      await api.post(`/api/sessions/${sessionId}/events/${event.index}/redact`, { rect: selection, expected_screenshot: event.screenshot });
      modified = true; selection = null;
      image.src = `${url}?v=${Date.now()}`;
      feedback.textContent = "Redaction saved. Select another area or close to return to Review.";
    } finally { busy = false; drawSelection(); }
  };
  dialog.addEventListener("close", () => {
    if (modified && currentView === "review" && currentSessionId === sessionId) renderReview(sessionId);
  });
  dialog.addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
}

async function renderSettings() {
  rememberReviewDrafts();
  setActive("settings");
  title.textContent = "Settings";
  const data = await api.get("/api/settings");
  const storageData = await api.get("/api/storage");
  const dataLocationData = await api.get("/api/data-location");
  const settings = data.settings;
  const storage = storageData.storage;
  const dataLocation = dataLocationData.data_location || {};
  const warningClass = storage.warning ? "storage-warning active-warning" : "storage-warning";
  const warningText = storage.warning
    ? `Storage is above the ${storage.warning_mb} MB warning threshold.`
    : `Storage is below the ${storage.warning_mb} MB warning threshold.`;
  const saveFeedback = settingsFeedback
    ? `<p class="save-feedback" id="settings-save-feedback">${escapeHtml(settingsFeedback)}</p>`
    : "";
  settingsFeedback = "";
  app.innerHTML = `
    <section class="card ${warningClass}">
      <h2>Local Storage</h2>
      <p><strong>${escapeHtml(storage.total_mb)} MB</strong> across ${escapeHtml(storage.session_count)} session${storage.session_count === 1 ? "" : "s"}.</p>
      <p class="muted">${escapeHtml(warningText)}</p>
      <p class="muted">${escapeHtml(storage.root)}</p>
      <div class="actions">
        <button class="secondary" id="cleanup-retention">Preview retention cleanup</button>
      </div>
    </section>
    ${renderSystemStatus()}
    ${renderDataLocationCard(dataLocation)}
    <form class="card form" id="settings-form">
      <h2>Settings</h2>
      ${saveFeedback}
      <label>Observation screenshot interval seconds <input name="observation_interval_seconds" type="number" min="5" value="${escapeAttr(settings.observation_interval_seconds)}"></label>
      <h2>Scheduled passive capture</h2>
      <label class="check-row"><input name="background_enabled" type="checkbox" ${settings.background_enabled ? "checked" : ""}> Enable automated capture using the weekly timetable</label>
      <h3>Weekly recording timetable</h3>
      ${settings.background_weekly_schedule == null ? `<p class="muted">Your existing daily schedule (${escapeHtml(settings.background_start_time)}–${escapeHtml(settings.background_end_time)}) stays active until you save. The grid rounds any partial half-hours outwards.</p>` : ""}
      <div id="weekly-schedule"></div>
      <label>Passive screenshot interval seconds <input name="background_interval_seconds" type="number" min="1" value="${escapeAttr(settings.background_interval_seconds)}"></label>
      <label class="check-row"><input name="background_change_detection" type="checkbox" ${settings.background_change_detection ? "checked" : ""}> Skip unchanged passive screenshots</label>
      <label>Change sensitivity threshold <input name="background_change_threshold" type="number" min="1" value="${escapeAttr(settings.background_change_threshold)}"></label>
      <h2>Manual capture hotkey</h2>
      <label class="check-row"><input name="launch_on_startup" type="checkbox" ${settings.launch_on_startup ? "checked" : ""}> Open Panoptix with Windows startup</label>
      <label class="check-row"><input name="manual_hotkey_enabled" type="checkbox" ${settings.manual_hotkey_enabled ? "checked" : ""}> Enable manual CYP capture hotkey</label>
      <label>Hotkey <input name="manual_hotkey" value="${escapeAttr(settings.manual_hotkey)}" placeholder="<ctrl>+<alt>+p"></label>
      <label>Retention days <input name="retention_days" type="number" min="1" value="${escapeAttr(settings.retention_days)}"></label>
      <label>Storage warning MB <input name="storage_warning_mb" type="number" min="1" value="${escapeAttr(settings.storage_warning_mb)}"></label>
      <div class="folder-field">
        <label>Export folder <input name="export_directory" value="${escapeAttr(settings.export_directory)}" placeholder="Leave blank for Panoptix local exports"></label>
        <button type="button" data-browse-folder="export_directory">Browse folder</button>
      </div>
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
  const timetable = PanoptixWeeklySchedule.mount(app.querySelector("#weekly-schedule"), data.timetable);
  app.querySelector("#settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.patch("/api/settings", {
      observation_interval_seconds: Number(form.get("observation_interval_seconds")),
      background_enabled: form.get("background_enabled") === "on",
      background_weekly_schedule: timetable.value(),
      background_interval_seconds: Number(form.get("background_interval_seconds")),
      background_change_detection: form.get("background_change_detection") === "on",
      background_change_threshold: Number(form.get("background_change_threshold")),
      manual_hotkey_enabled: form.get("manual_hotkey_enabled") === "on",
      manual_hotkey: form.get("manual_hotkey"),
      launch_on_startup: form.get("launch_on_startup") === "on",
      retention_days: Number(form.get("retention_days")),
      storage_warning_mb: Number(form.get("storage_warning_mb")),
      export_directory: form.get("export_directory"),
      default_evidence_purpose: form.get("default_evidence_purpose"),
      marker_shape: form.get("marker_shape"),
      marker_color: form.get("marker_color"),
      marker_size: Number(form.get("marker_size")),
      marker_stroke: Number(form.get("marker_stroke")),
    });
    settingsFeedback = "Settings saved";
    await refreshStatus();
    await renderSettings();
  });
  app.querySelector("[data-browse-folder=\"export_directory\"]").addEventListener("click", async (event) => {
    const input = app.querySelector("input[name=\"export_directory\"]");
    const picked = await browseForFolder(input.value);
    if (picked) {
      input.value = picked;
    }
  });
  app.querySelector("#browse-data-directory").addEventListener("click", async () => {
    const input = app.querySelector("#data-directory");
    const picked = await browseForFolder(input.value || dataLocation.active_path || "");
    if (picked) {
      input.value = picked;
    }
  });
  app.querySelector("#save-data-directory").addEventListener("click", async () => {
    await saveDataDirectory(app.querySelector("#data-directory").value);
  });
  app.querySelector("#reset-data-directory").addEventListener("click", async () => {
    await saveDataDirectory("");
  });
  app.querySelector("#cleanup-retention").onclick = previewRetention;
}

function renderDataLocationCard(dataLocation) {
  const feedback = dataLocationFeedback
    ? `<p class="save-feedback" id="data-location-feedback">${escapeHtml(dataLocationFeedback)}</p>`
    : "";
  dataLocationFeedback = "";
  const warning = dataLocation.warning
    ? `<p class="status-warning"><strong>Screenshot folder warning</strong>: ${escapeHtml(dataLocation.warning)}</p>`
    : "";
  const restart = dataLocation.restart_required
    ? `<p class="status-warning">Panoptix could not switch to ${escapeHtml(dataLocation.path)}. Restart to try again.</p>`
    : "";
  return `
    <section class="card">
      <h2>Screenshot storage folder</h2>
      <p class="muted">Sessions, screenshots and settings are saved here. Point this at a shared network folder to open evidence from an admin PC.</p>
      <p class="muted">In use now: ${escapeHtml(dataLocation.active_path || dataLocation.path || "")}</p>
      ${feedback}
      ${warning}
      ${restart}
      <div class="folder-field">
        <label>Screenshot folder <input id="data-directory" value="${escapeAttr(dataLocation.configured_directory || "")}" placeholder="${escapeAttr(dataLocation.default_path || "Panoptix local storage")}"></label>
        <button type="button" id="browse-data-directory">Browse folder</button>
      </div>
      <div class="actions">
        <button class="primary" type="button" id="save-data-directory">Save screenshot folder</button>
        <button type="button" id="reset-data-directory">Use default folder</button>
      </div>
      <p class="muted">Existing sessions stay in the old folder. Copy them across manually if you need them in the new location.</p>
    </section>
  `;
}

async function browseForFolder(initial) {
  const response = await api.post("/api/browse-folder", { initial: initial || "" });
  const result = response.result || {};
  if (result.error) {
    alert(result.error);
    return "";
  }
  return result.path || "";
}

async function saveDataDirectory(directory) {
  if (reviewDrafts.size && !confirm("Changing the screenshot folder discards unsaved review drafts in this tab. Continue?")) return;
  const response = await api.patch("/api/data-location", { directory });
  if (response.error) {
    alert(response.error);
    return;
  }
  const updated = response.data_location || {};
  reviewDrafts.clear();
  reviewSession = null;
  dataLocationFeedback = updated.restart_required
    ? "Screenshot folder saved. Restart Panoptix to start using it."
    : `Screenshot folder saved. New screenshots are going to ${updated.active_path} now.`;
  await refreshStatus();
  await renderSettings();
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

async function pollStatus() {
  try {
    await refreshStatus();
  } catch (error) {
    // A dropped poll must not kill the timer; the next tick retries.
    statusPill.textContent = "Cannot reach Panoptix - recording status is unknown";
    statusPill.classList.toggle("active", false);
    console.warn("Status poll failed", error);
  }
}

setInterval(pollStatus, 5000);

// Browsers throttle background timers to about once a minute, so the count goes
// stale while staff are working in another window. Catch up on the way back in.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    pollStatus();
  }
});
window.addEventListener("focus", pollStatus);
window.addEventListener("pageshow", pollStatus);

render(currentView).then(bindBannerStop);
