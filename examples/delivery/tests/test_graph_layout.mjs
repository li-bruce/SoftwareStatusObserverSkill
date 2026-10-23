import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {layoutGraph,selectedEvents,selectedConfiguration,sourceBinding,callValues,nodeTypes,nodeType} from '../integrations/bo_view/graph-core.js';
import {emptyLayout,layoutKey,readLayout,writeLayout,placeIncremental,setPosition,togglePin,calculateLayout,applyLayout,GraphGesture,annotationFor,displayName,setAnnotation,pickHit,searchNodes,ancestorsToReveal,hierarchyOf,hierarchyRegions,selectionContext,nodeCenter,compoundEdges,edgePorts,relationStyles,settleExpansion,hasSelfRelation,presentationGraph,emptyFilters,cleanFilters,renderRevision} from '../integrations/bo_view/layout.js';
const view=JSON.parse(fs.readFileSync(new URL('../scratch/graph-fixture.json',import.meta.url),'utf8'));
const expanded=new Set(['flow.checks','flow.commit','checksum']);
const graph=layoutGraph(view,expanded);
assert.ok(graph.byId.has('flow.checks')&&graph.byId.has('checksum')&&graph.byId.has('state.checking'));
assert.ok(graph.byId.has('field:checksum:out:checksum'),'typed return value is a graph node');
assert.ok(graph.edges.some(e=>e.type==='contains'&&e.to==='state.checking'));
assert.ok(graph.edges.some(e=>e.type==='transition'&&e.from==='state.checking'));
assert.ok(graph.edges.some(e=>e.type==='transition'&&e.event==='publish'&&e.observed),'actual lifecycle transitions join the same graph');
assert.ok(graph.edges.some(e=>e.from==='checksum'&&e.to==='field:checksum:out:checksum'));
const pairTypes=new Set(graph.edges.filter(e=>e.from==='checksum').map(e=>e.type));
assert.ok(pairTypes.has('data')&&pairTypes.has('join'),'distinct relations must not merge');
const wait=view.machine.configurations[0].journal.find(e=>e.event==='wait');
const history=layoutGraph(view,expanded,new Set(),new Map(),'latest',String(wait.seq));
assert.ok(history.boxes.filter(b=>b.type==='state').every(b=>b.state==='declared'),'an activity-only frame cannot claim a later lifecycle state');
assert.ok(history.edges.filter(e=>e.type==='transition').every(e=>!e.observed),'future transitions cannot light up a past frame');
const exactFrame=view.events.find(e=>e.node==='flow.checks'&&e.outputs.revision===wait.seq);
assert.ok(exactFrame);
const renamed=structuredClone(view);renamed.model.machine.execution.parent='custom.checks';
renamed.machine.configurations[0].results={future:'must not appear'};
renamed.machine.configurations[0].disposition='interrupted';
renamed.machine.configurations[0].qualification={allowed:true};
const historicalConfiguration=selectedConfiguration(renamed,'latest',String(wait.seq));
assert.equal(historicalConfiguration.results,undefined);
assert.equal(historicalConfiguration.disposition,undefined);
assert.equal(historicalConfiguration.qualification,undefined);
renamed.events=renamed.events.map(e=>e.node==='flow.checks'?{...e,node:'custom.checks'}:e);
const earlyEvents=selectedEvents(renamed,'latest',String(wait.seq));
renamed.events.push({...exactFrame,node:'permission',seq:10000,id:'later-rule',outputs:{allowed:false}});
renamed.events.push({...exactFrame,node:'custom.checks',seq:10001,id:'same-revision-later'});
assert.deepEqual(selectedEvents(renamed,'latest',String(wait.seq)),earlyEvents,'a later reevaluation cannot leak into an earlier frame with the same revision');
renamed.events=renamed.events.filter(e=>e.node!=='custom.checks'||e.outputs.revision!==wait.seq);
assert.deepEqual(selectedEvents(renamed,'latest',String(wait.seq)),[],'missing exact frame evidence remains unknown');
assert.equal(sourceBinding(view,graph.all,'field:checksum:out:checksum'),view.manifest.bindings.checksum,'parameter source is its captured function');
assert.equal(sourceBinding(view,graph.all,'missing'),undefined);
const callIdentity={node:'fn',call_id:'c1',run_id:'r1',attempt:'a1',entity:'d1',build_id:'b1',model_revision:'m1',basis:{param_version:1}};
const valuesEvents=[{...callIdentity,inputs:{version:1},outputs:{}},{...callIdentity,inputs:{length:3},outputs:{passed:true}}];
assert.deepEqual(callValues({id:'fn'},valuesEvents),{inputs:{version:1,length:3},outputs:{passed:true}});
for(const key of ['call_id','run_id','attempt','entity','build_id','model_revision']){
  const next={...callIdentity,[key]:'different',inputs:{length:5},outputs:{}};
  assert.deepEqual(callValues({id:'fn'},[...valuesEvents,next]),{inputs:{length:5},outputs:{}},`${key} must isolate call values`);
}
const legacy=valuesEvents.map(e=>({...e,call_id:'a1:fn'}));
assert.deepEqual(callValues({id:'fn'},legacy),{inputs:{length:3},outputs:{passed:true}},'legacy repeated call IDs do not justify merged values');

