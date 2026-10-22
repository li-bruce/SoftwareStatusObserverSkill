const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const out=process.env.BO_UI_OUT,project=process.env.BO_DESIGN_PROJECT,base=process.env.BO_TEST_URL;
const checks=[],errors=[];
const cli=(script,args)=>cp.spawnSync(process.env.BO_PYTHON,['-B','-X','utf8',path.join(process.env.BO_SKILL,'scripts',script),...args],{encoding:'utf8'});
function record(id,details={}){checks.push({id,pass:true,...details});}
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')console.error('BROWSER',m.text());});
 try{
  await page.goto(base+'/graph');await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(()=>window.graphDebug?.graph?.boxes.length===4&&!graphDebug.layoutBusy);
  assert.equal(await page.locator('#record-start').isVisible(),false);
  assert.match(await page.locator('#connection').innerText(),/设计声明/);
  assert.equal(await page.locator('form[action*="design"],#design-answer,#design-confirm').count(),0);
  record('draft-no-fake-runtime-or-answer-form');
  const initial=fs.readFileSync(path.join(project,'discovery.json'),'utf8');
  const node=page.locator('#semantic [data-node-id="upload"]');
  let pos=await node.evaluate(e=>({x:+e.dataset.screenX,y:+e.dataset.screenY}));
  await page.mouse.click(pos.x,pos.y);await page.locator('#core-toggle').click();
  await page.locator('#annotate').click();await page.locator('#node-name').fill('源数据');
  await page.locator('#node-note').fill('检查输入版本');await page.locator('#annotation-form button[type="submit"]').click();
  await page.mouse.move(pos.x,pos.y);await page.mouse.down();await page.mouse.move(pos.x+56,pos.y+34,{steps:8});await page.mouse.up();
  await page.waitForFunction(async()=>{const d=await (await fetch('/api/preferences')).json();return Object.values(d.entries).some(x=>x.includes('源数据'));});
  await page.waitForFunction(()=>document.querySelector('#layout-status').textContent==='视图已保存到项目');
  const moved=await node.evaluate(e=>({x:+e.dataset.x,y:+e.dataset.y}));
  await page.screenshot({path:path.join(out,'01-draft.png'),fullPage:true});
  await page.reload();await page.waitForFunction(()=>window.graphDebug?.graph&&!graphDebug.layoutBusy);
  await page.waitForFunction(()=>document.querySelector('#semantic [data-node-id="upload"]')?.dataset.core==='true');
  const restored=await node.evaluate(e=>({x:+e.dataset.x,y:+e.dataset.y,fill:e.dataset.fill}));
  assert.equal(restored.x,moved.x);assert.equal(restored.y,moved.y);
  record('draft-layout-annotation-core-reload',restored);
  const focus=cli('bo_design.py',['focus','--root',project,'--decision','D1','--label','核对下载是否需要等待预览']);assert.equal(focus.status,0,focus.stderr+focus.stdout);
  await page.waitForFunction(()=>document.querySelector('#semantic [data-node-id="download"]')?.dataset.discussion==='true');
  assert.equal(fs.readFileSync(path.join(project,'discovery.json'),'utf8'),initial);
  await page.screenshot({path:path.join(out,'02-discussion.png'),fullPage:true});record('conversation-focus-read-only');
  const before=cli('requirements_dialogue.py',['check','--file',path.join(project,'discovery.json')]);assert.notEqual(before.status,0);
  // Simulated answer is written by the coding assistant, never submitted through the Web.
  const doc=JSON.parse(initial);doc.sources.push({id:'U2',kind:'user',text:'先允许下载，预览在后台继续。',locator:'合成对话第 2 轮，测试输入'});
  doc.decisions[0].status='resolved';doc.decisions[0].resolution={kind:'user_answer',text:'先允许下载，预览在后台继续。',source_refs:['U2']};
  doc.networks[0].edges.at(-1).relation='data';doc.networks[0].edges.at(-1).label='预览可稍后查看';
  fs.writeFileSync(path.join(project,'discovery.json'),JSON.stringify(doc,null,2));
  await page.waitForFunction(()=>graphDebug.view.model.edges.some(e=>e.label==='预览可稍后查看'));
  await page.waitForFunction(()=>document.querySelector('#discussion-label').textContent==='讨论范围待更新');
  const after=cli('requirements_dialogue.py',['check','--file',path.join(project,'discovery.json')]);assert.equal(after.status,0,after.stdout);
  fs.writeFileSync(path.join(out,'dialogue-gates.json'),JSON.stringify({before:{code:before.status,result:JSON.parse(before.stdout)},after:{code:after.status,result:JSON.parse(after.stdout)}},null,2));
  assert.equal(cli('bo_design.py',['focus','--root',project,'--nodes','validate','download','--label','格式通过即可下载；预览继续生成']).status,0);
  await page.waitForFunction(()=>document.querySelector('#discussion-label').textContent.startsWith('格式通过'));
  await page.screenshot({path:path.join(out,'03-chat-updated-graph.png'),fullPage:true});record('chat-change-live-graph-and-existing-gate');
  await page.locator('#discussion-clear').click();await page.locator('#fit').click();
  await page.setViewportSize({width:760,height:820});await page.locator('#fit').click();
  await page.screenshot({path:path.join(out,'04-narrow.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);record('narrow-layout');
  assert.equal(cli('bo_web.py',['mode','disabled','--root',project]).status,0);
  await page.waitForFunction(()=>document.querySelector('#connection').textContent==='调试 Web 已关闭');
  assert.equal(await page.evaluate(()=>graphDebug.graph),null);
  assert.equal((await page.request.get(base+'/api/design')).status(),404);
  assert.equal((await page.request.post(base+'/api/design/answer',{data:{}})).status(),404);
  assert.equal(cli('bo_web.py',['mode','visible','--root',project]).status,0);
  await page.reload();await page.waitForFunction(()=>window.graphDebug?.graph&&!graphDebug.layoutBusy);
  assert.equal((await page.request.post(base+'/api/design/answer',{data:{}})).status(),405);
  record('web-close-restore-with-no-answer-route');
  assert.deepEqual(errors,[]);
 }finally{
  fs.writeFileSync(path.join(out,'design-ui-result.json'),JSON.stringify({checks,errors},null,2));await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
