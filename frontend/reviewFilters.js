(function initReviewFilters(globalScope) {
  function normalize(value) {
    return String(value || "").toLowerCase().trim();
  }

  function eventSearchText(event) {
    const tags = Array.isArray(event.tags) ? event.tags.join(" ") : "";
    return normalize([
      event.title,
      event.staff_note,
      event.cyp_quote,
      tags,
      event.type,
      event.timestamp,
    ].join(" "));
  }

  function matchesFilter(event, filter) {
    if (filter === "highlights") {
      return Boolean(event.highlight);
    }
    if (filter === "selected") {
      return event.selected_for_export !== false;
    }
    if (filter === "unselected") {
      return event.selected_for_export === false;
    }
    if (filter === "redacted") {
      return Array.isArray(event.redactions) && event.redactions.length > 0;
    }
    if (filter === "clicks") {
      return event.type === "click";
    }
    if (filter === "observations") {
      return event.type === "periodic";
    }
    return true;
  }

  function matchesSearch(event, query) {
    const terms = normalize(query).split(/\s+/).filter(Boolean);
    if (!terms.length) {
      return true;
    }
    const haystack = eventSearchText(event);
    return terms.every((term) => haystack.includes(term));
  }

  function filterReviewEvents(events, filter, query) {
    return (events || []).filter((event) => matchesFilter(event, filter) && matchesSearch(event, query));
  }

  const api = { filterReviewEvents };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  globalScope.PanoptixReviewFilters = api;
}(typeof globalThis !== "undefined" ? globalThis : window));
