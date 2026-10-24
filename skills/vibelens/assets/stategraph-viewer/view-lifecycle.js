// Stable project preferences and build-specific recordings have different lifetimes.
import { layoutKey } from "./layout.js";

export function projectLayoutKey(view, storage) {
  const model = view.model;
  const base = layoutKey(model, storage.projectId || view.layout_id);
  const legacy =
    "business-observer.layout.v2:" +
    (view.layout_id ||
      model.presentation?.layout_id ||
      model.presentation?.subject ||
      model.intent);
  for (const old of [
    legacy,
    ...(model.presentation?.layout_aliases || []).map((id) => "business-observer.layout.v2:" + id),
  ])
    storage.migrateLayout?.(old, base);
  return base;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    );
  return value;
}

/** Runtime values, clocks and process restarts do not create a new graph version. */
export function graphVersion(view) {
  return JSON.stringify([
    view.manifest.build_id,
    view.manifest.model_hash || canonical(view.model),
  ]);
}

export function recordingMatches(saved, view) {
  return !!saved?.context && graphVersion(saved.context) === graphVersion(view);
}

/** Distinguish lost capture from normal expiry of the bounded live history. */
export function connectionStatus(view, translate) {
  const health = view.health || {};
  const missing = ["errors", "dropped", "parse_errors", "truncated"].reduce(
    (total, key) => total + (health[key] || 0),
    0,
  );
  const status = missing
    ? translate("Missing ") + missing + translate(" records")
    : translate(view.historical ? "Saved run" : "Connected");
  return !view.historical && health.evicted_events
    ? status + " · " + translate("{0} earlier events expired", health.evicted_events)
    : status;
}
