import assert from "node:assert/strict";
import * as layout from "../skills/vibelens/assets/stategraph-viewer/layout.js";
import { layoutGraph } from "../skills/vibelens/assets/stategraph-viewer/graph-core.js";
import { projectStorage } from "../skills/vibelens/assets/stategraph-viewer/preferences.js";
import {
  projectLayoutKey,
  graphVersion,
  recordingMatches,
} from "../skills/vibelens/assets/stategraph-viewer/view-lifecycle.js";

// A code iteration adds a feature while an unrelated advanced call crosses two
// collapsed groups. Root hints deliberately omit the new feature and states.
const view = {
  model: {
    project_id: "stable-project",
    presentation: { subject: "First title" },
    nodes: [
      { id: "a", kind: "action", layer: "business", label: "Upload" },
      { id: "b", kind: "action", layer: "business", label: "Review" },
      { id: "f", kind: "function", parent: "a", origin: "source-ast", label: "Store" },
      { id: "g", kind: "function", parent: "b", analysis_level: "advanced", label: "Notify" },
      { id: "new", kind: "function", label: "Login" },
    ],
    edges: [
      { id: "fg", from: "f", to: "g", type: "flow", origin: "source-ast" },
      { id: "fg2", from: "f", to: "g", type: "flow", origin: "source-ast" },
      { id: "af", from: "a", to: "f", type: "contains" },
      { id: "internal", from: "a", to: "f", type: "data" },
    ],
    machine: {
      values: ["ready", "done"],
      transitions: [{ trigger: "finish", source: "ready", dest: "done" }],
    },
    graph_roots: ["a", "b"],
  },
  machine: { configurations: [], journal: [] },
  manifest: { build_id: "v1", bindings: {} },
  authority: { basis: {}, parameters: {} },
  binding_status: { status: "current" },
  events: [],
  health: { run_id: "r1" },
};
function graphFor(state, input = view) {
  const graph = layoutGraph(
    input,
    new Set(state.expanded),
    new Set(),
    new Map(),
    "latest",
    "latest",
    {
      hiddenNodes: state.filters.hiddenNodes,
      hiddenEdges: state.filters.hiddenEdges,
    },
  );
  layout.placeIncremental(graph, state);
  return { graph, shown: layout.presentationGraph(graph, state.filters) };
}
const state = layout.emptyLayout();
let { graph, shown } = graphFor(state);
assert.ok(graph.byId.has("new"), "root hints cannot hide later implemented features");
assert.ok(graph.byId.has("state.ready"), "generated state roots are accounted for");
assert.ok(
  shown.edges.some((e) => e.from === "a" && e.to === "b" && e.members.length === 2),
  "static relations survive collapse, grouped with real source IDs",
);
let count = layout.elementCoverage(graph, shown);
assert.equal(count.excludedNodes, 0);
assert.equal(count.excludedEdges, 0);
assert.equal(count.foldedNodes, 2);
assert.equal(count.foldedEdges, 2);
state.expanded = ["a", "b"];
({ graph, shown } = graphFor(state));
assert.equal(layout.elementCoverage(graph, shown).foldedNodes, 0);
layout.setPosition(graph, state, "a", 450, 320);
const positions = structuredClone(state.positions);
state.camera = { x: 10, y: 20, scale: 0.8 };
state.annotations.a = { label: "My upload", note: "Keep this", core: true };
state.filters.hiddenEdges = ["fg"];
state.filters.hiddenNodes = ["new"];
state.filters.edges = state.filters.edges.filter((x) => x !== "transition");
const store = new Map();
const memory = { getItem: (k) => store.get(k) || null, setItem: (k, v) => store.set(k, v) };
layout.writeLayout(memory, "saved", state);
const restored = layout.readLayout(memory, "saved").state;
const changed = structuredClone(view);
changed.manifest.build_id = "v2";
changed.model.presentation.subject = "New title";
changed.model.nodes.push({ id: "added", parent: "a", kind: "function", label: "Validate" });
({ graph, shown } = graphFor(restored, changed));
for (const [id, p] of Object.entries(positions)) assert.deepEqual(restored.positions[id], p);
assert.deepEqual(restored.camera, state.camera);
assert.deepEqual(restored.expanded, ["a", "b"]);
assert.deepEqual(restored.annotations.a, state.annotations.a);
assert.ok(!shown.glyphs.has("new"));
assert.ok(!shown.edges.some((e) => e.members.some((m) => m.id === "fg")));
assert.ok(
  shown.edges.some((e) => e.members.some((m) => m.id === "fg2")),
  "hiding one member keeps its parallel relation",
);
assert.ok(!shown.edges.some((e) => e.type === "transition"));
assert.ok(shown.glyphs.has("added"));
const moved = restored.positions.added;
assert.ok(Math.hypot(moved.x - restored.positions.a.x, moved.y - restored.positions.a.y) < 1000);
restored.filters.hiddenNodes = ["a"];
({ graph, shown } = graphFor(restored, changed));
assert.ok(!graph.byId.has("f") && !graph.byId.has("added"), "hiding a group hides its branch");
assert.ok(!shown.edges.some((e) => e.members.some((m) => m.from === "f")));
restored.filters = layout.emptyFilters();
({ graph, shown } = graphFor(restored, changed));
count = layout.elementCoverage(graph, shown);
assert.equal(count.excludedNodes, 0);
assert.equal(count.excludedEdges, 0);
assert.deepEqual(
  restored.positions.a,
  positions.a,
  "all elements does not rearrange existing nodes",
);
restored.filters.hiddenNodes = ["f"];
restored.filters.hiddenEdges = ["fg"];
layout.migrateNodeIds(restored, { f: "renamed" }, { fg: "renamed-edge" });
assert.deepEqual(restored.positions.renamed, positions.f);
assert.deepEqual(restored.filters.hiddenNodes, ["renamed"]);
assert.deepEqual(restored.filters.hiddenEdges, ["renamed-edge"]);

