/** Exercise the bilingual product introduction and its separate sample walkthrough. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const { chromium } = createRequire(import.meta.url)("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.resolve(process.env.BO_SITE_EVIDENCE || ".validation/site-browser");
const python = process.env.BO_PYTHON || path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const base = (process.env.BO_SITE_URL || "http://127.0.0.1:" + (process.env.BO_SITE_PORT || "8873")).replace(/\/$/, "");
// A supplied URL tests the deployed introduction; the default starts a local copy.
const server = process.env.BO_SITE_URL ? null : spawn(python, ["-B", "-m", "http.server", new URL(base).port, "--bind", "127.0.0.1", "--directory", "docs/site"], {cwd: root, windowsHide: true, stdio: "ignore"});
let browser;
const errors = [], checks = [];
await mkdir(output, {recursive: true});
try {
  for (let attempt = 0; attempt < 80; attempt++) {
    try { if ((await fetch(base)).ok) break; } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  browser = await chromium.launch({headless: true, ...(process.env.BO_BROWSER_EXECUTABLE ? {executablePath: process.env.BO_BROWSER_EXECUTABLE} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.on("pageerror", error => errors.push(error.message));
  for (const language of ["en", "zh-CN"]) {
    await page.goto(base + "/?lang=" + language);
    await page.waitForSelector("#concept-graph svg");
    assert.equal(await page.locator("html").getAttribute("lang"), language);
    assert.match(await page.locator(".brand").innerText(), /^VibeLens/);
    assert.equal(await page.locator("a.github").getAttribute("href"), "https://github.com/li-bruce/VibeLens");
    assert.match(await page.locator("#install-prompt").textContent(), /\$vibelens/);
    assert.equal(await page.locator("[data-view]").count(), 7);
    for (const view of ["business", "state", "decision", "function", "data", "source", "mixed"]) {
      await page.click("#tab-" + view);
      assert.equal(await page.locator("#tab-" + view).getAttribute("aria-selected"), "true");
      const description = (await page.locator("#level-body").textContent()).trim();
      assert.ok(description && !description.startsWith("level."), "View description is missing");
      assert.ok(await page.locator("#concept-graph [data-node]").count());
    }
    await page.click("#tab-data");
    await page.locator("#explore").screenshot({path: path.join(output, language + "-data.png")});
    await page.click("#tab-source");
    await page.locator("#explore").screenshot({path: path.join(output, language + "-source.png")});
    const before = await page.locator("#level-body").textContent();
    await page.click("#language");
    assert.notEqual(await page.locator("#level-body").textContent(), before);
    await page.click("#language");
    checks.push(language + ": seven connected views and language switch");
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(base + "/?lang=" + language);
    await page.waitForSelector("#concept-graph svg");
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Page overflows on mobile");
    await page.screenshot({path: path.join(output, language + "-mobile.png"), fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
  }
  await page.goto(base + "/demo.html?lang=zh-CN");
  assert.match(await page.locator(".brand").innerText(), /^VibeLens/);
  assert.equal(await page.locator("a.github").getAttribute("href"), "https://github.com/li-bruce/VibeLens");
  await page.click("#stage-record");
  await page.click("#start");
  await page.click("#upload");
  await page.click("#approve");
  await page.click("#stop");
  assert.equal(await page.locator("#play").isDisabled(), false);
  await page.locator("#replay").fill("1");
  assert.ok((await page.locator("#change-detail").innerText()).length > 15);
  await page.screenshot({path: path.join(output, "demo-replay.png"), fullPage: true});
  checks.push("Separate sample walkthrough: record, upload, approve, stop and inspect replay");
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, "result.json"), JSON.stringify({passed: true, url: base, checks, errors}, null, 2));
  console.log("PASS: bilingual seven-view introduction, 390px layout and independent recording walkthrough.");
} catch (error) {
  await writeFile(path.join(output, "result.json"), JSON.stringify({passed: false, url: base, checks, errors, error: String(error.stack)}, null, 2));
  throw error;
} finally {
  await browser?.close();
  if (server?.exitCode === null) server.kill();
}
