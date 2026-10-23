import assert from "node:assert/strict";
import { CodeLayer, withCodeGraph, codeTypes, codeRelations, codeSummary } from "../skills/business-observer/assets/stategraph-viewer/code-layer.js";
import { profileFor } from "../skills/business-observer/assets/stategraph-viewer/analysis.js";
import { nodeType, relationType, status } from "../skills/business-observer/assets/stategraph-viewer/graph-core.js";
import { emptyFilters, cleanFilters, relationStyles } from "../skills/business-observer/assets/stategraph-viewer/layout.js";
import { meanings, glyphShapes } from "../skills/business-observer/assets/stategraph-viewer/glyphs.js";

const view = { model: { nodes: [{id: "business"}], edges: [], graph_roots: ["business"] }, manifest: { build_id: "original", bindings: {} } };
const slice = { schema: "bo-code-graph/v1", revision: "source-1", nodes: [{id: "file", code_role: "file"}, {id: "fn", parent: "file", code_role: "function"}], edges: [{id: "binding", from: "business", to: "fn", origin: "code-index", code_relation: "maps"}], bindings: {fn: {path: "app.py", line: 1}} };
const original = JSON.stringify(view);
const merged = withCodeGraph(view, slice);
assert.equal(JSON.stringify(view), original);
assert.equal(merged.manifest.build_id, "original");
assert.equal(merged.model.nodes.length, 3);
assert.equal(merged.model.edges.length, 1);
assert.equal(withCodeGraph(view, null), view);
assert.equal(nodeType(slice.nodes[0]), "code-file");
assert.equal(relationType(slice.edges[0]), "code-maps");
assert.equal(status(slice.nodes[1], {}, [], "latest"), "declared");
assert.deepEqual(profileFor("code").nodes, codeTypes);
assert.deepEqual(profileFor("code").edges, codeRelations);
for (const type of codeTypes) { assert.ok(meanings[type]); assert.ok(glyphShapes(type).length); }
for (const relation of codeRelations) assert.ok(relationStyles[relation]);
assert.deepEqual(cleanFilters(emptyFilters()), emptyFilters());
const hidden = cleanFilters({...emptyFilters(), nodes: ["business"]});
assert.deepEqual(hidden.nodes, ["business"]);
assert.deepEqual(cleanFilters({nodes:[],edges:[],regions:[]}).nodes,[]);
assert.deepEqual(cleanFilters({nodes:["state"],edges:["guard"]}).nodes,["state"]);

let calls = 0;
const layer = new CodeLayer(async () => { calls++; return { ok: true, json: async () => slice }; });
await layer.load({enabled: false});
assert.equal(calls, 0);
await layer.load({enabled: true, focus: "business"});
assert.equal(calls, 1);
assert.equal(layer.slice, slice);
await layer.load({enabled: false});
assert.equal(layer.slice, null);
let resolve;
const delayed = new CodeLayer(() => new Promise((done) => resolve = done));
const pending = delayed.load({enabled: true, focus: "business"});
delayed.clear();
resolve({ok: true, json: async () => slice});
assert.equal(await pending, null);
assert.equal(delayed.slice, null);
// Failed refreshes remove earlier source results rather than display stale facts.
layer.fetcher = async () => ({ok: false, json: async () => ({error: "Parser unavailable"})});
layer.slice = slice;
await assert.rejects(layer.load({enabled: true}), /Parser unavailable/);
assert.equal(layer.slice, null);
const text = (key, ...values) => key.replace(/\{(\d+)\}/g, (_, index) => values[index]);
assert.equal(codeSummary(null, text), "");
assert.equal(codeSummary({loaded_nodes: 400, total_nodes: 900, loaded_edges: 600, boundary_nodes: 80, omitted_edges: 12, errors: []}, text),
  "Code: 400 / 900 nodes · 600 relations · 80 boundary nodes · 12 related links omitted");
console.log("PASS: optional source projection, typed filters, stable model, no runtime claim and obsolete-request rejection.");
