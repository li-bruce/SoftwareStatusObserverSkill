const { chromium } = require('C:/Users/Lvi_P/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root=path.resolve(__dirname,'..'), url=process.argv[2], report={checks:[],errors:[]};
const out=path.join(root,'review/round-03');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}), page=await browser.newPage({viewport:{width:1440,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));let originalPreferences;
 const passed=name=>report.checks.push(name);
 try{
  const initial=await (await page.request.get(url+'/api/view')).json();assert.equal(initial.binding_status.status,'current');passed('reachable HTTP and current loaded source binding');
  originalPreferences=await (await page.request.get(url+'/api/preferences')).json();
  await page.request.post(url+'/api/preferences',{data:{revision:originalPreferences.revision,positions:{},expanded:[],labels:{},notes:{},core:[],type:'all',edge_type:'all',search:''}});
  await page.goto(url);await page.waitForLoadState('networkidle');await page.locator('[data-node="approval"]').waitFor();
  assert.equal(await page.locator('[data-node]').count(),5);passed('initial view contains five high-level nodes');
  const recording=JSON.parse(fs.readFileSync(path.join(root,'data/demo.json'),'utf8')).recording;
  await page.locator('#record').selectOption(recording);
  await page.waitForFunction(()=>document.getElementById('health').textContent.includes('recorded sources'));
  const b=initial.snapshot.runs.find(r=>r.task_id==='任务-B'&&r.version===1);await page.locator('#run').selectOption(b.id);
  await page.locator('[data-node="approval"]').click();assert.match(await page.locator('#detail-title').innerText(),/审批/);passed('click selects actual node');
  await page.locator('#source-button').click();assert.match(await page.locator('#source').innerText(),/Workflow|_authorization/);passed('node resolves bound source snapshot');
  await page.locator('[data-node="approval"]').dblclick();await page.locator('[data-group="approval"]').waitFor();passed('double click expands a same-type region');
  const history=initial.history;
  const blocked=history.findIndex(f=>f.snapshot.runs.some(r=>r.id===b.id&&r.state==='blocked'));
  const stopping=history.findIndex(f=>f.snapshot.runs.some(r=>r.id===b.id&&r.state==='stopping'));
  assert(blocked>=0&&stopping>blocked);
  async function frame(index){await page.locator('#timeline').evaluate((el,index)=>{el.value=index;el.dispatchEvent(new Event('input',{bubbles:true}));},index);}
  await frame(blocked);assert.match(await page.locator('#status').innerText(),/等待有效审批/);await page.locator('[data-node="queue"]').click();assert.match(await page.locator('#event-values').innerText(),/no_valid_approval/);passed('locate actual authorization wait reason');
  const restored=history.findIndex((f,i)=>i>blocked&&f.snapshot.runs.some(r=>r.id===b.id&&r.state==='queued'));
  await frame(restored);assert.match(await page.locator('#status').innerText(),/等待机器/);passed('recover with preserved queue position');
  await frame(stopping);assert.match(await page.locator('#status').innerText(),/等待停止确认/);assert.match(await page.locator('#status').innerText(),new RegExp(b.id));passed('cancellation retains printer until stop confirmation');
  await frame(0);assert.match(await page.locator('#status').innerText(),/尚未创建/);assert.equal(await page.locator('#graph circle[fill="#16856c"]').count(),0);passed('early replay contains no future state or event markers');
  await frame(history.length-1);await page.locator('[data-node="approval"]').click();
  await page.locator('#alias').fill('审批验收批注');await page.locator('#note').fill('对应原节点身份');await page.locator('#core').check();await page.locator('#note').blur();
  await page.waitForFunction(()=>document.getElementById('save-status').textContent==='个人视图已保存');
  await page.reload();await page.waitForLoadState('networkidle');assert.match(await page.locator('[data-node="approval"]').textContent(),/审批验收批注/);passed('name annotation and core marker persist after reload');
  const before=await page.evaluate(()=>window.boReadOnlyState().positions);
  await page.locator('[data-node="approval"]').dblclick();
  // Ensure group expanded, then drag its boundary rather than a child node.
  if(await page.locator('[data-group="approval"]').count()===0)await page.locator('[data-node="approval"]').dblclick();
  const box=await page.locator('[data-group="approval"] > rect').boundingBox();
  await page.mouse.move(box.x+10,box.y+42);await page.mouse.down();await page.mouse.move(box.x+70,box.y+82,{steps:8});await page.mouse.up();
  await page.waitForFunction(()=>document.getElementById('save-status').textContent==='个人视图已保存');
  const after=await page.evaluate(()=>window.boReadOnlyState().positions);
  assert(after.approval.x!==before.approval.x);assert.equal(Math.round(after.approval.x-before.approval.x),Math.round(after['grant-match'].x-before['grant-match'].x));passed('group drag moves root and hidden descendants together');
  await page.locator('#search').fill('grant_matches');assert(await page.locator('[data-node]').count()>0);passed('search resolves folded function');
  await page.locator('#overview').click();await page.locator('#type').selectOption('state');assert(await page.locator('[data-node]').count()>=11);passed('state filter finds deep nodes without manual unfolding');
  await page.locator('#overview').click();
  const prefs=await (await page.request.get(url+'/api/preferences')).json();
  const conflict=await page.request.post(url+'/api/preferences',{data:{...prefs,revision:prefs.revision-1}});assert.equal(conflict.status(),409);passed('stale preference write rejected explicitly');
  await page.locator('#record').selectOption('live');await page.locator('#record-start').click();await page.locator('#record-stop').click();await page.waitForFunction(()=>document.getElementById('record-status').textContent.includes('已保存'));passed('record controls create explicit saved record');
  const final=await (await page.request.get(url+'/api/view')).json();assert.deepEqual(final.snapshot.effects,initial.snapshot.effects);passed('all graph interactions leave business effects unchanged');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:960});await page.locator('#overview').click();assert(await page.locator('#status').isVisible());const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert(!overflow,`body overflow ${width}`);await page.screenshot({path:path.join(out,`browser-${width}.png`),fullPage:true});passed(`real browser at width ${width}`);}
  assert.deepEqual(errors,[]);passed('no browser page errors');
 }catch(error){report.errors.push(String(error.stack));await page.screenshot({path:path.join(out,'browser-failure.png'),fullPage:true});}
 finally{if(originalPreferences){const current=await(await page.request.get(url+'/api/preferences')).json();await page.request.post(url+'/api/preferences',{data:{...originalPreferences,revision:current.revision}});}await browser.close();}
 report.valid=!report.errors.length;fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));process.exitCode=report.valid?0:1;
})().catch(e=>{console.error(e);process.exitCode=1;});
