/** Real graph service: context actions, conversation locale, recording and quiet stale focus. */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.resolve(process.env.BO_BROWSER_EVIDENCE || ".validation/viewer-controls");
const python = process.env.BO_PYTHON || path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const base = `http://127.0.0.1:${process.env.BO_BROWSER_PORT || "8878"}`;
await mkdir(output, { recursive: true });
let logs = "", browser, page, project;
const errors = [], checks = [];
const server = spawn(python, ["-B", "-X", "utf8", "tools/database_demo.py", "--port", new URL(base).port], {cwd:root, windowsHide:true, stdio:["ignore","pipe","pipe"]});
server.stdout.on("data", data => logs += data); server.stderr.on("data", data => logs += data);
async function api(route, data) {
  const response = await fetch(base+route, data === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
  const result = await response.json(); assert.ok(response.ok, JSON.stringify(result)); return result;
}
async function language(value) {
  await new Promise((resolve,reject) => {
    const child = spawn(python, ["-B", "-X", "utf8", "skills/vibelens/scripts/bo_design.py", "language", "--root", project, "--locale", value, "--source", "Viewer acceptance conversation"], {cwd:root,windowsHide:true});
    let message=""; child.stderr.on("data", data=>message+=data); child.stdout.on("data", data=>message+=data);
    child.on("error",reject); child.on("exit", code=>code===0 ? resolve() : reject(Error(message)));
  });
}
async function rightClickNode(id) {
  const point = await page.locator(`#semantic [data-node-id="${id}"]`).evaluate(node=>({x:+node.dataset.screenX,y:+node.dataset.screenY}));
  await page.mouse.click(point.x,point.y,{button:"right"});
  await page.waitForSelector('#graph-menu[data-kind="node"]',{state:"visible"});
}
const shot = name => page.screenshot({path:path.join(output,name+".png"),fullPage:true});
try {
  for(let attempt=0;attempt<100;attempt++) {try {await api('/api/bo/health'); break;} catch {await new Promise(resolve=>setTimeout(resolve,250));}}
  project=logs.match(/Disposable application: (.+)/)?.[1].trim(); assert.ok(project);
  browser=await chromium.launch({headless:true,args:["--enable-unsafe-swiftshader"],...(process.env.BO_BROWSER_EXECUTABLE?{executablePath:process.env.BO_BROWSER_EXECUTABLE}:{})});
  page=await browser.newPage({viewport:{width:1440,height:960},locale:"zh-CN"});
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base+'/graph'); await page.waitForSelector('#semantic [data-node-id="publish"]',{state:'attached'});
  assert.equal(await page.locator('html').getAttribute('lang'),'en','browser locale does not override English default');
  assert.equal(await page.locator('#title').textContent(),'VibeLens');
  assert.equal(await page.locator('.view-tools').count(),0);
  for(const id of ['record-start','record-stop','record-clear']) {
    assert.equal(await page.locator('#'+id+' svg').count(),1);
    assert.ok(await page.locator('#'+id).getAttribute('aria-label'));
    assert.equal((await page.locator('#'+id).textContent()).trim(),'');
  }
  await language('zh-CN'); await page.waitForFunction(()=>document.documentElement.lang==='zh-CN');
  await page.waitForSelector('#semantic [data-node-id="publish"]',{state:'attached'});
  assert.equal(await page.locator('#record-start').getAttribute('aria-label'),'开始记录');
  await page.selectOption('#language','en'); await page.waitForFunction(()=>document.documentElement.lang==='en');
  await page.goto(base+'/graph'); await page.waitForSelector('#semantic [data-node-id="publish"]',{state:'attached'});
  assert.equal(await page.locator('html').getAttribute('lang'),'en','manual choice wins over conversation');
  checks.push('English fallback, live conversation language, translated accessible icons, persisted manual override');
  await page.click('#fit'); await page.waitForTimeout(250); await rightClickNode('publish');
  await page.keyboard.press('End'); assert.equal(await page.evaluate(()=>document.activeElement.id),'hide-node');
  await page.keyboard.press('Escape'); assert.equal(await page.evaluate(()=>document.activeElement.id),'viewport');
  await page.keyboard.press('Shift+F10'); await page.waitForSelector('#graph-menu',{state:'visible'});
  await shot('01-node-context-menu');
  await page.click('#annotate'); await page.fill('#node-note','Inspect this flow after an iteration');
  await page.check('#node-core'); await page.locator('#annotation-form button[type="submit"]').click();
  await page.click('#selection-menu'); await page.click('#pin');
  assert.equal(await page.evaluate(()=>!!document.activeElement.closest('#graph-menu')),false,'completed actions restore focus outside the hidden menu');
  await page.waitForFunction(()=>document.querySelector('#semantic [data-node-id="publish"]').dataset.pinned==='true');
  await page.click('#selection-menu'); await page.click('#node-expand'); await page.click('#fit');
  await page.waitForSelector('#semantic-edges [data-edge-id]',{state:'attached'});
  await page.locator('#semantic-edges [data-edge-id]').first().focus(); await page.keyboard.press('Shift+F10');
  assert.equal(await page.locator('#graph-menu').getAttribute('data-kind'),'edge');
  await shot('02-edge-context-menu'); await page.click('#edge-inspect');
  assert.ok(await page.locator('#edge-members li').count()); await page.click('#close-edge');
  const visibleLegend=await page.locator('#legend-types > div:not([hidden])').evaluateAll(nodes=>nodes.map(n=>({type:n.dataset.legendNode,title:n.title,text:n.textContent})));
  assert.ok(visibleLegend.length); assert.ok(visibleLegend.every(item=>item.title && item.text.length < 40));
  await page.reload(); await page.waitForSelector('#semantic [data-node-id="publish"]',{state:'attached'});
  await page.locator('#semantic [data-node-id="publish"]').evaluate(node=>node.click());
  await page.click('#selection-menu'); await page.click('#annotate');
  assert.equal(await page.inputValue('#node-note'),'Inspect this flow after an iteration');
  await page.click('#close-detail');
  checks.push('Actual pointer context menu, keyboard navigation, edge actions, compact legend, persisted notes/core/pin');
  let scope={available:true,locale:'en',revision:'controls-focus-1',stale:false,nodes:['publish'],label:'Confirmed publish flow'};
  await page.route('**/api/design',route=>route.fulfill({json:scope}));
  await page.waitForSelector('#semantic [data-discussion="true"]',{state:'attached'});
  assert.equal(await page.locator('#discussion-bar').count(),0,'conversation focus has no separate UI bar');
  await page.locator('#viewport').focus(); await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!document.querySelector('#semantic [data-discussion="true"]'));
  await page.waitForFunction(async()=>Object.entries((await (await fetch('/api/preferences')).json()).entries).some(([key,value])=>key.endsWith(':analysis')&&JSON.parse(value).discussion?.active===false));
  await page.reload(); await page.waitForSelector('#semantic [data-node-id="publish"]',{state:'attached'});
  await page.waitForTimeout(2200);
  assert.equal(await page.locator('#semantic [data-discussion="true"]').count(),0,'dismissal survives reload and polling');
  scope={...scope,revision:'controls-focus-2'};
  await page.waitForSelector('#semantic [data-discussion="true"]',{state:'attached'});
  // Zoom out, then click clear space above the graph.
  const canvas=await page.locator('#viewport canvas').boundingBox();
  await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);
  await page.mouse.wheel(0,4000); await page.waitForTimeout(350);
  await page.mouse.click(canvas.x+canvas.width/2,canvas.y+40);
  await page.waitForFunction(()=>!document.querySelector('#semantic [data-discussion="true"]'));
  scope={...scope,revision:'controls-focus-3'};
  await page.waitForSelector('#semantic [data-discussion="true"]',{state:'attached'});
  scope={...scope,stale:true};
  await page.waitForFunction(()=>!document.querySelector('#semantic [data-discussion="true"]'));
  assert.equal(await page.locator('#semantic [data-discussion="true"]').count(),0);
  checks.push('No discussion bar; Escape and blank-canvas dismissal; persisted dismissal and new-revision focus; silent stale removal');
  await shot('03-stale-focus-removed');
  await page.unroute('**/api/design');
  const before=(await api('/api/view')).events.length;
  await page.waitForFunction(()=>!document.getElementById('record-start').disabled); await page.click('#record-start');
  await page.waitForFunction(()=>!document.getElementById('record-stop').disabled);
  assert.equal(await page.locator('#record-clear').isDisabled(),true);
  // The fixture independently seeds twelve candidates; IDs 1 through 7 are approved.
  const operation=await api('/demo/run',{rollback:false}); assert.equal(operation.stored,7);
  await page.click('#record-stop'); await page.waitForSelector('#replay',{state:'visible'});
  const first=(await api('/api/recordings')).recordings[0]; assert.ok(first.events>0);
  await page.click('#replay-next'); await shot('04-recording-replay');
  await page.click('#replay-live'); await page.waitForFunction(()=>!document.getElementById('record-start').disabled);
  await page.click('#record-start'); await page.waitForFunction(()=>!document.getElementById('record-stop').disabled);
  const blocked=await fetch(base+'/api/recordings/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:first.id})});
  assert.equal(blocked.status,400); await page.click('#record-stop'); await page.waitForSelector('#replay',{state:'visible'});
  await page.route(base+'/api/recordings/'+first.id, route => route.fulfill({status:503,json:{error:'Deliberate recording load failure'}}));
  await page.selectOption('#record-list',first.id);
  await page.waitForFunction(()=>document.getElementById('record-status').textContent.includes('Deliberate recording load failure'));
  assert.notEqual(await page.inputValue('#record-list'),first.id,'failed loads restore the displayed record selection');
  await page.unroute(base+'/api/recordings/'+first.id);
  await page.route(base+'/api/recordings/'+first.id, async route => {
    await new Promise(resolve=>setTimeout(resolve,500));
    await route.continue();
  });
  await page.selectOption('#record-list',first.id);
  assert.equal(await page.locator('#record-clear').isDisabled(),true,'loading a different record disables destructive actions');
  await page.waitForFunction(()=>!document.getElementById('record-clear').disabled); await page.click('#record-clear');
  await page.waitForSelector('#replay',{state:'hidden'});
  const remaining=(await api('/api/recordings')).recordings;
  assert.equal(remaining.length,1); assert.notEqual(remaining[0].id,first.id);
  const events=(await api('/api/view')).events;
  assert.ok(events.length>before); assert.equal(remaining[0].events,0,'observer-only actions produce no business events');
  assert.ok(events.every(event=>!String(event.node).includes('recordings')));
  checks.push('Quiet stale focus, real operation capture/replay, active-clear rejection, delayed-load clear guard, isolated selected-record clear, zero observer-only events');
  await page.setViewportSize({width:390,height:844}); await page.click('#fit');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#semantic [data-node-id="publish"]').evaluate(node=>node.click());
  await page.click('#selection-menu');
  const bounds=await page.locator('#graph-menu').boundingBox(); assert.ok(bounds.x>=0 && bounds.x+bounds.width<=390);
  await shot('05-mobile-menu'); await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'result.json'),JSON.stringify({passed:true,checks,errors,recordedEvents:first.events,remainingRecordings:remaining.length},null,2));
  console.log('PASS: conversation locale, context menus, stale scope, recording controls and 390px viewer.');
} catch(error) {
  if(page) await shot('failure').catch(()=>{});
  await writeFile(path.join(output,'result.json'),JSON.stringify({passed:false,checks,errors,error:String(error.stack)},null,2));
  throw error;
} finally { await browser?.close(); if(server.exitCode===null) server.kill(); await writeFile(path.join(output,'server.log'),logs); }