const state=emptyLayout();placeIncremental(graph,state);
const collapsedSearch=layoutGraph(view,new Set());
assert.deepEqual(collapsedSearch.boxes.map(b=>b.id),view.model.graph_roots,'overview contains only explicitly declared top-level nodes');
assert.ok(collapsedSearch.all.has('state.checking'),'folding does not remove state data');
setAnnotation(state,'checksum',{label:"Check file content",note:"Content check before archiving"});
assert.equal(searchNodes(collapsedSearch.all,state,"before archiving")[0].node.id,'checksum');
assert.equal(searchNodes(collapsedSearch.all,state,"Check file")[0].node.id,'checksum');
assert.ok(searchNodes(collapsedSearch.all,state,'checksum').some(r=>r.node.id==='field:checksum:out:checksum'));
assert.deepEqual(searchNodes(collapsedSearch.all,state,'   '),[]);
const reveal=new Set(['workers']),savedSearchPositions=JSON.stringify(state.positions);
for(const id of ancestorsToReveal(collapsedSearch.all,'field:checksum:out:checksum'))reveal.add(id);
const found=layoutGraph(view,reveal);placeIncremental(found,state);
assert.ok(found.byId.has('field:checksum:out:checksum'));
assert.ok(reveal.has('workers'),'search keeps previously expanded regions');
for(const [id,p] of Object.entries(JSON.parse(savedSearchPositions)))assert.deepEqual(state.positions[id],p,'search preserves dragged positions');
assert.deepEqual(ancestorsToReveal(new Map([['a',{parent:'b'}],['b',{parent:'a'}]]),'a'),['b'],'invalid parent cycles terminate');
setAnnotation(state,'checksum',{});
const hitA={id:'business',x:0,y:0,w:190,h:140,cx:95,cy:31,r:35};
const hitB={id:'function',x:40,y:20,w:190,h:135,cx:135,cy:51,r:30};
const handle={expand:'business',x:122,y:17,w:24,h:26};
assert.equal(pickHit([hitA,hitB],95,31).id,'business','a later label rectangle cannot steal a glyph drag');
assert.equal(pickHit([hitA,hitB],130,47).id,'function','nearby overlapping glyphs select the nearest center');
assert.equal(pickHit([hitA,handle],135,20).expand,'business','expansion handle remains clickable');
assert.equal(pickHit([hitA],95,105).id,'business','node labels remain selectable');
assert.equal(pickHit([hitA,hitB],400,300),undefined,'background stays available for panning');
const gesture=new GraphGesture(),original=graph.byId.get('checksum');
gesture.start({pointerId:7,x:100,y:90},{node:original,pan:{x:20,y:30},scale:.5});
assert.equal(gesture.move({pointerId:8,x:250,y:190}),null,'a second pointer must not move the first drag');
const move=gesture.move({pointerId:7,x:140,y:120});
assert.equal(move.kind,'node');assert.equal(move.x,original.x+80);assert.equal(move.y,original.y+60);
setPosition(graph,state,move.id,move.x,move.y);gesture.end(7);togglePin(graph,state,'checksum');
const pinned={...state.positions.checksum};
const snapshot=JSON.stringify(state.positions);
const refresh=layoutGraph({...view,manifest:{...view.manifest,build_id:'next-build'}},expanded);
placeIncremental(refresh,state);assert.equal(JSON.stringify(state.positions),snapshot,'runtime or build refresh preserves stable node coordinates');
const further=new Set([...expanded,'workers']),more=layoutGraph(view,further);
placeIncremental(more,state);
for(const [id,p] of Object.entries(JSON.parse(snapshot)))assert.deepEqual(state.positions[id],p,'expansion cannot move an existing node');
assert.ok(more.byId.has('execution.init'));
const folded=layoutGraph(view,new Set());placeIncremental(folded,state);
const unfolded=layoutGraph(view,further);placeIncremental(unfolded,state);
assert.deepEqual(state.positions.checksum,pinned,'collapse and reopen preserve a dragged pin');

