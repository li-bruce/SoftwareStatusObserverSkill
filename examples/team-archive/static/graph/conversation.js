import { t as boTranslate } from "./i18n.js";
// Read-only conversation focus. Answers and changes stay in the coding assistant.
import { selectionContext } from "./layout.js";
export function discussionContext(graph, ids) {
  const result = { active: ids.length > 0, nodes: new Set(), edges: new Set(), regions: new Set() };
  for (const id of ids) {
    const context = selectionContext(graph, id);
    for (const key of ["nodes", "edges", "regions"])
      for (const value of context[key]) result[key].add(value);
  }
  return result;
}
export function createConversationFocus({ onFocus, onClear }) {
  const button = document.getElementById("discussion-focus"),
    clear = document.getElementById("discussion-clear");
  const label = document.getElementById("discussion-label");
  let revision = "",
    ids = [],
    active = false,
    lastPoll = 0;
  button.onclick = () => {
    active = true;
    onFocus(ids);
    clear.hidden = false;
  };
  clear.onclick = () => {
    active = false;
    onClear();
    clear.hidden = true;
  };
  return {
    get ids() {
      return active ? ids : [];
    },
    async refresh() {
      if (Date.now() - lastPoll < 2000) return;
      lastPoll = Date.now();
      try {
        const response = await fetch("/api/design", { cache: "no-store" });
        if (response.status === 404) return;
        if (!response.ok) throw Error(boTranslate("Cannot load the current discussion scope"));
        const value = await response.json();
        if (!value.available) {
          button.hidden = true;
          clear.hidden = true;
          return;
        }
        if (revision === value.revision + String(value.stale)) return;
        revision = value.revision + String(value.stale);
        ids = value.stale ? [] : value.nodes;
        button.hidden = !ids.length;
        label.textContent = value.stale
          ? boTranslate("Discussion scope needs updating")
          : value.label || "";
        active = ids.length > 0;
        clear.hidden = !active;
        if (active) onFocus(ids);
        else onClear();
      } catch (error) {
        label.textContent = error.message;
      }
    },
  };
}
