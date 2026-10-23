// Execute the shipped DOM handlers. HTTP is a controlled boundary here; server
// permissions/effects are verified separately by the existing SQLite scenarios.
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {BOProbe} from '../observer_runtime/bo_observer/adapters/javascript/bo_runtime.mjs';
const require=createRequire(new URL('../../multilanguage/package.json',import.meta.url));
const {JSDOM}=require('jsdom');
const input=JSON.parse(readFileSync(0,'utf8')),runs=[];
for(const mode of ['on','off','fault']) {
  const dom=new JSDOM(readFileSync(new URL('../static/app.html',import.meta.url),'utf8'),{runScripts:'outside-only',url:'http://localhost'});
  const w=dom.window,events=[],requests=[];
  w.TextEncoder=TextEncoder;w.setInterval=()=>0;
  const snapshot=structuredClone(input.snapshot);
  w.fetch=async(url,options={})=>{
    if(options.method==='POST') {const data=JSON.parse(options.body);requests.push({action:url.slice(5),data});return {ok:true,json:async()=>({ok:true})};}
    return {ok:true,json:async()=>snapshot};
  };
  const probe=new BOProbe({project:input.project,buildId:input.build_id,enabled:mode!=='off',sink:mode==='fault'?()=>{throw Error('collector offline')}:e=>events.push(e)});
  w.bo_observe=(node,phase,values)=>probe.record(node,phase,()=>values,{entity:'browser',attempt:'browser',scope:'application'});
  w.eval(readFileSync(new URL('../static/app.js',import.meta.url),'utf8'));
  const settle=()=>new Promise(r=>setTimeout(r,20));await settle();
  for(const id of ['title','size-limit'])w.document.getElementById(id).dispatchEvent(new w.Event('input',{bubbles:true}));
  w.document.getElementById('size-limit').value='1.5';
  w.document.getElementById('limit-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();
  assert.equal(requests.length,0,'fractional size must not be sent');
  const invalid=events.filter(e=>e.node==='ui.validate');
  if(mode==='on')assert.equal(invalid.at(-1).outputs.valid,false);
  w.document.getElementById('size-limit').value='4096';
  w.document.getElementById('limit-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();
  w.document.getElementById('edit-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();
  for(const id of ['move','new-run','approve']){w.document.getElementById(id).click();await settle();}
  for(const action of ['resume','cancel','revoke']) {
    const button=w.document.createElement('button');button.dataset.action=action;button.dataset.id='case-id';w.document.body.append(button);button.click();await settle();
  }
  await probe.flush();
  assert.deepEqual(requests.map(r=>r.action),['size-limit','edit','move','run','approve','resume','cancel','revoke']);
  assert.equal(requests[0].data.limit_bytes,4096);
  if(mode==='on') {
    assert.equal(events.filter(e=>e.node==='ui.command').length,requests.length);
    for(let i=0;i<requests.length;i++)assert.equal(events.filter(e=>e.node==='ui.command')[i].inputs.action,requests[i].action);
  } else assert.equal(events.length,0);
  runs.push({case:'ui_actions',mode,events,observations:{actions:requests.map(r=>r.action),limit:requests[0].data.limit_bytes,invalid_blocked:true},health:{errors:probe.bo_errors,dropped:probe.bo_dropped}});
  w.close();
}
process.stdout.write(JSON.stringify(runs));
