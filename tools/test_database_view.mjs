import assert from "node:assert/strict";
import * as core from "../skills/business-observer/assets/stategraph-viewer/graph-core.js";
import * as layout from "../skills/business-observer/assets/stategraph-viewer/layout.js";
import * as analysis from "../skills/business-observer/assets/stategraph-viewer/analysis.js";
import {
  dataLines,
  dataRoles,
  dataRelations,
  databaseWarning,
  dataStatusClass,
  dataRelationEvidence,
  observedDataTransfer,
} from "../skills/business-observer/assets/stategraph-viewer/data-layer.js";
import { glyphShapes } from "../skills/business-observer/assets/stategraph-viewer/glyphs.js";
import { transferEdges } from "../skills/business-observer/assets/stategraph-viewer/recording.js";
import {
  boStepDetail,
  boStepPlan,
  boTransferLabel,
} from "../skills/business-observer/assets/stategraph-viewer/replay-steps.js";
import { setLocale } from "../skills/business-observer/assets/stategraph-viewer/i18n.js";

// Two storage families, a concrete query, application processing, and a write
// share one ordinary graph. All runtime assertions use existing probe events.
const nodes = [
  { id: "business", kind: "action", layer: "business", label: "Publish selection" },
  {
    id: "db",
    kind: "data",
    data_role: "store",
    data_store: "gallery",
    label: "Gallery",
    data_origin: "database",
    data_coverage: "complete",
    data_metadata: { engine: "sqlite" },
  },
  {
    id: "pictures",
    parent: "db",
    kind: "data",
    data_role: "dataset",
    data_store: "gallery",
    data_key: "pictures",
    label: "Pictures",
    data_metadata: { kind: "table", status: "matched" },
  },
  {
    id: "id",
    parent: "pictures",
    kind: "data",
    data_role: "column",
    label: "id",
    data_metadata: { native_type: "INTEGER", primary_key: true, nullable: false },
  },
  {
    id: "feed",
    kind: "data",
    data_role: "dataset",
    data_store: "documents",
    data_key: "feed",
    label: "Published feed",
    data_origin: "declaration",
    data_coverage: "partial",
    data_metadata: { kind: "collection", status: "declared_only" },
  },
  {
    id: "load",
    parent: "business",
    kind: "function",
    data_role: "query",
    data_store: "gallery",
    label: "Load pictures",
    source: { symbol: "load_pictures" },
  },
  {
    id: "filter",
    parent: "business",
    kind: "function",
    data_role: "transform",
    label: "Select approved pictures",
  },
  {
    id: "save",
    parent: "business",
    kind: "function",
    data_role: "query",
    data_store: "documents",
    label: "Save feed",
  },
];
for (const [status, label] of [
  ["application_declared", "Application model declaration"],
  ["unverified", "Database structure unverified"],
  ["outside_scope", "Reference outside inspected scope"],
])
  assert.ok(
    dataLines({ data_role: "column", data_metadata: { status } }).some(
      (row) => row.text === label && row.role === "muted",
    ),
  );
assert.equal(databaseWarning({ valid: true }), null);
assert.equal(databaseWarning(undefined), null);
for (const [source, description] of [
  ["provided", "Targets supplied by application"],
  ["parsed_sql", "Targets from SQL"],
  ["driver", "Targets reported by driver"],
])
  assert.ok(
    dataLines({ data_role: "query" }, {}, { target_source: source }, true).some(
      (row) => row.text === description,
    ),
  );