const memory=new Map(),storage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
state.expanded=[];state.camera={x:-200,y:140,scale:.8};
assert.ok(writeLayout(storage,layoutKey(view.model),state));
const restored=readLayout(storage,layoutKey(view.model));
assert.equal(restored.restored,true);assert.deepEqual(restored.state.expanded,[],'an intentionally folded graph stays folded');
assert.deepEqual(restored.state.positions.checksum,pinned);assert.deepEqual(restored.state.camera,state.camera);
assert.equal(layoutKey({...view.model,revision:'next'}),layoutKey(view.model));
assert.notEqual(layoutKey({...view.model,presentation:{layout_id:'another-project'}}),layoutKey(view.model));
memory.set('broken','{');assert.equal(readLayout(storage,'broken').restored,false);
assert.equal(writeLayout({setItem(){throw Error('quota');}},'full',state),false);

// Personal wording stays separate from source IDs, runtime facts and generated labels.
const originalModel=JSON.stringify(view.model),originalEvents=JSON.stringify(view.events);
for(const id of ['flow.checks','checksum','field:checksum:out:checksum','state.checking']){
  setAnnotation(state,id,{label:"My label for "+id,note:"Check input version\nRetain original result"});
}
state.expanded=['flow.checks','checksum','workers'];state.focus='field:checksum:out:checksum';
const annotatedPositions=JSON.stringify(state.positions);
assert.ok(writeLayout(storage,layoutKey(view.model),state));
const personal=readLayout(storage,layoutKey(view.model)).state;
assert.deepEqual(personal.annotations,state.annotations);
assert.equal(personal.focus,'field:checksum:out:checksum');
assert.deepEqual(personal.expanded,['flow.checks','checksum','workers']);
assert.equal(JSON.stringify(personal.positions),annotatedPositions,'annotation persistence retains dragged positions and pins');
const hiddenBranch=layoutGraph(view,new Set(['checksum','workers']));placeIncremental(hiddenBranch,personal);
assert.ok(!hiddenBranch.byId.has('checksum'),'folding a parent hides its expanded descendants');
const reopenedBranch=layoutGraph(view,new Set(personal.expanded));placeIncremental(reopenedBranch,personal);
assert.ok(reopenedBranch.byId.has('field:checksum:out:checksum'),'reopening the parent restores deeper expansion');
assert.equal(displayName(reopenedBranch.byId.get('checksum').node,personal),'My label for checksum');
assert.equal(displayName({...reopenedBranch.byId.get('checksum').node,label:"New generated label"},personal),'My label for checksum','regeneration cannot overwrite a user label');
setAnnotation(personal,'checksum',{...annotationFor(personal,'checksum'),label:''});
assert.equal(displayName({...reopenedBranch.byId.get('checksum').node,label:"New generated label"},personal),"New generated label");
assert.equal(annotationFor(personal,'checksum').note,"Check input version\nRetain original result",'restore original name keeps the note');
setAnnotation(personal,'checksum',{label:'',note:''});
assert.ok(!personal.annotations.checksum);
setAnnotation(personal,'__proto__',{label:"Safe ID",note:'<script>text only</script>'});
assert.equal(Object.getPrototypeOf(personal.annotations),null);
assert.equal(annotationFor(personal,'__proto__').label,"Safe ID");
setAnnotation(personal,'limits',{label:"x".repeat(100),note:"n".repeat(600)});
assert.equal(annotationFor(personal,'limits').label.length,80);assert.equal(annotationFor(personal,'limits').note.length,500);
memory.set('old',JSON.stringify({schema:2,positions:{checksum:pinned},expanded:['flow.checks'],camera:state.camera}));
const old=readLayout(storage,'old').state;
assert.equal(Object.keys(old.annotations).length,0);assert.deepEqual(old.positions.checksum,pinned,'v0.2 layout upgrades without losing positions');
memory.set('invalid-note',JSON.stringify({schema:2,annotations:{checksum:{label:42,note:{}}},focus:42}));
const invalid=readLayout(storage,'invalid-note').state;
assert.equal(Object.keys(invalid.annotations).length,0);assert.equal(invalid.focus,null);
assert.equal(JSON.stringify(view.model),originalModel);assert.equal(JSON.stringify(view.events),originalEvents);
gesture.start({pointerId:9,x:20,y:30},{pan:{x:4,y:5},scale:.7});
assert.deepEqual(gesture.move({pointerId:9,x:40,y:60}),{kind:'pan',x:24,y:35});
assert.equal(gesture.end(9).moved,true);assert.equal(gesture.move({pointerId:9,x:50,y:70}),null);

