/** Real canonical viewer + SQLite application, including live source edits. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, writeFile, unlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const {chromium} = createRequire(import.meta.url)("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.resolve(process.env.BO_BROWSER_EVIDENCE || path.join(root, "docs/review/code-vis"));
await mkdir(output, {recursive:true});
const port = process.env.BO_BROWSER_PORT || "8871", base = `http://127.0.0.1:${port}`;
const python = process.env.BO_PYTHON || path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const server = spawn(python, ["-B", "-X", "utf8", "tools/database_demo.py", "--port", port], {cwd:root, windowsHide:true, stdio:["ignore","pipe","pipe"]});
let logs = "", browser, page;
const errors = [], checkpoints = {};
server.stdout.on("data", (s)=>logs+=s); server.stderr.on("data", (s)=>logs+=s);
const sleep=(ms)=>new Promise((r)=>setTimeout(r,ms));
async function api(route, body) {
  const response = await fetch(base+route, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json(); assert.ok(response.ok, JSON.stringify(data)); return data;
}
async function pick(id) {
  await page.locator("#semantic [data-node-id]").evaluateAll((nodes,id)=>nodes.find(n=>n.dataset.nodeId===id).click(),id);
}
async function shot(name) { await page.screenshot({path:path.join(output,name+".png"),fullPage:true}); }
try {
  for(let i=0;i<80;i++) {try {await api("/api/bo/health");break;} catch {await sleep(250);} }
  const launch = {headless:true,args:["--enable-unsafe-swiftshader"]};
  if(process.env.BO_BROWSER_EXECUTABLE) launch.executablePath=process.env.BO_BROWSER_EXECUTABLE;
  browser=await chromium.launch(launch); page=await browser.newPage({viewport:{width:1550,height:1040}});
  page.on("pageerror",(e)=>errors.push(e.message));
  let codeRequests=0; page.on("request",r=>{if(r.url().includes("/api/code/graph"))codeRequests++;});
  await page.goto(base+"/graph?lang=en");
  await page.waitForSelector('#semantic [data-node-id="publish"]',{state:"attached"});
  await page.waitForTimeout(1100);
  assert.equal(codeRequests,0,"default overview must not construct a code index");
  await shot("01-default-overview");
  await pick("publish"); await page.click("#code-local");
  await page.waitForSelector('#semantic [data-node-type="code-function"]',{state:"attached"});
  await page.click("#fit");
  assert.ok(await page.locator('#semantic-edges [data-relation-type="code-maps"]').count());
  checkpoints.focus=await api("/api/code/graph?focus=publish");
  assert.ok(checkpoints.focus.edges.some(e=>e.code_relation==="calls"));
  await shot("02-business-to-code");
  await page.click("#code-local");
  await page.waitForFunction(()=>!document.querySelector('#semantic [data-node-type="code-function"]'));
  await page.selectOption("#analysis-view","code");
  await page.waitForSelector('#semantic [data-node-type="code-file"]',{state:"attached"});
  await page.click("#expand"); await page.click("#fit");
  checkpoints.all=await api("/api/code/graph");
  const file=checkpoints.all.nodes.find(n=>n.code_role==="file"&&n.label==="gallery.py");
  await pick(file.id); await page.click("#pin"); await page.click("#annotate");
  await page.fill("#node-note","Review this file after each schema change");
  await page.locator('#annotation-form button[type="submit"]').click();
  await page.waitForTimeout(900);
  checkpoints.layoutBefore = await page.locator('#semantic [data-node-id]').evaluateAll((nodes,id)=>({...nodes.find(n=>n.dataset.nodeId===id).dataset}),file.id);
  await shot("03-complete-code-view");
  await page.reload(); await page.waitForSelector('#semantic [data-node-type="code-function"]',{state:"attached"});
  await pick(file.id); await page.click("#annotate");
  assert.equal(await page.inputValue("#node-note"),"Review this file after each schema change");
  await page.locator('#annotation-form button[type="submit"]').click();
  await page.click("#source"); await page.click("#full-source");
  await page.waitForFunction(()=>document.getElementById("source-code").textContent.includes("def publish"));
  await page.click("#close-detail");
  const projectPath=logs.match(/Disposable application: (.+)/)?.[1].trim();
  assert.ok(projectPath,logs);
  const added=path.join(projectPath,"new_feature.py");
  await writeFile(added,"def newly_added(value):\n    return value\n");
  await page.waitForFunction(()=>[...document.querySelectorAll('#semantic [data-node-id]')].some(n=>n.textContent.includes("new_feature.py")));
  checkpoints.added=await api("/api/code/graph");
  assert.notEqual(checkpoints.all.revision,checkpoints.added.revision);
  await shot("04-new-file-auto-refresh");
  await writeFile(added,"def invalid(:\n");
  await page.waitForFunction(()=>document.getElementById("code-status").textContent.includes("incomplete"));
  checkpoints.parseFailure=await api("/api/code/graph");
  assert.equal(checkpoints.parseFailure.status,"incomplete");
  await shot("05-parser-error-is-visible");
  await unlink(added);
  await page.waitForFunction(()=>!document.getElementById("code-status").textContent.includes("incomplete"));
  const before=await api("/api/view");
  for(let i=0;i<3;i++)await api("/api/code/graph?focus=publish");
  assert.equal((await api("/api/view")).events.length,before.events.length);
  await page.selectOption("#analysis-view","data-operations");
  await page.click("#record-start");
  await page.waitForFunction(()=>!document.getElementById("record-stop").disabled);
  checkpoints.run=await api("/demo/run",{});
  assert.equal(checkpoints.run.stored,7);
  await page.click("#record-stop");
  await page.waitForFunction(()=>!document.getElementById("replay").hidden);
  await page.click("#replay-live");
  await api("/demo/upgrade",{});
  await page.waitForFunction(()=>document.getElementById("record-list").options.length===1);
  await page.selectOption("#analysis-view","code");
  await page.waitForSelector('#semantic [data-node-type="code-file"]',{state:"attached"});
  checkpoints.layoutAfter = await page.locator('#semantic [data-node-id]').evaluateAll((nodes,id)=>({...nodes.find(n=>n.dataset.nodeId===id).dataset}),file.id);
  assert.equal(checkpoints.layoutAfter.x,checkpoints.layoutBefore.x);
  assert.equal(checkpoints.layoutAfter.y,checkpoints.layoutBefore.y);
  assert.equal(checkpoints.layoutAfter.pinned,"true");
  await pick(file.id); await page.click("#annotate");
  assert.equal(await page.inputValue("#node-note"),"Review this file after each schema change");
  await page.locator('#annotation-form button[type="submit"]').click();
  await page.selectOption("#language","zh-CN");
  await page.waitForFunction(()=>document.getElementById("code-status").textContent.includes("代码"));
  await shot("06-updated-code-zh");
  checkpoints.final=await api("/api/code/graph");
  assert.equal(checkpoints.final.status,"current");
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,"browser-result.json"),JSON.stringify({passed:true,errors,checkpoints},null,2));
  console.log("PASS: lazy/focused/full code views, relationships, source, live edits/errors/deletion, persistence, exclusion, real recording and bilingual reload.");
} catch(error) {
  if(page)await shot("failure");
  if(page) checkpoints.codeStatus = await page.locator("#code-status").evaluate(n=>({text:n.textContent,detail:n.title})).catch(()=>null);
  await writeFile(path.join(output,"browser-result.json"),JSON.stringify({passed:false,error:String(error.stack),errors,checkpoints,logs},null,2));
  throw error;
} finally {
  await browser?.close();
  try{await api("/demo/stop",{});}catch{}
  if(server.exitCode===null)server.kill();
  await writeFile(path.join(output,"server.log"),logs);
}