// Stable project identity carries every custom view, including dormant IDs,
// through subject/layout changes and a fresh browser storage instance.
const old = "business-observer.layout.v2:Old title",
  base = "business-observer.layout.v2:stable-project";
let document = {
  schema: 1,
  revision: 3,
  project_id: "stable-project",
  entries: {
    [old]: JSON.stringify(state),
    [old + ":view:custom-1"]: JSON.stringify(restored),
    [old + ":analysis"]: JSON.stringify({
      selected: "custom-1",
      custom: [{ id: "custom-1", label: "My view" }],
    }),
  },
};
const api = async (_, o) =>
  o?.method === "POST"
    ? {
        ok: true,
        json: async () => (document = { ...JSON.parse(o.body), revision: document.revision + 1 }),
      }
    : { ok: true, json: async () => structuredClone(document) };
const serverStorage = await projectStorage(null, () => {}, api);
changed.model.presentation.layout_aliases = ["Old title"];
assert.equal(projectLayoutKey(changed, serverStorage), base);
await serverStorage.flush();
const reload = await projectStorage(null, () => {}, api);
assert.deepEqual(
  JSON.parse(reload.getItem(base + ":view:custom-1")),
  JSON.parse(JSON.stringify(restored)),
);
assert.equal(JSON.parse(reload.getItem(base + ":analysis")).selected, "custom-1");
reload.setItem(base, JSON.stringify({ schema: 2, focus: "new" }));
projectLayoutKey(changed, reload);
assert.equal(
  JSON.parse(reload.getItem(base)).focus,
  "new",
  "migration cannot overwrite a newer view",
);
await reload.flush();
const saved = { context: structuredClone(view) };
assert.ok(recordingMatches(saved, view));
assert.ok(!recordingMatches(saved, changed));
const runtime = structuredClone(view);
runtime.health.run_id = "r2";
runtime.authority.basis.clock = 999;
assert.equal(
  graphVersion(runtime),
  graphVersion(view),
  "restart and time do not invalidate same-build recordings",
);
runtime.model.nodes.push({ id: "extra", kind: "function" });
assert.ok(!recordingMatches(saved, runtime), "a graph-only update also invalidates replay");
console.log(
  "PASS: per-element filters, ID migration, persistent custom views, stable positions, complete folded graph and recording version boundary.",
);
