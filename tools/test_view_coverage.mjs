import fs from 'node:fs';
import assert from 'node:assert/strict';
// Deliberately retain non-English business labels: relation selection must
// depend on node identity/types rather than translated presentation strings.
const folder=new URL('../skills/business-observer/assets/stategraph-viewer/',import.meta.url),urls=new Map();
function url(name){if(urls.has(name))return urls.get(name);const text=fs.readFileSync(new URL(name,folder),'utf8').replace(/from '\.\/([^']+)'/g,(_,file)=>`from '${url(file)}'`);const result='data:text/javascript;base64,'+Buffer.from(text).toString('base64');urls.set(name,result);return result;}
const core=await import(url('graph-core.js')),analysis=await import(url('analysis.js')),layout=await import(url('layout.js'));
const steps=await import(url('replay-steps.js'));
const nodes=[
  {id:'upload',label:'提交文件',kind:'action',layer:'business',source:{path:'service.py',symbol:'upload'},capture:{in:{note:'string'},out:{state:'string'}}},
  {id:'notify',label:'通知审核人',kind:'effect',layer:'program',semantic_roles:['business'],source:{path:'service.py',symbol:'notify'},capture:{out:{count:'number'}}},
  {id:'review',label:'审核文件',kind:'action',layer:'business',source:{path:'service.py',symbol:'review'}},
  {id:'pending',kind:'state',layer:'state',value:'pending',label:'待审核'},
  {id:'approved',kind:'state',layer:'state',value:'approved',label:"Passed"},
  {id:'guard',kind:'decision',semantic_roles:['permission'],label:'核对审核人'},
  {id:'slot',kind:'resource',execution_role:'resource',label:'处理名额'},
  {id:'helper',kind:'function',origin:'python-ast',label:'保存消息'},
];
const edges=[
  {id:'send',from:'upload',to:'notify',type:'flow',label:'提交后通知'},
  {id:'await',from:'notify',to:'pending',type:'flow',label:'等待审核'},
  {id:'resume',from:'pending',to:'review',type:'flow',label:'开始审核'},
  {id:'permission',from:'guard',to:'review',type:'guard',label:'核对身份'},
  {id:'call',from:'notify',to:'helper',type:'flow',origin:'python-ast',label:'保存消息'},
  {id:'acquire',from:'slot',to:'helper',type:'resource',label:'占用名额'},
];
const event={id:'e1',node:'upload',phase:'return',seq:1,attempt:'run',call_id:'c1',run_id:'r1',entity:'file1',build_id:'build',model_revision:'1',basis:{param_version:1},inputs:{note:"Please review the attachment"},outputs:{state:'pending'},depends:[]};
const view={model:{nodes,edges,machine:{values:['pending','approved'],labels:{pending:'待审核',approved:'通过'},transitions:[{trigger:'approve',source:'pending',dest:'approved'}]},graph_roots:nodes.map(n=>n.id)},machine:{configurations:[],journal:[]},manifest:{bindings:{}},events:[event],authority:{parameters:{attempt:'run'},basis:{param_version:1}},binding_status:{status:'current'}};
function project(id,override={},expanded=new Set()){
  const profile={...analysis.profileFor(id),...override};
  const graph=core.layoutGraph(view,expanded,new Set(),new Map(),'latest','latest',{match:(all,events,status,relations)=>analysis.matchingNodes(all,view,events,profile,status,relations)});
  layout.refreshHierarchy(graph);
  return {graph,shown:layout.presentationGraph(graph,profile)};
}
const business=project('business');
assert.ok(business.shown.glyphs.has('notify'),'effect with business membership stays visible');
assert.ok(business.shown.edges.some(e=>e.from==='upload'&&e.to==='notify'));
assert.ok(business.graph.byId.get('pending').node.filter_context,'hidden state remains a labelled real endpoint');
assert.ok(!business.shown.edges.some(e=>e.from==='notify'&&e.to==='review'),'never invent a direct edge through a hidden state');
const states=project('states');
assert.equal(states.graph.all.has('state.pending'),false,'reuse authored state identity');
assert.ok(states.shown.edges.some(e=>e.from==='pending'&&e.to==='approved'&&e.type==='transition'));
const functions=project('functions',{},new Set(['upload','notify']));
assert.ok(functions.shown.glyphs.has('upload'),'business action remains a function in the function view');
assert.ok(functions.shown.glyphs.has('field:upload:in:note'));
assert.ok(functions.shown.edges.some(e=>e.from==='field:upload:in:note'&&e.to==='upload'));
assert.ok(core.lines(nodes[0],view,[event],'latest').some(row=>row.text?.includes("Please review the attachment")));
assert.equal(core.status(nodes[0],view,[event],'latest'),'ok');
const recording={context:{...view,events:[]},final:view};
const items=[{kind:'start'},{...event,kind:'probe'},{kind:'end'}];
const detail=steps.boStepDetail(recording,items,1,0,business.graph.all,business.graph.boxes);
assert.ok(detail.rows.some(row=>row.field==='note'),'business view replay keeps its own input changes');
assert.ok(steps.boStepPlan(recording,items,business.graph.all,business.graph.boxes).includes(1));
const parameters=project('data',{nodes:['data'],edges:['data']});
assert.ok(parameters.graph.byId.get('upload').node.filter_context);
assert.ok(parameters.shown.edges.some(e=>e.from==='field:upload:in:note'&&e.to==='upload'));
for(const id of ['permission','resources','data','runtime','blocked','shared','overview']){
  const {graph,shown}=project(id);
  for(const edge of shown.edges){
    assert.ok(graph.all.has(edge.from)&&graph.all.has(edge.to));
    for(const member of edge.members)assert.ok(graph.rawEdges.some(e=>e.id===member.id),'every relation has original evidence');
  }
}
const none=project('business',{edges:[]});assert.equal(none.shown.edges.length,0,'an explicit empty edge filter remains empty');
const depth=project('data',{nodes:['data'],edges:['data'],depth:1});
assert.ok(depth.shown.glyphs.has('field:upload:in:note'));
assert.ok(depth.shown.edges.some(e=>e.to==='upload'),'depth filtering retains the real boundary endpoint');
const foldedView={...view,model:{...view.model,nodes:[
  {id:'group',kind:'action',layer:'business',label:'审核'},
  {id:'inner',kind:'function',parent:'group',label:'等待审核'},
  {id:'external',kind:'function',label:'读取审核人'}],edges:[
  {id:'inner-call',from:'inner',to:'external',type:'flow',origin:'python-ast',label:'读取审核人'}],graph_roots:['group','external']},
  events:[{...event,node:'inner',phase:'wait'}]};
