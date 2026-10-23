import assert from "node:assert/strict";
import fs from "node:fs";
import { DemoSession } from "../docs/site/demo-model.mjs";
import { extra, chinese } from "../docs/site/messages.mjs";
import { messages } from "../docs/site/demo-messages.mjs";

const sample = new DemoSession();
assert.equal(sample.operate("approve"), false, "Review requires an uploaded, checked image");
assert.equal(sample.events.length, 0);
assert.equal(sample.start("all"), true);
assert.equal(sample.start("review"), false, "Starting twice preserves the active capture scope");
assert.equal(sample.operate("upload"), true);
assert.equal(sample.current.visible, false, "Pending images stay out of the exhibition");
assert.equal(sample.current.notified, true, "Review notification follows image validation");
assert.equal(sample.operate("approve"), true);
const recorded = sample.stop();
assert.deepEqual(
  recorded.map((event) => event.operation),
  ["upload", "validate", "notify", "approve"],
);
assert.equal(recorded[3].before.state, "pending");
assert.equal(recorded[3].after.state, "displayed");
assert.equal(recorded[3].before.visible, false);
assert.equal(recorded[3].after.visible, true);
assert.equal(sample.events.length, 4, "Recording controls produce no application events");
const beforeReplay = structuredClone(sample.current);
const frame = sample.frame(1);
assert.equal(frame.after.state, "pending");
frame.after.state = "changed by reader";
assert.equal(sample.frame(1).after.state, "pending", "Replay results are detached copies");
assert.deepEqual(sample.current, beforeReplay, "Replay does not execute business actions");
assert.equal(sample.frame(-1), null);
assert.equal(sample.frame(1.5), null);

sample.reset();
sample.start("review");
sample.operate("upload");
assert.equal(sample.captured.length, 0, "Focused capture excludes upstream operations");
sample.operate("approve");
sample.stop();
assert.equal(sample.captured.length, 1);
assert.equal(sample.captured[0].operation, "approve");
assert.equal(
  sample.captured[0].before.notified,
  true,
  "Focused facts retain their actual boundary values",
);

sample.reset();
sample.operate("upload");
assert.equal(sample.operate("return"), false, "The iteration cannot act before being requested");
sample.addReturnPath();
sample.start();
assert.equal(sample.operate("return"), true);
assert.equal(sample.current.visible, false);
assert.equal(sample.operate("upload"), true, "The new return path allows resubmission");
assert.equal(sample.current.state, "pending");
assert.equal(sample.operate("approve"), true);
sample.stop();
assert.deepEqual(
  sample.captured.map((event) => event.operation),
  ["return", "upload", "validate", "notify", "approve"],
);
assert.equal(sample.current.visible, true);

sample.restartOperation();
assert.equal(sample.iterated, true, "A new operation retains the requested return/resubmit flow");
assert.equal(sample.current.state, "empty");
assert.equal(sample.captured.length, 0);
assert.equal(sample.operate("upload"), true);
assert.equal(sample.operate("return"), true);

sample.reset();
assert.equal(sample.captured.length, 0);
assert.equal(sample.events.length, 0);
assert.equal(sample.iterated, false);
assert.equal(sample.recording, false);
assert.throws(() => sample.start("unknown"));

for (const name of ["index.html", "demo.html"]) {
  const html = fs.readFileSync(new URL("../docs/site/" + name, import.meta.url), "utf8");
  const keys = [...html.matchAll(/data-i18n(?:-aria)?="([^"]+)"/g)].map((match) => match[1]);
  for (const key of keys) {
    assert.ok(
      extra[key]?.[1] || chinese[key] || messages[key]?.[1],
      name + ": Chinese copy missing for " + key,
    );
  }
}
for (const [key, pair] of Object.entries({ ...extra, ...messages })) {
  assert.equal(pair.length, 2, "Two locales required: " + key);
  assert.ok(
    pair.every((value) => typeof value === "string" && value.trim()),
    "Empty locale: " + key,
  );
}
console.log(
  "PASS: walkthrough transitions, bounded recording scope, exact replay, iteration, reset, and bilingual copy.",
);
