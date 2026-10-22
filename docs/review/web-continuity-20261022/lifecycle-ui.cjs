const {chromium}=require(process.env.PLAYWRIGHT_MODULE),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const checks=[],errors=[],out=process.env.BO_UI_OUT,project=process.env.BO_PROJECT,base=process.env.BO_TEST_URL,mode=process.env.BO_LIFECYCLE;
const cli=(name,args)=>cp.spawnSync(process.env.BO_PYTHON,['-B','-X','utf8',path.join(process.env.BO_SKILL,'scripts',name),...args],{encoding:'utf8'});
function mark(id){checks.push({id,pass:true});}
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}),page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 const ready=async()=>{await page.goto(base+'/graph');await page.waitForFunction(()=>window.graphDebug?.graph&&!graphDebug.layoutBusy);};
 const click=async(id)=>{const loc=page.locator('#semantic [data-node-id="'+id+'"]');await loc.waitFor({state:'attached'});const p=await loc.evaluate(e=>({x:+e.dataset.screenX,y:+e.dataset.screenY}));await page.mouse.click(p.x,p.y);};
 try{
  if(mode==='design'){
   await ready();assert.equal(await page.evaluate(()=>graphDebug.view.stage),'design');
   await page.locator('#node-search').fill('archive_commit');await page.locator('#search-results button').first().click();
   await page.locator('#core-toggle').click();await page.locator('#annotate').click();await page.locator('#node-note').fill('立项讨论：关注提交前重查');
   await page.locator('#annotation-form button[type="submit"]').click();
   await page.waitForFunction(async()=>{const x=await (await fetch('/api/preferences')).json();return Object.values(x.entries).some(t=>t.includes('立项讨论'));});
   await page.waitForFunction(()=>document.querySelector('#layout-status').textContent==='视图已保存到项目');
   const settingsPath=path.join(project,'bo_stategraph/config/views/local.json');
   const saved=await (await page.request.get(base+'/api/preferences')).json();
   assert(Object.values(saved.entries).some(t=>t.includes('立项讨论')));
   assert(fs.existsSync(settingsPath),'Save acknowledgement must correspond to a real project file');
   fs.copyFileSync(settingsPath,path.join(out,'design-preferences.json'));
   await page.screenshot({path:path.join(out,'05-existing-design.png'),fullPage:true});mark('existing-project-design-annotation');
  }else if(mode==='archive'){
   await ready();assert.notEqual(await page.evaluate(()=>graphDebug.view.stage),'design');
   await page.locator('#node-search').fill('archive_commit');await page.locator('#search-results button').first().click();
   assert.equal(await page.locator('#semantic [data-node-id="archive_commit"]').getAttribute('data-core'),'true');
   await page.locator('#annotate').click();assert.equal(await page.locator('#node-note').inputValue(),'立项讨论：关注提交前重查');await page.locator('#close-detail').click();
   await page.screenshot({path:path.join(out,'06-design-to-runtime.png'),fullPage:true});mark('same-id-layout-key-annotation-survives-design-to-runtime');
   assert.equal(cli('bo_design.py',['focus','--root',project,'--nodes','archive_commit','approval_check','--label','核对提交时的实际审批依据']).status,0);
   await page.waitForFunction(()=>document.querySelector('#discussion-label').textContent.startsWith('核对提交'));
   await page.screenshot({path:path.join(out,'07-runtime-focus.png'),fullPage:true});mark('conversation-focus-in-live-runtime');
   assert.equal(cli('bo_web.py',['mode','hidden','--root',project]).status,0);
   const control=await browser.newPage();await control.goto(base+'/control');assert.equal(await control.locator('[data-bo-entry]').isVisible(),false);
   assert.equal((await page.request.get(base+'/api/view')).status(),200);mark('hide-entry-keeps-direct-graph');
   assert.equal(cli('bo_web.py',['mode','disabled','--root',project]).status,0);
   await page.waitForFunction(()=>document.querySelector('#connection').textContent==='调试 Web 已关闭');
   for(const route of ['/graph','/api/view','/api/source','/api/stategraph/export','/api/preferences','/api/recordings','/api/design','/pixi.min.js'])assert.equal((await page.request.get(base+route)).status(),404,route);
   const state=await (await page.request.get(base+'/api/state')).json();
   const projectId=state.projects[0].id;
   const changed=await page.request.post(base+'/api/size-limit',{data:{project_id:projectId,limit_bytes:9000}});assert.equal(changed.status(),200,await changed.text());
   const current=await (await page.request.get(base+'/api/state')).json();assert.equal(current.projects.find(p=>p.id===projectId).archive_limit_bytes,9000);
   await control.reload();await control.waitForFunction(()=>document.querySelector('#connection').textContent!=='连接中');
   await control.screenshot({path:path.join(out,'08-web-disabled-business.png'),fullPage:true});mark('web-closed-business-query-and-mutation-work');
   assert.equal(cli('bo_web.py',['mode','visible','--root',project]).status,0);await ready();
   assert.equal((await page.request.get(base+'/api/stategraph/export')).status(),200);mark('restore-web-and-export');
   await control.close();
  }else{
   await page.goto(base+'/control');await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('当前状态'));
   assert.equal(cli('bo_web.py',['mode','disabled','--root',project]).status,0);await page.reload();
   await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('当前状态'));
   assert.equal(await page.locator('[data-bo-entry]').isVisible(),false);
   assert.equal((await page.request.get(base+'/api/view')).status(),404);
   assert.equal((await page.request.get(base+'/api/app-state')).status(),200);
   const before=await (await page.request.get(base+'/api/app-state')).json();
   await page.locator('#content').fill('新的安全内容');await page.locator('#edit').click();
   await page.waitForFunction(async previous=>{const x=await (await fetch('/api/app-state')).json();return x.param_version===previous+1;},before.param_version);
   await page.screenshot({path:path.join(out,'09-delivery-without-graph.png'),fullPage:true});mark('delivery-control-independent-of-observer-http');
   assert.equal(cli('bo_web.py',['mode','visible','--root',project]).status,0);
  }
  assert.deepEqual(errors,[]);
 }finally{fs.writeFileSync(path.join(out,'lifecycle-'+mode+'.json'),JSON.stringify({checks,errors},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