const blockedProfile=analysis.profileFor('blocked');
const folded=core.layoutGraph(foldedView,new Set(),new Set(),new Map(),'latest','latest',{
  match:(all,events,status,relations)=>analysis.matchingNodes(all,foldedView,events,blockedProfile,status,relations)});
assert.ok(folded.byId.get('external').node.filter_context);
assert.ok(folded.edges.some(e=>e.from==='group'&&e.to==='external'&&e.members.some(m=>m.from==='inner')),
  'folding the selected source cannot strand its boundary endpoint; preserve the actual inner source as evidence');
assert.ok(layout.compoundEdges(folded).length,'compound presentation must retain static edges without throwing');
for(const e of folded.edges)e.origin='source-ast';
assert.ok(layout.compoundEdges(folded).length,'language-neutral source edges survive compound presentation');
const rootless={...foldedView,model:{...foldedView.model}};delete rootless.model.graph_roots;
const rootlessGraph=core.layoutGraph(rootless,new Set(),new Set(),new Map(),'latest','latest');
assert.ok(rootlessGraph.byId.has('group')&&rootlessGraph.byId.has('external'),'a valid model without optional graph_roots remains usable');
const rootExpansion=new Set(rootlessGraph.boxes.filter(b=>!b.node.parent).map(b=>b.id));
assert.ok(core.layoutGraph(rootless,rootExpansion,new Set(),new Map(),'latest','latest').byId.has('inner'),'expand the visible roots without requiring an authored root list');
view.events.push({...event,id:'session-event',node:'notify',attempt:'session',scope:'application'});
assert.ok(core.selectedEvents(view,'latest').some(e=>e.id==='session-event'),'application events are not lost behind a selected task attempt');
view.events.push({...event,id:'other-attempt',attempt:'unrelated'});
assert.ok(!core.selectedEvents(view,'latest').some(e=>e.id==='other-attempt'),'ordinary events remain isolated by attempt');
assert.equal(project('blocked').shown.edges.length,0,'no invented blocked activity');
view.model.machine.execution={within:'pending',activities:[],resources:[{id:'slot'}]};
assert.ok(project('resources').shown.glyphs.has('pending'),'execution scope resolves the authored state identity');
assert.ok(analysis.sharedMemberships(view.model).some(m=>m.group==='pending'&&m.member==='slot'),'shared execution membership uses the same state identity');
console.log('PASS: business effects, real boundary endpoints, authored states, business parameters, all presets and explicit empty filters.');