assert.match(
  databaseWarning({ valid: false, errors: ["Metadata unavailable"] }).details,
  /Metadata unavailable/,
);
const edge = (id, from, to, relation) => ({
  id,
  from,
  to,
  type: "data",
  data_relation: relation,
  label: relation,
});
const edges = [
  edge("read", "pictures", "load", "reads"),
  edge("write", "save", "feed", "writes"),
  edge("process", "load", "filter", "transforms"),
  edge("save-input", "filter", "save", "transforms"),
  edge("reference", "id", "feed", "references"),
];
assert.equal(dataRelationEvidence({ ...edges[4], data_origin: "database" }), "Database metadata");
assert.equal(
  dataRelationEvidence({ ...edges[4], data_origin: "declaration" }),
  "Model declaration",
);
assert.equal(
  dataRelationEvidence({
    ...edges[4],
    data_origin: "database",
    data_constraints: [{ origin: "declaration" }],
  }),
  "Database metadata and model",
  "merged constraints preserve actual and declared provenance",
);
assert.equal(
  dataRelationEvidence({
    type: "maps",
    members: [{ data_origin: "database" }, { data_origin: "declaration" }],
  }),
  "Database metadata and model",
  "folded constraint edges preserve both origins",
);
assert.equal(dataRelationEvidence({ type: "reads", data_origin: "declaration" }), null);
const event = {
  id: "query",
  kind: "probe",
  node: "load",
  phase: "return",
  seq: 1,
  attempt: "run",
  run_id: "r1",
  call_id: "c1",
  entity: "gallery",
  build_id: "v1",
  model_revision: "1",
  basis: { param_version: 1 },
  inputs: {
    operation: "read",
    statement: "SELECT id FROM pictures WHERE approved = ?",
    parameters: { approved: true },
  },
  outputs: {
    status: "executed",
    duration_ms: 2,
    rows: 12,
    rows_known: true,
    targets: ["pictures"],
  },
  depends: [],
};
const transformed = {
  ...event,
  id: "transformed",
  node: "filter",
  call_id: "c2",
  seq: 2,
  inputs: {},
  outputs: {
    status: "executed",
    input_count: 12,
    output_count: 7,
    before: { total: 12 },
    result: { total: 7 },
  },
  depends: [{ event: "query", type: "data" }],
};
const written = {
  ...event,
  id: "written",
  node: "save",
  call_id: "c3",
  seq: 3,
  inputs: { operation: "write" },
  outputs: {
    status: "rolled_back",
    rows: 7,
    rows_known: true,
    targets: ["feed"],
    committed: false,
  },
  phase: "change",
  depends: [{ event: "transformed", type: "data" }],
};
const view = {
  model: { nodes, edges, machine: { values: [], transitions: [] } },
  machine: { configurations: [], journal: [] },
  manifest: { bindings: {} },
  authority: { parameters: { attempt: "run" }, basis: { param_version: 1 } },
  binding_status: { status: "current" },
  events: [event, transformed, written],
};
{
  const all = new Map([
    ["query", { id: "query", data_store: "gallery", data_role: "query" }],
    [
      "source",
      { id: "source", data_store: "gallery", data_role: "dataset", data_key: "table:pictures" },
    ],
    [
      "destination",
      {
        id: "destination",
        data_store: "gallery",
        data_role: "dataset",
        data_key: "table:exhibition",
      },
    ],
  ]);
  const mixed = {
    node: "query",
    phase: "return",
    outputs: {
      targets: ["table:pictures", "table:exhibition"],
      target_access: [
        { target: "table:pictures", action: "read" },
        { target: "table:exhibition", action: "write" },
      ],
    },
  };
  assert.equal(
    observedDataTransfer({ from: "source", to: "query", data_relation: "reads" }, mixed, all),
    true,
  );
  assert.equal(
    observedDataTransfer({ from: "query", to: "destination", data_relation: "writes" }, mixed, all),
    true,
  );
  assert.equal(
    observedDataTransfer({ from: "query", to: "source", data_relation: "writes" }, mixed, all),
    false,
    "a read source must not animate as a write",
  );
  assert.equal(
    observedDataTransfer({ from: "destination", to: "query", data_relation: "reads" }, mixed, all),
    false,
    "a write destination must not animate as a read",
  );
  all.get("source").data_key = "table:public.pictures";
  assert.equal(
    observedDataTransfer({ from: "source", to: "query", data_relation: "reads" }, mixed, all),
    true,
    "an unqualified table resolves only within its store",
  );
  all.set("ambiguous", {
    id: "ambiguous",
    data_store: "gallery",
    data_role: "dataset",
    data_key: "table:archive.pictures",
  });
  assert.equal(
    observedDataTransfer({ from: "source", to: "query", data_relation: "reads" }, mixed, all),
    false,
    "ambiguous schemas must not produce a guessed transfer",
  );
}
function project(id, expanded = []) {
  const profile = analysis.profileFor(id);
  const graph = core.layoutGraph(
    view,
    new Set(expanded),
    new Set(),
    new Map(),
    "latest",
    "latest",
    {
      match: (all, events, status, relations) =>
        analysis.matchingNodes(all, view, events, profile, status, relations),
    },
  );
  layout.refreshHierarchy(graph);
  return { graph, shown: layout.presentationGraph(graph, profile) };
}
for (const role of dataRoles) {
  assert.ok(layout.emptyFilters().nodes.includes(role));
  assert.ok(core.nodeTypes[role]);
  assert.ok(glyphShapes(role).length, "renderer and legend share geometry");
}
for (const relation of dataRelations) {
  assert.ok(layout.emptyFilters().edges.includes(relation));
  assert.ok(layout.relationStyles[relation]);
  assert.equal(core.relationType({ type: relation }), relation);
}
const migrated = layout.cleanFilters({
  nodes: ["function", "data"],
  edges: ["data"],
  regions: ["data"],
});
assert.ok(migrated.nodes.includes("query") && migrated.nodes.includes("store"));
assert.ok(migrated.edges.includes("reads"));
migrated.nodes = migrated.nodes.filter((type) => type !== "query");
migrated.edges = migrated.edges.filter((type) => type !== "reads");
const saved = layout.cleanFilters(JSON.parse(JSON.stringify(migrated)));
assert.ok(
  !saved.nodes.includes("query") && !saved.edges.includes("reads"),
  "explicit exclusions survive later reloads",
);
assert.equal(
  layout.filterNode(nodes[5], new Map(nodes.map((n) => [n.id, n])), saved),
  false,
  "generic Function cannot bypass a query exclusion",
);
const structure = project("database", ["db", "pictures"]);
assert.ok(structure.shown.regions.has("db"));
assert.ok(structure.shown.glyphs.has("id"));
assert.ok(!structure.graph.byId.has("load"), "structure view does not add unrelated operations");
assert.ok(structure.shown.edges.some((e) => e.type === "references"));
const operations = project("data-operations");
assert.ok(
  operations.graph.byId.get("pictures").node.filter_context,
  "actual storage endpoint remains a labelled boundary",
);
assert.ok(
  operations.shown.edges.some(
    (e) => e.type === "reads" && e.from === "pictures" && e.to === "load",
  ),
);
assert.ok(operations.shown.edges.some((e) => e.type === "writes" && e.to === "feed"));
assert.ok(operations.shown.edges.some((e) => e.type === "transforms"));
assert.ok(operations.graph.edges.find((e) => e.id === "read").observed);
const queryLines = core.lines(
  nodes.find((n) => n.id === "load"),
  view,
  view.events,
  "latest",
);
assert.match(queryLines[0].text, /Executed.*2 ms.*12 rows/);
assert.ok(queryLines.some((row) => row.text.includes("SELECT id")));
const transformLines = core.lines(
  nodes.find((n) => n.id === "filter"),
  view,
  view.events,
  "latest",
);
assert.ok(transformLines.some((row) => row.text.includes("12 → 7")));
assert.ok(transformLines.some((row) => row.text.includes('"total":7')));
assert.equal(
  core.lines(
    nodes.find((n) => n.id === "save"),
    view,
    view.events,
    "latest",
  )[0].role,
  "bad",
);
assert.equal(
  core.status(
    nodes.find((n) => n.id === "save"),
    view,
    view.events,
    "latest",
  ),
  "blocked",
);
assert.ok(
  dataLines(nodes[3]).some(
    (row) => row.text.includes("Primary key") && row.text.includes("Required"),
  ),
);
assert.ok(dataLines(nodes[4]).some((row) => row.text.includes("Awaiting database")));
const unknown = dataLines(nodes[5], {}, { status: "executed", rows_known: false, rows: -1 }, true);
assert.match(unknown[0].text, /Row count unknown/);
assert.doesNotMatch(unknown[0].text, /-1 rows/);
for (const [status, label, style] of [
  ["started", "Started", null],
  ["returned", "Returned result", null],
  ["transformed", "Processed", null],
  ["ended_before_exit", "Transaction ended; outcome unverified", "historical"],
  ["partial_failure", "Some writes failed", "blocked"],
  ["acknowledgement_failed", "Write acknowledgement failed", "blocked"],
  ["rollback_failed", "Rollback failed; outcome unverified", "blocked"],
]) {
  const row = dataLines(nodes[5], {}, { status }, true)[0];
  assert.equal(row.text, label);
  assert.equal(dataStatusClass(status), style);
  if (style)
    assert.equal(core.status(nodes[5], view, [{ ...event, outputs: { status } }], "latest"), style);
  if (status === "ended_before_exit") {
    assert.equal(row.role, "muted");
    assert.doesNotMatch(row.text, /[Cc]ommitt/);
  }
}
const transfers = transferEdges(event, view.events, operations.shown.edges, operations.graph.all);
assert.ok(
  transfers.some((id) => operations.shown.edges.find((e) => e.id === id)?.type === "reads"),
);
assert.equal(
  transferEdges(
    { ...event, outputs: { targets: ["different_table"] } },
    view.events,
    operations.shown.edges,
    operations.graph.all,
  ).length,
  0,
  "unknown targets cannot animate a declared relation",
);
assert.ok(
  transferEdges(transformed, view.events, operations.shown.edges, operations.graph.all).some(
    (id) => operations.shown.edges.find((e) => e.id === id)?.type === "transforms",
  ),
);
assert.match(
  boTransferLabel(
    operations.shown.edges.find((e) => e.type === "writes"),
    written,
  ),
  /Rolled back/,
);
const recording = { context: { ...view, events: [] }, final: view },
  items = [{ kind: "start" }, event, transformed, written, { kind: "end" }];
