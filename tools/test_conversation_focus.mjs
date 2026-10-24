/** A known discussion must not override a developer's saved analysis view. */
import assert from "node:assert/strict";
import { createConversationFocus } from "../skills/vibelens/assets/stategraph-viewer/conversation.js";

let persisted = null, now = 10000, focuses = 0, clears = 0, language = null;
let scope = { available: true, revision: "confirmed-1", stale: false, nodes: ["review"], label: "Review flow" };
const originalDate = Date.now, originalFetch = globalThis.fetch;
Date.now = () => now;
globalThis.fetch = async () => ({ok: true, status: 200, json: async () => structuredClone(scope)});
const create = () => createConversationFocus({
  onFocus: () => focuses++, onClear: () => clears++,
  onLocale: value => {language = value;},
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
  controller.clear();
  now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, [], "polling does not undo a deliberate dismissal");
  controller = create(); now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, [], "a cleared focus stays cleared after reload");
  scope.revision = "confirmed-2"; now += 3000;
  await controller.refresh();
  assert.equal(focuses, 2, "a genuinely new discussion guides the new region");
  scope.stale = true; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, []);
  scope.stale = false; now += 3000;
  await controller.refresh();
  assert.equal(focuses, 3);
  scope.available = false; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, [], "unavailable discussion cannot retain old highlights");
  assert.ok(clears > 0);
  scope.available = true; scope.locale = 'zh-CN'; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, ['review'], 'same revision recovers after unavailable metadata');
  assert.equal(focuses, 3, 'recovery restores focus without reframing');
  assert.equal(language, 'zh-CN');
  scope.locale = 'en'; now += 3000;
  await controller.refresh();
  assert.equal(language, 'en', 'language can change without a new graph revision');
  const workingFetch = globalThis.fetch;
  for (const broken of [async()=>({status:404}), async()=>{throw Error('offline');}]) {
    globalThis.fetch = broken; now += 3000; await controller.refresh();
    assert.deepEqual(controller.ids, []);
    globalThis.fetch = workingFetch; now += 3000; await controller.refresh();
    assert.deepEqual(controller.ids, ['review']);
    assert.equal(focuses, 3);
  }
  persisted = null; scope.available = true; now += 3000;
  const previousFocuses = focuses;
  controller = createConversationFocus({onFocus:()=>focuses++, onClear:()=>clears++,
    readState:()=>persisted, writeState:value=>{persisted=value;}, hasSavedView:()=>true});
  await controller.refresh();
  assert.equal(focuses, previousFocuses, "old saved views survive the first preference migration");
  assert.equal(persisted.revision, "confirmed-2false");
  persisted = null; scope.available = false; now += 3000;
  controller = createConversationFocus({onFocus:()=>focuses++, onClear:()=>clears++,
    readState:()=>persisted, writeState:value=>{persisted=value;}, hasSavedView:()=>true});
  await controller.refresh();
  scope.available = true; scope.revision = 'confirmed-3'; now += 3000;
  await controller.refresh();
  assert.deepEqual(controller.ids, ['review'], 'a newly confirmed scope can focus after an initially empty project');
  assert.equal(focuses, previousFocuses + 1);
  console.log("PASS: DOM-free conversation focus, saved view reload, persistent dismissal and stale/unavailable scope.");
} finally {
  Date.now = originalDate; globalThis.fetch = originalFetch;
}
