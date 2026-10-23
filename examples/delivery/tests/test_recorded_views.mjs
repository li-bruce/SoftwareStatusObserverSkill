import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const folder=['skills/business-observer/assets/stategraph-viewer','static/graph','integrations/bo_view'].map(p=>path.join(root,p)).find(p=>fs.existsSync(p));
const urls=new Map();
function url(name){
  if(urls.has(name))return urls.get(name);
  let text=fs.readFileSync(path.join(folder,name),'utf8').replace(/from '\.\/([^']+)'/g,(_,file)=>`from '${url(file)}'`);
  const value='data:text/javascript;base64,'+Buffer.from(text).toString('base64');urls.set(name,value);return value;
}
const core=await import(url('graph-core.js')),layout=await import(url('layout.js')),analysis=await import(url('analysis.js')),replay=await import(url('recording.js'));
const view={
  model:{nodes:[
    {id:'flow',label:"Check",layer:'business',kind:'action'},
    {id:'check',label:"Validate",kind:'function',parent:'flow',capture:{in:{length:'number'},out:{passed:'boolean'}},source:{symbol:'check'}},
    {id:'lifecycle',kind:'function',label:"Phase",parent:'flow'},
    {id:'state.checking',kind:'state',layer:'state',value:'checking',label:"Checking",parent:'lifecycle'},
    {id:'state.done',kind:'state',layer:'state',value:'done',label:"Complete",parent:'lifecycle'},
  ],edges:[{id:'f',from:'flow',to:'check',type:'contains'}],graph_roots:['flow'],
  machine:{values:['checking','done'],labels:{checking:"Checking",done:"Complete"},transitions:[{source:'checking',dest:'done',trigger:'finish'}],
    execution:{parent:'flow',within:'checking',activities:[{id:'check'}],resources:[]}},
  presentation:{memberships:[{group:'flow',member:'state.checking',reason:"State used by this flow",evidence:'test declaration'}]}},
  manifest:{build_id:'b',bindings:{check:{path:'core.py',line:3,snippet:'def check():'}}},
  binding_status:{status:'current'},authority:{parameters:{attempt:'a',param_version:1},basis:{param_version:1}},machine:{current:'checking',configurations:[],journal:[]},
  health:{run_id:'p',attempted:0},events:[],historical:false
};
const members=analysis.sharedMemberships(view.model);
const options={memberships:members};
let g=core.layoutGraph(view,new Set(['flow','lifecycle','state.checking']),new Set(),new Map(),'latest','latest',options);
const ref=g.boxes.find(b=>b.node.referenceOf==='check');
assert.ok(ref,'state contains a reference to the same declared activity');
assert.deepEqual(core.sourceBinding(view,g.all,ref.id),view.manifest.bindings.check);
assert.equal(g.boxes.filter(b=>b.id==='check').length,1,'one canonical node');
let folded=core.layoutGraph(view,new Set(['flow','lifecycle']),new Set(),new Map(),'latest','latest',options);
assert.ok(!folded.byId.has(ref.id)&&folded.byId.has('check'),'folding reference group leaves canonical member');
const settings=layout.emptyLayout();layout.setAnnotation(settings,'check',{label:"Custom check"});
assert.equal(layout.displayName(ref.node,settings),"Custom check",'reference shares canonical annotation');
const states=analysis.profileFor('states');
g=core.layoutGraph(view,new Set(),new Set(),new Map(),'latest','latest',{
  ...options,match:(all,events,status)=>analysis.matchingNodes(all,view,events,states,status)});
assert.deepEqual(g.boxes.map(b=>b.id).sort(),['state.checking','state.done']);
assert.ok(g.edges.some(e=>e.type==='transition'),'deep states visible without opening business');
const hits=[{region:'outer',cx:0,cy:0,radius:100,border:true},{region:'inner',cx:0,cy:0,radius:40,border:true}];
assert.equal(layout.pickHit(hits,65,0).region,'outer');
assert.equal(layout.pickHit(hits,10,0).region,'inner');
assert.equal(layout.pickHit(hits,150,0),undefined);
hits.push({id:'node',cx:10,cy:0,r:5,x:5,y:-5,w:10,h:10});
assert.equal(layout.pickHit(hits,10,0).id,'node','glyph wins over circle body');
const start='2026-01-01T00:00:00Z',event=(seq,node,outputs,extra={})=>({
  id:'p:'+seq,seq,run_id:'p',attempt:'a',node,phase:'return',inputs:{},outputs,
  basis:{param_version:1},observed_at:`2026-01-01T00:00:0${seq}Z`,...extra});
