import { t as boTranslate } from "./i18n.js";
// Event-bound authoritative projections. No business commands or clock inference.
const copy = (value) => structuredClone(value);
/** Find the exact recorded state snapshot associated with this event. */
export function runtimeFrame(recording, event) {
  if (recording.runtime_frames?.schema !== "stategraph-runtime-frames/v1" || !event) return null;
  return (
    recording.runtime_frames.frames.find(
      (f) =>
        f.event_id === event.id &&
        f.run_id === event.run_id &&
        f.build_id === recording.build_id &&
        Number.isInteger(event.revision) &&
        f.revision === event.revision &&
        f.machine.state_revision === event.revision,
    ) || null
  );
}
export function applyRuntimeFrame(recording, event, view) {
  if (!recording.runtime_frames) return false;
  const exact = runtimeFrame(recording, event);
  view.replay.runtime_exact = Boolean(exact);
  if (exact) {
    view.machine = copy(exact.machine);
    view.authority = copy(exact.authority);
  } else {
    view.machine = {
      current: null,
      configurations: [],
      journal: [],
      runtime_gap: boTranslate("No runtime snapshot recorded for this step"),
    };
    view.authority.state = null;
    if (!recording.runtime_frames.partial || Number.isInteger(event?.revision))
      view.replay.gaps = [
        ...(view.replay.gaps || []),
        boTranslate("No runtime snapshot recorded for this step; state has not been inferred."),
      ];
  }
  return true;
}
/** Compare available snapshots and emit state/resource changes for the replay display. */
export function runtimeChanges(before, after, owner, put) {
  const previous = new Map((before.configurations || []).map((c) => [c.attempt, c]));
  for (const cfg of after.configurations || []) {
    const old = previous.get(cfg.attempt) || {};
    put(owner, boTranslate("Flow"), old.phase, cfg.phase, "business", null, cfg.attempt);
    for (const [node, value] of Object.entries(cfg.activities || {}))
      put(node, boTranslate("Activity"), old.activities?.[node], value, "state", null, cfg.attempt);
  }
  // Global resources have a single node identity, never one copy per attempt.
  for (const node of new Set([
    ...Object.keys(before.shared_resources || {}),
    ...Object.keys(after.shared_resources || {}),
  ])) {
    const old = before.shared_resources?.[node],
      next = after.shared_resources?.[node];
    for (const field of new Set([...Object.keys(old || {}), ...Object.keys(next || {})]))
      put(node, field, old?.[field], next?.[field], "resource", null, null);
  }
}