// Run the shipped ELK library, not an algorithm stub. JSON crosses the VM realm.
const sandbox={module:{exports:{}},console,setTimeout,clearTimeout};sandbox.exports=sandbox.module.exports;
vm.createContext(sandbox);vm.runInContext('global = this;',sandbox);
vm.runInContext(fs.readFileSync(new URL('../observer_generated/static/elk.bundled.js',import.meta.url),'utf8'),sandbox);
vm.runInContext('elk = new module.exports();',sandbox);
const elk={layout:input=>{sandbox.inputJson=JSON.stringify(input);return vm.runInContext('elk.layout(JSON.parse(inputJson))',sandbox);}};
for(const algorithm of ['cluster','layered','stress']){
  const result=await calculateLayout(elk,unfolded,state,algorithm);
  assert.deepEqual(result.checksum,pinned,algorithm+' must respect an exact user pin');
  assert.ok(Object.values(result).every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
  assert.ok(unfolded.boxes.some(b=>!result[b.id].pinned&&(b.x!==result[b.id].x||b.y!==result[b.id].y)));
  applyLayout(unfolded,state,result);
  for(let i=0;i<unfolded.boxes.length;i++)for(let j=i+1;j<unfolded.boxes.length;j++){
    const a=unfolded.boxes[i],b=unfolded.boxes[j],visible=presentationGraph(unfolded).glyphs;
    if(!visible.has(a.id)||!visible.has(b.id))continue;
    assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y,algorithm+' must separate node label bounds: '+a.id+' / '+b.id);
  }
}
// A two-level hierarchy must stay spatially distinct without pins. Foreign
// branches stay outside its regions; nested bounds include their own children.
const clustered=layoutGraph(view,new Set(['flow.checks','checksum']));
const clean=emptyLayout();
applyLayout(clustered,clean,await calculateLayout(elk,clustered,clean,'cluster'));
const regions=hierarchyRegions(clustered),outer=regions.find(r=>r.id==='flow.checks'),inner=regions.find(r=>r.id==='checksum');
assert.ok(outer&&inner&&inner.depth>outer.depth);
assert.ok(Math.hypot(inner.cx-outer.cx,inner.cy-outer.cy)+inner.radius<=outer.radius,'nested circle is contained in its parent');
const checkBranch=new Set(outer.ids);
for(const b of clustered.boxes.filter(b=>!checkBranch.has(b.id)))assert.ok(b.x+b.w<=outer.x||b.x>=outer.x+outer.w||b.y+b.h<=outer.y||b.y>=outer.y+outer.h,'unrelated root stays outside a packed branch');
const context=selectionContext(clustered,'field:checksum:out:checksum');
assert.ok(context.active&&context.nodes.has('checksum')&&context.regions.has('flow.checks')&&context.regions.has('checksum'));
assert.ok(!context.nodes.has('flow.wait'),'selection does not recursively highlight the entire graph');
assert.equal(selectionContext(clustered,'not-visible').active,false);
assert.equal(emptyLayout().algorithm,'cluster');
assert.equal(hierarchyOf(clustered).depths.get('field:checksum:out:checksum'),2);
const savedCluster=JSON.stringify(clean.positions);
placeIncremental(clustered,clean);
assert.equal(JSON.stringify(clean.positions),savedCluster,'polling never reruns clustering');
togglePin(clustered,clean,'flow.checks');
const pinnedParent={...clean.positions['flow.checks']};
applyLayout(clustered,clean,await calculateLayout(elk,clustered,clean,'cluster'));
assert.deepEqual(clean.positions['flow.checks'],pinnedParent);
const pinnedRegion=hierarchyRegions(clustered).find(r=>r.id==='flow.checks');
for(const b of clustered.boxes.filter(b=>!checkBranch.has(b.id)))assert.ok(b.x+b.w<=pinnedRegion.x||b.x>=pinnedRegion.x+pinnedRegion.w||b.y+b.h<=pinnedRegion.y||b.y>=pinnedRegion.y+pinnedRegion.h,'a free root cannot land inside a pinned branch');
setPosition(clustered,clean,'field:checksum:out:checksum',outer.x+outer.w+500,outer.y-100);
assert.notDeepEqual(hierarchyRegions(clustered),regions,'regions follow real drag coordinates');
const cycle={boxes:[{id:'a',node:{parent:'b'}},{id:'b',node:{parent:'a'}}],byId:new Map([['a',{}],['b',{}]]),all:new Map([['a',{parent:'b'}],['b',{parent:'a'}]])};
assert.equal(hierarchyOf(cycle).roots.length,2,'invalid parent cycles cannot hang layout');
// Circular closures enclose labels and subgroups; moving the core moves all of them.
function checkCircles(subject){
  const list=hierarchyRegions(subject);
  for(const region of list){
    assert.ok(Number.isFinite(region.radius)&&region.radius>0);
    for(const id of region.ids){
      const b=subject.byId.get(id);
      if(list.some(r=>r.id===id&&!r.self))continue;
      for(const p of [{x:b.x,y:b.y},{x:b.x+b.w,y:b.y},{x:b.x+b.w,y:b.y+b.h},{x:b.x,y:b.y+b.h}])
        assert.ok(Math.hypot(p.x-region.cx,p.y-region.cy)<region.radius,'circle contains the entire node label');
    }
    for(const child of list.filter(r=>r.id!==region.id&&region.ids.includes(r.id)))
      assert.ok(Math.hypot(child.cx-region.cx,child.cy-region.cy)+child.radius<=region.radius,'outer circle contains the entire nested circle');
  }
}
checkCircles(clustered);
for(const y of [0,3,500]){
  const boxes=Array.from({length:7},(_,i)=>({id:String(i),x:i*190,y:i===3?y:0,w:115,h:66,node:{parent:i?'0':undefined}}));
  checkCircles({boxes,byId:new Map(boxes.map(b=>[b.id,b])),all:new Map(boxes.map(b=>[b.id,b.node]))});
}
// Moving a collapsed core must move stored children, including deeper levels.
const moving=layoutGraph(view,new Set()),moveState=structuredClone(clean);
placeIncremental(moving,moveState);
const beforeMove=structuredClone(moveState.positions),owner=moving.byId.get('flow.checks');
setPosition(moving,moveState,owner.id,owner.x+137,owner.y-91);
for(const [id,p] of Object.entries(beforeMove)){
  const carried=id===owner.id||ancestorsToReveal(moving.all,id).includes(owner.id),next=moveState.positions[id];
  assert.ok(Math.abs(next.x-p.x-(carried?137:0))<1e-8&&Math.abs(next.y-p.y-(carried?-91:0))<1e-8,'drag carries exactly its full subtree');
  assert.equal(next.pinned,p.pinned,'drag keeps pin preferences');
}
assert.ok(writeLayout(storage,'group-move',moveState));
const movedAgain=readLayout(storage,'group-move').state;
const reopened=layoutGraph(view,new Set(['flow.checks','checksum']));
placeIncremental(reopened,movedAgain);
for(const b of reopened.boxes)assert.deepEqual({x:b.x,y:b.y},{x:moveState.positions[b.id].x,y:moveState.positions[b.id].y},'reopen restores parent-relative movement after reload');
const hiddenBefore=structuredClone(moveState.positions),newCore={...moveState.positions[owner.id],x:owner.x+250,y:owner.y+160};
applyLayout(moving,moveState,{[owner.id]:newCore});
for(const id of ['checksum','field:checksum:out:checksum']){
  assert.ok(Math.abs(moveState.positions[id].x-hiddenBefore[id].x-250)<1e-8,'automatic move carries hidden descendants once');
  assert.ok(Math.abs(moveState.positions[id].y-hiddenBefore[id].y-160)<1e-8);
}
// Cross-group summaries attach at boundaries, and preserve typed original facts.
const sampleNodes=[
  {id:'a'},{id:'b'},{id:'f',parent:'a'},{id:'x',parent:'f'},
  {id:'g',parent:'a'},{id:'y',parent:'b'}
];
const sampleBoxes=sampleNodes.map((node,i)=>({id:node.id,node,x:[0,2200,0,0,800,2200][i],y:[0,0,-600,-900,0,400][i],w:140,h:100}));
const sampleEdges=[
  {id:'outside-one',from:'x',to:'y',type:'guard',label:"Permission",observed:true,current:true},
  {id:'outside-two',from:'g',to:'y',type:'guard',label:"Version",observed:false,current:true},
  {id:'inside-call',from:'f',to:'g',type:'flow',origin:'python-ast',callsite:{line:9},label:"Call g",observed:false},
  {id:'inside-flow',from:'f',to:'g',type:'flow',label:"Next step"},
  {id:'parameter',from:'x',to:'f',type:'data',label:"Input"},
  {id:'containment',from:'a',to:'f',type:'contains',label:"Contains"}
];
const sample={boxes:sampleBoxes,byId:new Map(sampleBoxes.map(b=>[b.id,b])),all:new Map(sampleNodes.map(n=>[n.id,n])),edges:sampleEdges};
sample.regions=hierarchyRegions(sample);
sample.edges.push({id:'upper-flow',from:'a',to:'b',type:'flow',label:"Top-level flow"});
const summary=compoundEdges(sample),external=summary.find(e=>e.members.some(m=>m.id==='upper-flow'));
const innerCross=summary.filter(e=>e.type==='guard');
assert.deepEqual(innerCross.map(e=>[e.from,e.to]),[['x','y'],['g','y']],'expanded cross-circle edges keep exact inner endpoints');
assert.ok(innerCross.every(e=>e.crossing&&!e.sourceRegion&&!e.targetRegion),'inner crossing edges use the foreground layer');
assert.deepEqual(innerCross.flatMap(e=>e.members.map(m=>[m.id,m.from,m.to,m.observed])),[['outside-one','x','y',true],['outside-two','g','y',false]],'partial runtime evidence stays on its true relation');
assert.equal(external.from,'a');assert.equal(external.to,'b');
assert.ok(external.sourceRegion&&external.targetRegion);
assert.equal(external.members[0].id,'upper-flow','only an actual top-level edge joins the outer circles');
const ports=edgePorts(sample,external);
for(const [id,endpoint] of [['a',ports.start],['b',ports.end]]){
  const circle=sample.regions.find(r=>r.id===id);
  assert.ok(Math.abs(Math.hypot(endpoint.x-circle.cx,endpoint.y-circle.cy)-circle.radius)<1e-8,'upper-level edge ends on the enclosing circle');
}
assert.ok(summary.some(e=>e.type==='call'&&e.from==='f'&&e.to==='g'&&e.sourceRegion));
assert.ok(summary.some(e=>e.type==='flow'&&e.from==='f'&&e.to==='g'),'flow and static call cannot merge');
assert.ok(summary.some(e=>e.type==='data'&&e.from==='x'&&e.to==='f'&&!e.targetRegion),'local parameter relation stays inside its own group');
assert.ok(!summary.some(e=>e.type==='contains'),'containment is shown by enclosure, not duplicate crossing lines');
assert.equal(sample.edges.length,7,'presentation does not delete source relations');
assert.notDeepEqual(relationStyles.call,relationStyles.flow);
// Expansion may clear neighboring free groups, but never moves the opened core.
const settleState=emptyLayout(),settled=layoutGraph(view,new Set(['flow.checks','checksum']));
placeIncremental(settled,settleState);const retainedCore={...settleState.positions.checksum};
settleExpansion(settled,settleState,'checksum');
assert.deepEqual(settleState.positions.checksum,retainedCore);
checkCircles(settled);
assert.deepEqual(view.model.nodes.find(n=>n.id==='checksum').source,{path:'app/checks.py',symbol:'checksum'},'view operations do not edit model facts');
console.log(JSON.stringify({valid:true,coverage:'unified nodes and edges, real ELK layered/stress, drag/pan, pins, persisted annotations and focus, nested expansion, upgrade, source identity and history boundary'}));