const record={status:'stopped',id:'r',build_id:'b',started_at:start,ended_at:'2026-01-01T00:00:09Z',
  context:structuredClone(view),final:{...structuredClone(view),machine:{current:'done',configurations:[{attempt:'a',phase:'done',param_version:1,
    results:{future:true},qualification:{allowed:true},journal:[{seq:1,phase:'checking',after:{activities:{check:'running'},resources:{},join:{state:'waiting',pending:['check']}}}]}]}},
  events:[event(1,'flow',{revision:1,phase:'checking'}),event(2,'check',{passed:true})],commands:[],gaps:[]};
const items=replay.timeline(record),before=replay.frame(record,1,items);
assert.equal(before.events.length,1);assert.equal(before.machine.current,'checking');
assert.equal(before.machine.configurations[0].results,undefined);
assert.deepEqual(before.machine.configurations[0].qualification,{});
assert.equal(core.callValues({id:'check'},before.events).outputs.passed,undefined,'future return not visible');
assert.equal(replay.frame(record,items.length-1,items).machine.current,'done');
assert.equal(record.final.machine.configurations[0].phase,'done','replay never mutates original');
const a=event(1,'a',{}),b=event(2,'b',{},{depends:[{event:'p:1',type:'data'}]});
const edges=[{id:'e',type:'data',members:[{from:'a',to:'b',type:'data'}]},{id:'ref',type:'shared',members:[{from:'a',to:'b',type:'shared'}]}];
assert.deepEqual(replay.transferEdges(b,[a,b],edges,new Map()),['e']);
assert.deepEqual(replay.transferEdges({...b,depends:[]},[a,b],edges,new Map()),[],'sequence alone is not evidence');
assert.deepEqual(replay.transferEdges({...b,depends:[{event:'p:1',type:'guard'}]},[a,b],edges,new Map()),[],'a guard dependency cannot animate a data edge');
assert.deepEqual(replay.transferEdges(event(3,'flow',{revision:1}),[],[
  {id:'allocation',type:'resource',members:[{from:'slots',to:'check'}]}
],new Map(),{journal:[{seq:1,event:'start',activity:'check',after:{resources:{slots:{holders:['check']}}}}]}),['allocation']);
const changedParameter=structuredClone(record);
changedParameter.context.authority.parameters.limit_bytes=8192;
changedParameter.context.model.presentation.replay_parameters={limit_bytes:{node:'limit',direction:'out',field:'limit_bytes'}};
changedParameter.events=[event(1,'limit',{limit_bytes:64}),event(2,'unrelated',{limit_bytes:999})];
assert.equal(replay.frame(changedParameter,2).authority.parameters.limit_bytes,64,'only explicit parameter binding updates the replay header');
console.log('Recorded-view checks passed: state projection, shared identity, circle picking, replay boundary, evidence-only motion.');
const steps=await import(url('replay-steps.js'));
const projectStates={machine:{values:['pending','approved'],labels:{pending:'Awaiting review',approved:'Published'}}};
assert.equal(core.phaseLabel(projectStates,'pending'),'Awaiting review');
assert.equal(core.phaseLabel({machine:{values:['pending']}},'pending'),'pending','optional labels cannot crash live state display');
assert.equal(steps.boDisplayValue('pending',projectStates,{kind:'business',field:'Flow'}),'Awaiting review','business phase keeps project semantics');
assert.equal(steps.boDisplayValue('pending',projectStates,{kind:'state',field:'Activity'}),'Not started','activity uses activity semantics even with a colliding project state');
assert.equal(steps.boDisplayValue('pending',projectStates,{kind:'value',field:'state'}),'pending','raw captured values are not relabeled by enum coincidence');
assert.equal(steps.boDisplayValue('pending',projectStates,{kind:'value',field:'note'}),'pending');
assert.equal(steps.boDisplayValue(undefined,projectStates,{kind:'business'}),'Not recorded');
const detailed=structuredClone(record);
detailed.events=[event(1,'flow',{revision:1,phase:'checking'}),event(2,'check',{passed:false}),event(3,'check',{passed:true}),event(4,'check',{passed:false}),event(5,'check',{passed:true},{attempt:'b'})];
const raw=replay.timeline(detailed),all=new Map(view.model.nodes.map(n=>[n.id,n]));
const business=[{id:'flow',node:all.get('flow'),type:'business'}],functions=[{id:'check',node:all.get('check'),type:'function'}];
const businessSteps=steps.boStepPlan(detailed,raw,all,business),functionSteps=steps.boStepPlan(detailed,raw,all,functions);
assert.ok(businessSteps.length<functionSteps.length,'business steps omit internal value-only events');
assert.equal(steps.boStepPlan(detailed,raw,all,business,{mode:'events'}).length,raw.length,'raw facts remain available');
assert.equal(steps.boStepDetail(detailed,raw,2,1,all,functions).rows[0].after,false,'no future value');
const changes=steps.boStepDetail(detailed,raw,4,1,all,functions).rows;
assert.deepEqual(changes.map(r=>[r.before,r.after]),[[undefined,false],[false,true],[true,false]],'retain changes even when final value returns to original');
assert.equal(steps.boStepDetail(detailed,raw,5,4,all,functions).rows[0].before,undefined,'another attempt cannot inherit a previous value');
const baseline=structuredClone(detailed);baseline.context.events=[event(0,'check',{passed:true})];
assert.equal(steps.boStepDetail(baseline,replay.timeline(baseline),2,1,all,functions).rows[0].before,true,'captured initial context supplies prior value');
const separateCalls=structuredClone(detailed);separateCalls.events[1].call_id='call-1';separateCalls.events[2].call_id='call-2';
assert.equal(steps.boStepDetail(separateCalls,replay.timeline(separateCalls),3,2,all,functions).rows[0].before,undefined,'different invocations cannot share a local variable history');
assert.ok(!steps.boStepDetail(detailed,raw,4,1,all,business).rows.some(r=>r.field==='passed'),'business steps do not expose unrelated hidden-function parameter churn');
assert.equal(steps.boTransferLabel({type:'resource',members:[{from:'slots'}]},event(1,'flow',{revision:1}),{journal:[{seq:1,before:{resources:{slots:{available:2}}},after:{resources:{slots:{available:1}}}}]}),'Acquire · capacity 2 → 1');
assert.deepEqual(replay.transferEdges(event(3,'flow',{revision:2}),[],[{id:'allocation',type:'resource',members:[{from:'slots',to:'check'}]}],new Map(),{journal:[{seq:2,event:'finish',activity:'check',before:{resources:{slots:{holders:['check']}}},after:{resources:{slots:{holders:[]}}}}]}),['allocation'],'resource return has actual holder evidence');
layout.setAnnotation(settings,'check',{core:true,note:"Recheck commit conditions"});
const storage={getItem:()=>JSON.stringify(settings)};
const restored=layout.readLayout(storage,'key');
assert.equal(layout.annotationFor(restored.state,'check').core,true);
assert.equal(layout.annotationFor(restored.state,'check').note,"Recheck commit conditions");
console.log('Focused replay checks passed: view granularity, intermediate changes, attempt isolation, baseline values, typed payload and core marks.');

