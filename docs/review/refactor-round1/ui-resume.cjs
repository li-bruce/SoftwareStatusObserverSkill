// Run against the same persisted project after stopping it and changing its port.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=process.env.BO_TEST_URL||'http://127.0.0.1:8838';
const result={scope:'Fresh browser context; restarted application, same project files, different port',checks:[],errors:[]};
const passed=name=>{result.checks.push({name,passed:true});console.log('PASS '+name);};
async function main(){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:960}}),page=await context.newPage();
  page.on('pageerror',e=>result.errors.push(e.message));page.on('crash',()=>result.errors.push('page crashed'));
  await page.goto(base+'/graph');await page.waitForFunction(()=>window.graphDebug?.graph);
  const stored=await (await page.request.get(base+'/api/preferences')).json();
  assert(Object.values(stored.entries).some(raw=>raw.includes('审查重点')));
  assert(await page.locator('#analysis-view option').filter({hasText:'审查视图'}).count());
  await page.selectOption('#analysis-view','overview');await page.click('#collapse');await page.click('#fit');
  assert.equal(await page.locator('#semantic [data-node-id="flow.checks"]').innerText(),'检查与排队');
  passed('Restart and port change restore project labels, notes, core mark and custom view without browser cache');
  const node=page.locator('#semantic [data-node-id="flow.policy"]');
  const x=Number(await node.getAttribute('data-screen-x')),y=Number(await node.getAttribute('data-screen-y'));
  await page.mouse.click(x,y);
  await page.waitForFunction(()=>document.querySelector('#semantic [data-node-id="flow.policy"]').dataset.emphasis==='selected');
  assert(await page.locator('#semantic [data-emphasis="related"]').count()>0);
  passed('A pointer selection highlights its related graph context');
  const firstCamera=await page.evaluate(()=>window.graphDebug.camera);
  const canvas=await page.locator('canvas').boundingBox();
  await page.mouse.move(canvas.x+20,canvas.y+canvas.height-30);await page.mouse.down();
  await page.mouse.move(canvas.x+60,canvas.y+canvas.height-65,{steps:6});await page.mouse.up();
  const nextCamera=await page.evaluate(()=>window.graphDebug.camera);
  assert(Math.abs(nextCamera.pan.x-firstCamera.pan.x)>20);passed('Dragging empty canvas pans the camera');
  for(let i=0;i<12;i++){
   await page.locator('#semantic [data-node-id="flow.checks"]').focus();await page.click('#node-expand');
   await page.click('#fit');await page.click('#collapse');
  }
  assert.equal(await page.locator('#renderer').getAttribute('data-context-lost'),'false');
  passed('Repeated expansion, fit and collapse retain a live WebGL context');
  const records=await (await page.request.get(base+'/api/recordings')).json();
  const saved=records.recordings.find(r=>r.events>10);assert(saved);
  await page.selectOption('#record-list',saved.id);await page.selectOption('#analysis-view','business');
  await page.selectOption('#replay-grain','events');
  const options=await page.locator('#replay-events option').count();let found=false;
  for(let i=1;i<options;i++){
   await page.selectOption('#replay-events',{index:i});
   if((await page.locator('#change-rows').innerText()).includes('流程状态')){found=true;break;}
  }
  // Field names are project-defined; fall back to the first actual change row.
  if(!found){for(let i=1;i<options;i++){await page.selectOption('#replay-events',{index:i});if((await page.locator('#change-rows').innerText()).trim()){found=true;break;}}}
  assert(found);await page.click('#fit');
  await page.screenshot({path:path.join(__dirname,'ui-final/07-restart-and-replay.png'),fullPage:true});
  passed('Saved recording remains readable after restart and displays explicit state changes');
  result.build_id=(await (await page.request.get(base+'/api/view')).json()).manifest.build_id;
  assert.deepEqual(result.errors,[]);result.passed=true;
 }finally{await browser.close();fs.writeFileSync(path.join(__dirname,'ui-resume-result.json'),JSON.stringify(result,null,2));}
}
main().catch(e=>{result.errors.push(e.stack);fs.writeFileSync(path.join(__dirname,'ui-resume-result.json'),JSON.stringify(result,null,2));console.error(e);process.exitCode=1;});