// Every expandable type uses its own circle identity; containment alone does not
// create a self glyph. A real relation to a hidden descendant still requires it.
// Data roles refine existing protocol kinds rather than introduce new kinds.
const dataRoleKinds={store:'data',dataset:'data',column:'data',query:'function',transform:'function'};
for(const type of Object.keys(nodeTypes)){
  const parent={id:'owner',kind:dataRoleKinds[type]||type,...(dataRoleKinds[type]?{data_role:type}:{}),...(type==='business'?{layer:'business'}:{}),...(type==='resource'?{execution_role:'resource'}:{})};
  const child={id:'child',parent:'owner',kind:'function'},hidden={id:'hidden',parent:'child',kind:'data'};
  const boxes=[parent,child].map((node,i)=>({id:node.id,node,type:nodeType(node),x:i*300,y:0,w:140,h:100}));
  const subject={all:new Map([parent,child,hidden].map(n=>[n.id,n])),boxes,byId:new Map(boxes.map(b=>[b.id,b])),edges:[{id:'contains',from:'owner',to:'child',type:'contains'}]};
  subject.regions=hierarchyRegions(subject);
  let shown=presentationGraph(subject);
  assert.equal(nodeType(parent),type);
  assert.ok(shown.regions.has('owner')&&!shown.glyphs.has('owner'),type+' is represented by its circle, without a duplicate');
  assert.ok(shown.glyphs.has('child'));
  subject.rawEdges=[...subject.edges,{id:'input',from:'hidden',to:'owner',type:'data'}];
  subject.regions=hierarchyRegions(subject);shown=presentationGraph(subject);
  assert.ok(hasSelfRelation(subject,'owner')&&shown.glyphs.has('owner'),type+' retains a real self relation');
  assert.deepEqual({x:subject.regions[0].cx,y:subject.regions[0].cy},nodeCenter(boxes[0]),'self glyph is at the circle center');
}
for(const role of Object.keys(dataRoleKinds)){
  assert.notEqual(nodeType({id:'invalid-kind',kind:role}),role,'a kind alone cannot imply a database role');
}
const originalSample=JSON.stringify([...sample.all]),coordinates=JSON.stringify(sample.boxes);
let filters=emptyFilters();filters.nodes=[];filters.regions=['function'];filters.edges=['flow'];
let filtered=presentationGraph(sample,filters);
assert.equal(filtered.glyphs.size,0);
assert.deepEqual(filtered.edges.map(e=>[e.from,e.to]),[['a','b']],'circle-only filtering retains actual upper-level relationships');
filters=emptyFilters();filters.regions=[];filters.nodes=['function'];filters.edges=['guard'];
filtered=presentationGraph(sample,filters);
assert.equal(filtered.regions.size,0);assert.equal(filtered.edges.length,2);
assert.ok(filtered.glyphs.has('a'),'hiding a circle falls back to the node when its type is enabled');
filters.depth=2;
filtered=presentationGraph(sample,filters);
assert.deepEqual([...filtered.glyphs],['x']);assert.equal(filtered.edges.length,0,'filtered edges cannot hang or invent replacement parents');
assert.equal(JSON.stringify([...sample.all]),originalSample);assert.equal(JSON.stringify(sample.boxes),coordinates,'filtering does not edit positions, types or source facts');
moveState.filters={...filters,nodes:[],edges:[],regions:[]};
writeLayout(storage,'filtered',moveState);
const restoredFilter=readLayout(storage,'filtered').state;
assert.deepEqual(restoredFilter.filters,moveState.filters,'empty selections and depth survive reload');
assert.equal(JSON.stringify(restoredFilter.positions),JSON.stringify(moveState.positions),'filters retain dragged hidden descendants');
assert.deepEqual(cleanFilters({nodes:['invalid','state','state'],depth:-1}).nodes,['state']);
assert.equal(cleanFilters({depth:-1}).depth,'all');
assert.equal(readLayout(storage,'old').state.filters.nodes.length,Object.keys(nodeTypes).length,'old layouts acquire all types without hiding anything');
const timed=structuredClone(view);
timed.machine.configurations[0].qualification={valid_until:100};
timed.authority.basis.clock=98;
const beforeDeadline=renderRevision(timed);
timed.authority.basis.clock=99;
assert.equal(renderRevision(timed),beforeDeadline,'clock-only polls do not rebuild the graph');
timed.authority.basis.clock=100;
assert.notEqual(renderRevision(timed),beforeDeadline,'the exact expiry boundary still updates historical judgments');
const expired=renderRevision(timed);timed.authority.basis.clock=101;
assert.equal(renderRevision(timed),expired);
timed.authority.basis.param_version+=1;
assert.notEqual(renderRevision(timed),expired,'real parameter changes remain observable');
assert.notEqual(renderRevision(timed,['run-one']),renderRevision(timed,['run-two']),'run selection cannot reuse a stale projection');
console.log(JSON.stringify({valid:true,coverage:'all expandable types, centered self relations, true cross-circle endpoints, foreground routing, independent node/edge/circle/depth filters, preference persistence, idle polling and exact expiry'}));
