// Actual browser controls against an isolated, already accepted application copy.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=process.env.BO_TEST_URL||'http://127.0.0.1:8837';
const out=process.env.BO_UI_OUT||path.join(__dirname,'ui');fs.mkdirSync(out,{recursive:true});
const reportPath=process.env.BO_UI_RESULT||path.join(__dirname,'ui-result.json');
const report={scope:'Local synthetic archive; real browser, SQLite, worker and record operations',checks:[],errors:[]};
function passed(name,evidence={}){report.checks.push({name,passed:true,...evidence});console.log('PASS '+name);}
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:960}}),page=await context.newPage();
  context.setDefaultTimeout(15000);
  page.on('pageerror',e=>report.errors.push(e.message));page.on('crash',()=>report.errors.push('page crashed'));
  await page.goto(base+'/graph');
  await page.waitForFunction(()=>window.graphDebug?.graph?.boxes.length&& !document.querySelector('#record-start').disabled);
  const inspect=()=>page.evaluate(()=>({nodes:[...document.querySelector('#semantic').children].map(e=>({...e.dataset,label:e.textContent})),metrics:window.graphDebug.metrics}));
  const focus=async id=>{await page.locator(`#semantic [data-node-id="${id}"]`).focus();};
  const photo=async name=>page.screenshot({path:path.join(out,name),fullPage:true});
  await page.selectOption('#analysis-view','overview');await page.click('#collapse');await page.click('#fit');
  assert.equal((await inspect()).nodes.length,3);assert.equal((await inspect()).metrics.webgl,true);
  passed('Initial view shows three business groups on WebGL');await photo('01-initial.png');
  await focus('flow.checks');await page.click('#node-expand');await page.click('#fit');
  await page.waitForFunction(()=>['circle','self'].includes(document.querySelector('#semantic [data-node-id="flow.checks"]').dataset.representation));
  const before=await page.evaluate(()=>Object.fromEntries(window.graphDebug.graph.boxes.map(b=>[b.id,{x:b.x,y:b.y}])));
  const spot=await page.evaluate(()=>{
   const debug=window.graphDebug,r=debug.graph.regions.find(r=>r.id==='flow.checks'),rect=document.querySelector('canvas').getBoundingClientRect();
   for(let i=0;i<60;i++){
    const a=i*Math.PI/30,x=r.cx+Math.cos(a)*r.radius*.9,y=r.cy+Math.sin(a)*r.radius*.9;
    const sx=rect.left+x*debug.camera.scale+debug.camera.pan.x,sy=rect.top+y*debug.camera.scale+debug.camera.pan.y;
    if(sx<rect.left+60||sx>rect.right-90||sy<rect.top+60||sy>rect.bottom-60)continue;
    if(debug.graph.boxes.some(b=>b.id!=='flow.checks'&&Math.hypot(b.x+b.w/2-x,b.y+b.h/2-y)<75))continue;
    return {x:sx,y:sy};
   }throw Error('No blank group location');
  });
  await page.mouse.move(spot.x,spot.y);await page.mouse.down();await page.mouse.move(spot.x+48,spot.y-24,{steps:8});await page.mouse.up();
  await page.waitForTimeout(500);
  const after=await page.evaluate(()=>Object.fromEntries(window.graphDebug.graph.boxes.map(b=>[b.id,{x:b.x,y:b.y}])));
  const dx=after['flow.checks'].x-before['flow.checks'].x,dy=after['flow.checks'].y-before['flow.checks'].y;
  assert(Math.abs(dx)>5&&Math.abs(dy)>5);
  for(const id of ['content_check','index_check','lifecycle']){assert(Math.abs(after[id].x-before[id].x-dx)<.1);assert(Math.abs(after[id].y-before[id].y-dy)<.1);}
  passed('Dragging blank region moves parent and its children together',{dx,dy});await photo('02-expanded-group.png');
  await focus('flow.checks');await page.click('#annotate');await page.fill('#node-name','检查与排队');await page.fill('#node-note','审查重点：同次运行的活动和名额');await page.check('#node-core');await page.click('#annotation-form button[type=submit]');
  await page.waitForFunction(()=>document.querySelector('#layout-status').textContent.includes('已保存到项目'));
  await page.reload();await page.waitForFunction(()=>window.graphDebug?.graph&&document.querySelector('#semantic [data-node-id="flow.checks"]')?.textContent==='检查与排队');
  assert.equal((await page.locator('#semantic [data-node-id="flow.checks"]').getAttribute('data-core')),'true');
  const persisted=await (await page.request.get(base+'/api/preferences')).json();
  assert(Object.values(persisted.entries).some(raw=>raw.includes('审查重点')));
  const refreshed=await page.evaluate(()=>{const b=window.graphDebug.graph.byId.get('flow.checks');return {x:b.x,y:b.y}});
  assert(Math.abs(refreshed.x-after['flow.checks'].x)<.1);assert(Math.abs(refreshed.y-after['flow.checks'].y)<.1);
  passed('Group positions, expansion, custom name, note and core mark survive reload',{revision:persisted.revision});
  await page.fill('#node-search','execution.schedule');await page.locator('#search-results button').first().click();
  await page.click('#source');assert((await page.locator('#detail-title').innerText()).includes('bo_stategraph/workflow.py'));
  await photo('03-source-and-hierarchy.png');await page.click('#close-detail');
  assert.equal(await page.locator('#analysis-details').getAttribute('aria-pressed'),'true');passed('Searching a hidden execution function reveals its hierarchy and source');
  for(const id of ['business','states','functions','permission','resources','data','runtime','blocked','shared','overview']){
   await page.selectOption('#analysis-view',id);await page.waitForTimeout(110);
   assert.equal(await page.locator('#analysis-view').inputValue(),id);
  }passed('All ten view presets remain selectable');
  await page.click('#filter-toggle');await page.fill('#custom-view-name','审查视图');await page.locator('#save-view button').click();
  const custom=await page.locator('#analysis-view').inputValue();assert(custom.startsWith('custom-'));
  await page.reload();await page.waitForFunction(()=>window.graphDebug?.graph);assert(await page.locator('#analysis-view option').filter({hasText:'审查视图'}).count());
  passed('Custom view is persisted in the project');
  await page.selectOption('#analysis-view','overview');await page.click('#collapse');
  for(const algorithm of ['layered','stress','cluster']){
   await page.selectOption('#layout',algorithm);await page.click('#arrange');await page.waitForTimeout(400);
   await page.waitForFunction(()=>!window.graphDebug.layoutBusy);assert.equal(await page.locator('#layout').inputValue(),algorithm);
  }passed('Circular, layered and force-style layouts complete');
  await page.click('#record-start');await page.waitForFunction(()=>!document.querySelector('#record-stop').disabled);
  const control=await context.newPage();control.on('pageerror',e=>report.errors.push(e.message));await control.goto(base+'/');
  await control.waitForFunction(()=>document.querySelector('#operator').options.length>0);await control.selectOption('#capacity','1');await control.click('#new-run');
  await page.bringToFront();await page.waitForFunction(()=>window.graphDebug.view.machine.current==='waiting');
  const waiting=await (await page.request.get(base+'/api/stategraph')).json();
  assert(waiting.instances.length>0);assert.equal(waiting.instances.at(-1).observed.state,'waiting');
  passed('A real request without approval appears as a waiting instance');
  await control.bringToFront();await control.click('#approve');await control.locator('[data-action=resume]').first().click();
  await page.bringToFront();await page.waitForFunction(()=>window.graphDebug.view.machine.configurations.some(c=>Object.values(c.activities).includes('running')));
  await page.selectOption('#analysis-view','resources');await photo('04-running-and-waiting.png');
  const running=await (await page.request.get(base+'/api/stategraph')).json();
  assert(running.instances.some(i=>Object.values(i.observed.configuration.activities).includes('running')));
  await page.waitForFunction(()=>window.graphDebug.view.machine.current==='completed',{},{timeout:20000});
  await page.click('#record-stop');await page.waitForFunction(()=>!document.querySelector('#replay').hidden);
  const records=await (await page.request.get(base+'/api/recordings')).json(),record=await (await page.request.get(base+'/api/recordings/'+records.recordings[0].id)).json();
  assert(record.events.length>0);assert(record.commands.length>=3);assert.equal(record.final.machine.current,'completed');
  const exported=await (await page.request.get(base+'/api/stategraph/export')).json();
  assert.deepEqual(exported.instances.map(i=>i.observed.configuration),exported.runtime.machine.configurations);
  passed('Recording captures real wait, approval, resume, activities and commit; export shares instances',{events:record.events.length,commands:record.commands.length});
  await page.selectOption('#analysis-view','functions');await page.selectOption('#replay-grain','events');
  const options=await page.locator('#replay-events option').count();assert(options>5);
  let observedChanges=0,lastChange=0;
  for(let i=0;i<options;i++){
   await page.selectOption('#replay-events',{index:i});
   if((await page.locator('#change-rows').innerText()).trim()){observedChanges++;lastChange=i;}
  }
  assert(observedChanges>0);await page.selectOption('#replay-events',{index:lastChange});await photo('05-replay-values.png');passed('Replay presents explicit value/state changes',{stepsWithChanges:observedChanges});
  await page.click('#replay-live');await page.selectOption('#analysis-view','overview');await page.click('#collapse');await focus('flow.policy');
  await page.selectOption('#capture-mode','focused');await page.click('#record-start');await control.click('#approve');await page.waitForTimeout(300);await page.click('#record-stop');
  const list2=await (await page.request.get(base+'/api/recordings')).json(),focused=await (await page.request.get(base+'/api/recordings/'+list2.recordings[0].id)).json();
  assert.equal(focused.capture.mode,'focused');assert(focused.events.every(e=>focused.capture.nodes.includes(e.node)));
  passed('Focused recording keeps an explicit region and boundary');
  await page.click('#replay-live');await page.setViewportSize({width:900,height:760});await page.click('#fit');await photo('06-narrow.png');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));passed('Narrow layout has no horizontal page overflow');
  for(const width of [390,320]){
   await page.setViewportSize({width,height:900});await page.click('#fit');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await photo(`06-narrow-${width}.png`);passed(`Public toolbar has no horizontal overflow at ${width}px`);
  }
  report.build_id=(await (await page.request.get(base+'/api/view')).json()).manifest.build_id;
  assert.deepEqual(report.errors,[]);report.passed=true;
 }finally{await browser.close();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));}
}
main().catch(e=>{report.errors.push(e.stack);fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.error(e);process.exitCode=1;});