// A plain Python project can bind transaction snapshots without activity journals.
const exact=structuredClone(record);
delete exact.context.model.machine.execution;
exact.context.model.presentation.runtime_owner='flow';
exact.context.machine.shared_resources={printer:{available:1,holder:null}};
exact.context.machine.configurations=[{attempt:'a',phase:'waiting',activities:{check:'pending'}}];
exact.context.machine.current='waiting';
exact.events=[event(1,'flow',{}, {revision:7}),event(2,'check',{passed:true},{revision:8})];
exact.runtime_frames={schema:'stategraph-runtime-frames/v1',frames:[{
  event_id:'p:1',run_id:'p',build_id:'b',revision:7,
  machine:{current:'printing',state_revision:7,configurations:[{attempt:'a',phase:'printing',activities:{check:'succeeded'}}],
    shared_resources:{printer:{available:0,holder:'a'}}},
  authority:{state:'printing',parameters:{attempt:'a'},basis:{epoch:7}},
}]};
const exactItems=replay.timeline(exact),historical=replay.frame(exact,1,exactItems);
assert.equal(historical.machine.shared_resources.printer.available,0);
assert.equal(historical.machine.current,'printing');
assert.equal(historical.replay.runtime_exact,true);
const printer={id:'printer',kind:'data',execution_role:'resource'};
assert.equal(core.status(printer,historical,[],'latest'), 'blocked');
assert.ok(core.lines(printer,historical,[],'latest').some(row=>row.text==='available：0'));
assert.doesNotThrow(()=>core.lines({id:'check',execution_role:'activity'},historical,[],'latest',historical.machine.configurations[0]));
const missing=replay.frame(exact,2,exactItems);
assert.equal(missing.machine.current,null,'unbound steps cannot use an earlier or final state');
assert.equal(missing.replay.runtime_exact,false);
assert.ok(missing.replay.gaps.length);
const facts=steps.boFacts(exact,exactItems).changes[1];
assert.ok(facts.some(c=>c.node==='flow'&&c.before==='waiting'&&c.after==='printing'));
assert.ok(facts.some(c=>c.node==='check'&&c.before==='pending'&&c.after==='succeeded'));
assert.ok(facts.some(c=>c.node==='printer'&&c.field==='available'&&c.before===1&&c.after===0));
const swapped=structuredClone(exact);swapped.runtime_frames.frames[0].run_id='other';
assert.equal(replay.frame(swapped,1).machine.current,null,'different producer cannot borrow a snapshot');
console.log('Exact runtime frame checks passed: global resources, ordinary Python states, missing frames and identity.');
