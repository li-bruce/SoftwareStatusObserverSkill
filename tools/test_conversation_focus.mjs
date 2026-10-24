/** A known discussion must not override a developer's saved analysis view. */
import assert from "node:assert/strict";
import { createConversationFocus } from "../skills/vibelens/assets/stategraph-viewer/conversation.js";

let persisted = null, now = 10000, focuses = 0, clears = 0;
let scope = { available: true, revision: "confirmed-1", stale: false, nodes: ["review"], label: "Review flow" };
const elements = Object.fromEntries(["discussion-focus", "discussion-clear", "discussion-label"].map(id => [id, {hidden:false}]));
const originalDate = Date.now, originalFetch = globalThis.fetch, originalDocument = globalThis.document;
Date.now = () => now;
globalThis.document = { getElementById: id => elements[id] };
globalThis.fetch = async () => ({ok: true, status: 200, json: async () => structuredClone(scope)});
const create = () => createConversationFocus({
  onFocus: () => focuses++, onClear: () => clears++,
  readState: () => persisted, writeState: value => { persisted = structuredClone(value); },
});
try {
  let controller = create();
  await controller.refresh();
  assert.equal(focuses, 1, "a new discussion should guide the first visit");
  controller = create(); now += 3000;
  await controller.refresh();
  assert.equal(focuses, 1, "reload must not reframe an already-seen discussion");
  assert.deepEqual(controller.ids, ["review"]);
  elements["discussion-clear"].onclick();
  controller = create(); now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, [], "a cleared focus stays cleared after reload");
  elements["discussion-focus"].onclick();
  assert.equal(focuses, 2, "explicit focus still reframes the graph");
  scope.revision = "confirmed-2"; now += 3000;
  await controller.refresh();
  assert.equal(focuses, 3, "a genuinely new discussion guides the new region");
  scope.stale = true; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, []);
  scope.stale = false; now += 3000;
  await controller.refresh();
  assert.equal(focuses, 4);
  scope.available = false; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, [], "unavailable discussion cannot retain old highlights");
  assert.ok(clears > 0);
  persisted = null; scope.available = true; now += 3000;
  const previousFocuses = focuses;
  controller = createConversationFocus({onFocus:()=>focuses++, onClear:()=>clears++,
    readState:()=>persisted, writeState:value=>{persisted=value;}, hasSavedView:()=>true});
  await controller.refresh();
  assert.equal(focuses, previousFocuses, "old saved views survive the first preference migration");
  assert.equal(persisted.revision, "confirmed-2false");
  console.log("PASS: first/new discussion, saved view reload, dismissal, explicit focus and stale/unavailable scope.");
} finally {
  Date.now = originalDate; globalThis.fetch = originalFetch; globalThis.document = originalDocument;
}
