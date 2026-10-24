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
export function createConversationFocus({
  onFocus,
  onClear,
  onLocale = () => {},
  readState = () => null,
  writeState = () => {},
  hasSavedView = () => false,
}) {
  let revision = "",
    ids = [],
    active = false,
    lastPoll = 0;
  function reset() {
    revision = "";
    ids = [];
    active = false;
    onClear();
  }
  return {
    get ids() {
      return active ? ids : [];
    },
    // Dismiss only this confirmed scope; a new conversation revision may focus again.
    clear() {
      if (!active) return;
      active = false;
      writeState({ revision, active });
      onClear();
    },
    async refresh() {
      if (Date.now() - lastPoll < 2000) return;
      lastPoll = Date.now();
      try {
        const response = await fetch("/api/design", { cache: "no-store" });
        if (response.status === 404) return reset();
        if (!response.ok) throw Error("Cannot load conversation focus");
        const value = await response.json();
        await onLocale(value.locale);
        if (!value.available) {
          // Remember an initially empty scope. A later confirmed scope is new,
          // even when the developer already saved a layout in this session.
          if (!readState()) writeState({ revision: "", active: false });
          reset();
          return;
        }
        if (revision === value.revision + String(value.stale)) return;
        revision = value.revision + String(value.stale);
        ids = value.stale ? [] : value.nodes;
        const saved = readState();
        // Reload restores highlights without reframing the developer's saved view.
        // Older preferences have no discussion state; preserve their existing view too.
        const restore = saved?.revision === revision || (!saved && hasSavedView());
        active = ids.length > 0 && (!restore || saved?.active === true);
        writeState({ revision, active });
        if (active && !restore) onFocus(ids);
        else onClear();
      } catch {
        // Conversation metadata is not application state. A failed/stale scope
        // must not keep highlighting unrelated nodes or add a status banner.
        reset();
      }
    },
  };
}