const detail = boStepDetail(recording, items, 2, 1, operations.graph.all, operations.graph.boxes);
assert.ok(detail.rows.some((row) => row.field === "result" && row.after.total === 7));
assert.ok(boStepPlan(recording, items, operations.graph.all, operations.graph.boxes).includes(2));
const full = core.layoutGraph(view);
layout.refreshHierarchy(full);
const coverage = layout.elementCoverage(
  full,
  layout.presentationGraph(full, layout.emptyFilters()),
);
assert.equal(coverage.excludedNodes, 0);
assert.equal(coverage.excludedEdges, 0, "All elements accounts for relations inside folded groups");
setLocale("zh-CN");
assert.match(dataLines(nodes[5], event.inputs, event.outputs, true)[0].text, /已执行.*12 条/);
assert.match(dataLines(nodes[3])[0].text, /主键.*必填/);
for (const status of [
  "started",
  "returned",
  "transformed",
  "ended_before_exit",
  "partial_failure",
  "acknowledgement_failed",
  "rollback_failed",
])
  assert.match(dataLines(nodes[5], {}, { status }, true)[0].text, /[\u4e00-\u9fff]/);
assert.equal(dataRelationEvidence({ ...edges[4], data_origin: "database" }), "数据库元数据");
setLocale("en");
console.log(
  "PASS: database roles, typed edges, structure and operation presets, true boundaries, inline facts, exact target evidence, rollback, replay, folded completeness and Chinese presentation.",
);
