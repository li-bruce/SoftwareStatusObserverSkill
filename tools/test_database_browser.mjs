/** Real SQLite + canonical viewer acceptance. Install Playwright or set NODE_PATH.
 * BO_BROWSER_EXECUTABLE optionally selects an installed Chromium executable.
 * BO_PYTHON optionally selects Python with the Skill's database dependencies.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const { chromium } = createRequire(import.meta.url)("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.resolve(
  process.env.BO_BROWSER_EVIDENCE || path.join(root, "docs/review/db-vis"),
);
await mkdir(output, { recursive: true });
const port = process.env.BO_BROWSER_PORT || "8869",
  base = `http://127.0.0.1:${port}`;
const python =
  process.env.BO_PYTHON ||
  path.join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
let logs = "",
  browser,
  page;
const errors = [],
  failures = [],
  checkpoints = {};
const server = spawn(python, ["-B", "-X", "utf8", "tools/database_demo.py", "--port", port], {
  cwd: root,
  windowsHide: true,
  stdio: ["ignore", "pipe", "pipe"],
});
server.stdout.on("data", (chunk) => (logs += chunk));
server.stderr.on("data", (chunk) => (logs += chunk));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function request(route, body) {
  const response = await fetch(
    base + route,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  assert.equal(response.ok, true, JSON.stringify(value));
  return value;
}
async function screenshot(name) {
  await page.screenshot({ path: path.join(output, name + ".png"), fullPage: true });
}
async function nodes() {
  return page
    .locator("#semantic [data-node-id]")
    .evaluateAll((items) =>
      Object.fromEntries(
        items.map((item) => [
          item.dataset.nodeId,
          { ...item.dataset, expanded: item.getAttribute("aria-expanded") },
        ]),
      ),
    );
}
async function pick(id) {
  await page
    .locator("#semantic [data-node-id]")
    .evaluateAll((items, key) => items.find((item) => item.dataset.nodeId === key).click(), id);
}
async function preset(id) {
  await page.selectOption("#analysis-view", id);
  await page.waitForTimeout(350);
}
async function waitReady() {
  for (let i = 0; i < 80; i++) {
    if (server.exitCode !== null) throw Error(logs);
    try {
      await request("/api/bo/health");
      return;
    } catch {
      await sleep(250);
    }
  }
  throw Error("Demo server did not become ready: " + logs);
}
async function menuClick(selector) {
  await page.click('#selection-menu');
  await page.click(selector);
}

try {
  await waitReady();
  const launch = { headless: true, args: ["--enable-unsafe-swiftshader"] };
  if (process.env.BO_BROWSER_EXECUTABLE) launch.executablePath = process.env.BO_BROWSER_EXECUTABLE;
  browser = await chromium.launch(launch);
  page = await browser.newPage({ viewport: { width: 1550, height: 1040 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => errors.push(error.stack || error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto(base + "/graph?lang=en");
  await page.waitForSelector("#semantic [data-node-id]", { state: "attached" });
  checkpoints.initial = await request("/api/view");
  await preset("database");
  await page.click("#expand");
  for (const [id, node] of Object.entries(await nodes())) {
    if (node.nodeType !== "dataset") continue;
    await pick(id);
    await menuClick("#node-expand");
  }
  await page.click("#fit");
  await page.waitForTimeout(300);
  const structural = await nodes();
  assert.ok(Object.values(structural).some((item) => item.nodeType === "column"));
  assert.ok(await page.locator('#semantic-edges [data-relation-type="references"]').count());
  await screenshot("database-01-structure-en");

  await preset("data-operations");
  await page.waitForFunction(() => document.querySelector('#semantic [data-node-id="load"]'));
  const operationNodes = await nodes();
  assert.ok(operationNodes.load && operationNodes.select && operationNodes.save);
  assert.ok(await page.locator('#semantic-edges [data-relation-type="reads"]').count());
  await page.click("#record-start");
  await page.waitForFunction(() => !document.getElementById("record-stop").disabled);
  checkpoints.commit = await request("/demo/run", {});
  checkpoints.rollback = await request("/demo/run", { rollback: true });
  assert.equal(checkpoints.commit.stored, 7);
  assert.equal(checkpoints.rollback.stored, 7);
  assert.equal(checkpoints.rollback.status, "rolled_back");
  assert.equal(checkpoints.rollback.observer_events, 0);
  assert.equal(
    checkpoints.commit.mapping_status,
    "pending",
    "both cases must execute before claiming mapping coverage",
  );
  assert.equal(
    checkpoints.rollback.mapping_status,
    "passed",
    "demo uses the same strict runtime gate as project integrations",
  );
  await page.waitForTimeout(1100);
  await page.click("#record-stop");
  await page.waitForFunction(() =>
    [...document.getElementById("record-list").options].some((option) => option.value),
  );
  await page.click("#replay-live");
  await page.waitForTimeout(300);
  checkpoints.afterRun = await request("/api/view");
  const eventNodes = new Set(checkpoints.afterRun.events.map((event) => event.node));
  assert.deepEqual([...eventNodes].sort(), ["load", "publish", "save", "select", "transaction"]);
  assert.ok(
    checkpoints.afterRun.events.some(
      (event) =>
        event.node === "select" &&
        event.outputs.input_count === 12 &&
        event.outputs.output_count === 7,
    ),
  );
  assert.ok(
    checkpoints.afterRun.events.some(
      (event) => event.node === "transaction" && event.outputs.committed === false,
    ),
  );
  assert.ok(
    checkpoints.afterRun.events.some(
      (event) => event.node === "transaction" && event.outputs.committed === true,
    ),
  );
  await pick("select");
  await menuClick("#details");
  await page.waitForFunction(() =>
    document.getElementById("detail-rows").textContent.includes("12 → 7"),
  );
  await screenshot("database-02-processing-en");
  await page.click("#close-detail");
  const recordings = await request("/api/recordings");
  const recordingId = recordings.recordings?.[0]?.id || recordings.items?.[0]?.id;
  assert.ok(recordingId, JSON.stringify(recordings));
  await page.selectOption("#record-list", recordingId);
  await page.waitForFunction(() => !document.getElementById("replay").hidden);
  await page.selectOption("#replay-grain", "events");
  const steps = await page
    .locator("#replay-events option")
    .evaluateAll((options) =>
      options.map((option) => ({ value: option.value, text: option.textContent })),
    );
  let captured = false;
  for (const step of steps) {
    await page.selectOption("#replay-events", step.value);
    if ((await page.locator("#step-changes").textContent()).includes("output_count")) {
      checkpoints.replay = await page.locator("#step-changes").textContent();
      await screenshot("database-03-replay-en");
      captured = true;
      break;
    }
  }
  assert.ok(captured, "Replay exposes the actual processing count changes");
  await page.click("#replay-live");

  await pick("load");
  const point = (await nodes()).load;
  await page.mouse.move(Number(point.screenX), Number(point.screenY));
  await page.mouse.down();
  await page.mouse.move(Number(point.screenX) + 55, Number(point.screenY) + 36, { steps: 6 });
  await page.mouse.up();
  await menuClick("#pin");
  await page.click("#filter-toggle");
  await page.locator('#filter-edges input[value="writes"]').uncheck();
  await page.click("#close-filters");
  assert.equal(await page.locator('#semantic-edges [data-relation-type="writes"]').count(), 0);
  await pick("transaction");
  await menuClick("#hide-node");
  assert.ok(!(await nodes()).transaction);
  await page.waitForTimeout(650);
  checkpoints.beforeUpgrade = await nodes();
  checkpoints.upgrade = await request("/demo/upgrade", {});
  await page.waitForFunction(
    async (expected) => (await (await fetch("/api/view")).json()).manifest.build_id === expected,
    checkpoints.upgrade.build_id,
  );
  await page.waitForTimeout(1300);
  checkpoints.afterUpgrade = await nodes();
  assert.equal(checkpoints.afterUpgrade.load.x, checkpoints.beforeUpgrade.load.x);
  assert.equal(checkpoints.afterUpgrade.load.y, checkpoints.beforeUpgrade.load.y);
  assert.equal(checkpoints.afterUpgrade.load.pinned, "true");
  assert.equal(await page.locator('#filter-edges input[value="writes"]').isChecked(), false);
  assert.ok(!checkpoints.afterUpgrade.transaction);
  const freshRecords = await request("/api/recordings");
  assert.equal((freshRecords.recordings || freshRecords.items || []).length, 0);
  assert.equal(
    await page
      .locator("#record-list option")
      .evaluateAll((options) => options.filter((option) => option.value).length),
    0,
  );
  const upgraded = await request("/api/view");
  assert.ok(
    upgraded.model.nodes.some((node) => node.data_role === "column" && node.label === "caption"),
  );
  assert.notEqual(checkpoints.initial.manifest.build_id, upgraded.manifest.build_id);
  await screenshot("database-04-updated-layout-en");
  await page.reload();
  await page.waitForSelector('#semantic [data-node-id="load"]', { state: "attached" });
  assert.equal((await nodes()).load.x, checkpoints.beforeUpgrade.load.x);
  assert.ok(!(await nodes()).transaction);
  await page.selectOption("#language", "zh-CN");
  await page.waitForSelector('#semantic [data-node-id="load"]', { state: "attached" });
  await preset("database");
  await page.click("#expand");
  for (const [id, node] of Object.entries(await nodes())) {
    if (node.nodeType !== "dataset" || node.expanded === "true") continue;
    await pick(id);
    await menuClick("#node-expand");
  }
  await page.click("#fit");
  await page.waitForTimeout(350);
  await screenshot("database-05-structure-zh");
  checkpoints.unavailable = await request("/demo/database-check", { available: false });
  assert.equal(checkpoints.unavailable.valid, false);
  await page.waitForFunction(
    () => document.getElementById("connection").dataset.databaseStale === "true",
  );
  const stale = await request("/api/view");
  assert.equal(stale.manifest.build_id, checkpoints.upgrade.build_id);
  assert.ok(
    stale.model.nodes.some((node) => node.data_role === "column" && node.label === "caption"),
  );
  await screenshot("database-06-unavailable-zh");
  checkpoints.recovered = await request("/demo/database-check", { available: true });
  assert.equal(checkpoints.recovered.valid, true);
  await page.waitForFunction(
    () => document.getElementById("connection").dataset.databaseStale === "false",
  );
  assert.equal(errors.length, 0, errors.join("\n"));
  console.log(
    "PASS: real SQLite query/processing/write, commit/rollback, observer exclusion, replay, schema/source refresh, layout/filter persistence and EN/ZH viewer.",
  );
} catch (error) {
  failures.push(error.stack || String(error));
  if (page) await screenshot("database-failure").catch(() => {});
  process.exitCode = 1;
  console.error(error);
} finally {
  await writeFile(
    path.join(output, "database-browser-results.json"),
    JSON.stringify({ passed: !failures.length, failures, errors, checkpoints }, null, 2),
  );
  await writeFile(path.join(output, "database-browser-server.log"), logs);
  await browser?.close();
  await request("/demo/stop", {}).catch(() => {});
  await new Promise((resolve) => {
    if (server.exitCode !== null) resolve();
    else {
      server.once("exit", resolve);
      setTimeout(() => {
        server.kill();
        resolve();
      }, 3000);
    }
  });
}
