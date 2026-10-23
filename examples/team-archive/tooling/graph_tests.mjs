// Independent counterexamples: no final-state leakage and no future events.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const moduleUrls=new Map();
async function moduleUrl(name){
  if(moduleUrls.has(name))return moduleUrls.get(name);
  let source=await readFile(new URL('../static/graph/'+name,import.meta.url),'utf8');
  for(const match of [...source.matchAll(/from\s+["']\.\/([^"']+)["']/g)])source=source.replace(match[0],`from '${await moduleUrl(match[1])}'`);
  const url='data:text/javascript;base64,'+Buffer.from(source).toString('base64');
  moduleUrls.set(name,url);return url;
}
const {selectedConfiguration,selectedEvents,status,layoutGraph,callValues,sourceBinding,parameterSummary:sizeContext,lines}=await import(await moduleUrl('graph-core.js'));
const frame={seq:1,phase:'checking',after:{activities:{content_check:'running',index_check:'pending'},resources:{processing_slots:{capacity:1,available:0,holders:['content_check']}},join:{state:'waiting',pending:['content_check','index_check']}}};
const run={attempt:'r',param_version:1,phase:'interrupted',disposition:'interrupted',results:{future:true},qualification:{future:true},discarded:['index_check'],journal:[frame]};
const view={model:{nodes:[],edges:[],machine:{execution:{parent:'actual-parent'},values:[],transitions:[]},overview:[]},machine:{configurations:[run]},authority:{parameters:{attempt:'r'},basis:{param_version:1,epoch:1}},events:[
  {attempt:'r',seq:1,node:'content_check',outputs:{}},
  {attempt:'r',seq:2,node:'actual-parent',outputs:{revision:1}},
  {attempt:'r',seq:3,node:'later-approval',outputs:{allowed:true}},
  {attempt:'r',seq:4,node:'actual-parent',outputs:{revision:1}}
],binding_status:{status:'current'}};
const historical=selectedConfiguration(view,'latest','1');
assert.equal(historical.phase,'checking');
for(const field of ['results','qualification','disposition','stop_reason'])assert.equal(historical[field],undefined,field+' cannot borrow final state');
assert.equal(historical.discarded,undefined,'a frame without discard facts must remain unknown');
assert.equal(status({id:'content_check',execution_role:'activity'},view,[],'latest',historical),'active');
assert.deepEqual(selectedEvents(view,'latest','1').map(e=>e.seq),[1,2]);
assert.deepEqual(selectedEvents(view,'latest','2'),[]);
assert.equal(selectedConfiguration(view,'latest','latest'),run);
const staticView=structuredClone(view);
staticView.model.nodes=[
  {id:'root',kind:'action',layer:'business',label:'root'},
  {id:'child',kind:'function',parent:'root',label:'child',capture:{in:{content_version:'number'},out:{}}},
  {id:'other',kind:'action',layer:'business',label:'other'}];
staticView.model.graph_roots=['root','other'];
assert.equal(layoutGraph(staticView).boxes.length,2);
const opened=layoutGraph(staticView,new Set(['root','child']));
assert(opened.all.has('field:child:in:content_version'));
assert(opened.byId.has('root')&&opened.byId.has('other'));
assert.equal(opened.all.get('field:child:in:content_version').event_node,'child');
staticView.model.nodes.push({id:'state.checking',kind:'state',parent:'child',label:"Checking",value:'checking'});
staticView.model.machine.values=['checking'];staticView.model.machine.labels={checking:"Checking"};
const closedParent=layoutGraph(staticView,new Set(['child']));
assert.deepEqual(closedParent.boxes.map(b=>b.id),['root','other'],'saved inner expansion cannot bypass a collapsed outer parent');
assert.ok(closedParent.all.has('state.checking'),'all states remain searchable in the full model');
assert.ok(layoutGraph(staticView,new Set(['root','child'])).byId.has('state.checking'),'state appears in its actual nested owner');
const callEvents=[
  {node:'child',call_id:'a',inputs:{content_version:1},outputs:{}},
  {node:'child',call_id:'a',inputs:{length:3},outputs:{passed:true}}]
  .map(e=>({run_id:'session',attempt:'run',entity:'doc',build_id:'build',model_revision:'v1',basis:{param_version:1},...e}));
assert.deepEqual(callValues({id:'child'},callEvents),{inputs:{content_version:1,length:3},outputs:{passed:true}});
assert.deepEqual(callValues({id:'child'},[...callEvents,{node:'child',call_id:'b',inputs:{length:7},outputs:{}}]).inputs,{length:7});
for(const field of ['call_id','run_id','attempt','entity','build_id','model_revision']){
  const different={...callEvents[1],[field]:'different'};
  assert.deepEqual(callValues({id:'child'},[callEvents[0],different]).inputs,{length:3},field);
}
assert.deepEqual(callValues({id:'child'},[callEvents[0],{...callEvents[1],basis:{param_version:2}}]).inputs,{length:3});
assert.deepEqual(callValues({id:'child'},callEvents.map(e=>({...e,call_id:'run:child'}))).inputs,{length:3});
assert.deepEqual(callValues({id:'child'},callEvents.map(e=>({...e,run_id:undefined}))).inputs,{length:3});
staticView.manifest={bindings:{child:{path:'source.py',line:4}}};
assert.equal(sourceBinding(staticView,opened.all,'field:child:in:content_version').line,4);
const sizeView=structuredClone(view);
sizeView.model.nodes=[{id:'size_guard',kind:'decision',basis_fields:['param_version','epoch']},{id:'project_limit',kind:'data',basis_fields:['param_version','epoch']}];
sizeView.model.presentation={context_fields:[{key:'content_bytes',label:"Current body",unit:"bytes"},
  {key:'limit_bytes',label:"Current project limit",saved_label:"Limit at save",unit:"bytes"}]};
sizeView.authority.basis={param_version:1,epoch:2};
const sizeEvents=[{node:'size_guard',phase:'decision',basis:{param_version:1,epoch:1},inputs:{limit_bytes:8192},outputs:{allowed:true}}];
assert.equal(status({id:'field:size_guard:out:allowed',field:'allowed',direction:'out',event_node:'size_guard'},sizeView,sizeEvents,'latest'),'historical');
assert.equal(status({id:'size_guard',kind:'decision'},sizeView,sizeEvents,'latest'),'historical');
assert.equal(status({id:'project_limit',kind:'data'},sizeView,[{node:'project_limit',phase:'read',basis:{param_version:1,epoch:1},outputs:{limit_bytes:8192}}],'latest'),'historical');
sizeView.authority.parameters={limit_bytes:1,limit_revision:2,content_bytes:42};
const completedRun={phase:'completed',qualification:{size:{content_bytes:42,limit_bytes:8192,limit_revision:1}}};
assert.equal(sizeContext(sizeView,completedRun),'Current body 42 bytes · Current project limit 1 bytes');
assert.equal(sizeContext({...sizeView,historical:true,authority:{parameters:{content_bytes:42,limit_bytes:8192}}},completedRun),'Current body 42 bytes · Limit at save 8192 bytes');
assert.equal(sizeContext(sizeView,completedRun,'1'),'');
assert.equal(sizeContext({...sizeView,authority:{parameters:{}}},completedRun),'');
assert(lines({id:'size_guard',kind:'decision',summary:"UTF-8 body-size decision"},sizeView,sizeEvents,'latest',completedRun).some(row=>row.text.includes('Historical decision/read')));
console.log('Graph invariants passed: exact boundary, missing boundary, historical phase, no final disposition/results, stable folded IDs.');
