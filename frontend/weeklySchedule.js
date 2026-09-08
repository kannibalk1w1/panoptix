(function (globalScope) {
  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const time = (slot) => `${String(Math.floor(slot / 2)).padStart(2, "0")}:${slot % 2 ? "30" : "00"}`;

  function mount(container, initial) {
    let schedule = initial.map((day) => [...day]);
    let drag = null;
    container.innerHTML = `
      <p id="timetable-help" class="muted">Click a half-hour block to switch it on or off. Drag a rectangle across times and days to change several blocks. Times follow this computer's local clock.</p>
      <div class="actions timetable-actions">
        <button type="button" class="secondary" data-schedule-action="weekdays">Weekdays 09:00–15:30</button>
        <button type="button" class="secondary" data-schedule-action="copy">Copy Monday to all days</button>
        <button type="button" class="secondary" data-schedule-action="clear">Clear all</button>
      </div>
      <p class="schedule-legend"><span class="schedule-swatch on"></span> Record <span class="schedule-swatch"></span> Don't record</p>
      <div class="timetable-scroll" tabindex="0" aria-label="Scrollable weekly timetable">
        <table class="weekly-timetable" aria-describedby="timetable-help"><caption class="visually-hidden">Weekly recording timetable, half-hour slots</caption>
          <thead><tr><th scope="col">Time</th>${days.map((day) => `<th scope="col"><abbr title="${day}">${day.slice(0, 3)}</abbr></th>`).join("")}</tr></thead>
          <tbody>${Array.from({length: 48}, (_, slot) => `<tr><th scope="row">${time(slot)}</th>${days.map((day, index) => `<td><button type="button" data-day="${index}" data-slot="${slot}" aria-label="${day} ${time(slot)} to ${time(slot + 1)}" title="${day} ${time(slot)}–${time(slot + 1)}"></button></td>`).join("")}</tr>`).join("")}</tbody>
        </table>
      </div>
      <p class="muted" id="timetable-summary" role="status"></p>`;
    const cells = [...container.querySelectorAll("[data-slot]")];
    const table = container.querySelector("table");
    const refresh = () => {
      cells.forEach((cell) => {
        const active = schedule[Number(cell.dataset.day)][Number(cell.dataset.slot)];
        cell.setAttribute("aria-pressed", String(active));
        cell.textContent = active ? "●" : "";
      });
      const hours = schedule.flat().filter(Boolean).length / 2;
      container.querySelector("#timetable-summary").textContent = hours ? `${hours} hours scheduled per week. Save settings to apply changes.` : "No capture blocks selected. Automated capture will stay off until you select blocks and save.";
    };
    const cellAt = (event) => {
      const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-slot]");
      return cell && table.contains(cell) ? cell : null;
    };
    const paint = (cell) => {
      const day = Number(cell.dataset.day), slot = Number(cell.dataset.slot);
      schedule = drag.original.map((row) => [...row]);
      for (let d = Math.min(day, drag.day); d <= Math.max(day, drag.day); d++) {
        for (let s = Math.min(slot, drag.slot); s <= Math.max(slot, drag.slot); s++) schedule[d][s] = drag.value;
      }
      refresh();
    };
    table.onpointerdown = (event) => {
      const cell = cellAt(event);
      if (!cell || event.button !== 0) return;
      event.preventDefault();
      cell.focus({preventScroll: true});
      const day = Number(cell.dataset.day), slot = Number(cell.dataset.slot);
      drag = {day, slot, value: !schedule[day][slot], original: schedule.map((row) => [...row])};
      table.setPointerCapture(event.pointerId);
      paint(cell);
    };
    table.onpointermove = (event) => { const cell = cellAt(event); if (drag && cell) paint(cell); };
    table.onpointerup = (event) => {
      const cell = cellAt(event);
      if (drag && cell) paint(cell);
      drag = null;
      if (table.hasPointerCapture(event.pointerId)) table.releasePointerCapture(event.pointerId);
    };
    table.onpointercancel = () => { if (drag) { schedule = drag.original; drag = null; refresh(); } };
    table.onclick = (event) => {
      const cell = event.target.closest("[data-slot]");
      if (cell && event.detail === 0) { // Native Space/Enter activation.
        const day = Number(cell.dataset.day), slot = Number(cell.dataset.slot);
        schedule[day][slot] = !schedule[day][slot];
        refresh();
      }
    };
    container.querySelectorAll("[data-schedule-action]").forEach((button) => {
      button.onclick = () => {
        if (button.dataset.scheduleAction === "copy") schedule = days.map(() => [...schedule[0]]);
        else schedule = days.map((_, day) => Array.from({length: 48}, (_, slot) => button.dataset.scheduleAction === "weekdays" && day < 5 && slot >= 18 && slot < 31));
        refresh();
      };
    });
    refresh();
    const first = schedule[0].findIndex(Boolean);
    if (first > 1) container.querySelector(".timetable-scroll").scrollTop = (first - 1) * 28;
    return {value: () => schedule.map((day) => [...day])};
  }
  globalScope.PanoptixWeeklySchedule = {mount};
}(globalThis));
