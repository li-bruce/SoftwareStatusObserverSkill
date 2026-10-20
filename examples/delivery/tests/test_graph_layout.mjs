import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {layoutGraph} from '../integrations/bo_view/graph-core.js';
import {emptyLayout,layoutKey,readLayout,writeLayout,placeIncremental,setPosition,togglePin,calculateLayout,applyLayout,GraphGesture,annotationFor,displayName,setAnnotation,pickHit} from '../integrations/bo_view/layout.js';
const view=JSON.parse(fs.readFileSync(new URL('../scratch/graph-fixture.json',import.meta.url),'utf8'));
const expanded=new Set(['flow.checks','checksum']);
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

const state=emptyLayout();placeIncremental(graph,state);
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
  setAnnotation(state,id,{label:'我理解的 '+id,note:'核对输入版本\n保留原始结果'});
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
assert.equal(displayName(reopenedBranch.byId.get('checksum').node,personal),'我理解的 checksum');
assert.equal(displayName({...reopenedBranch.byId.get('checksum').node,label:'生成器的新名称'},personal),'我理解的 checksum','regeneration cannot overwrite a user label');
setAnnotation(personal,'checksum',{...annotationFor(personal,'checksum'),label:''});
assert.equal(displayName({...reopenedBranch.byId.get('checksum').node,label:'生成器的新名称'},personal),'生成器的新名称');
assert.equal(annotationFor(personal,'checksum').note,'核对输入版本\n保留原始结果','restore original name keeps the note');
setAnnotation(personal,'checksum',{label:'',note:''});
assert.ok(!personal.annotations.checksum);
setAnnotation(personal,'__proto__',{label:'安全的 ID',note:'<script>text only</script>'});
assert.equal(Object.getPrototypeOf(personal.annotations),null);
assert.equal(annotationFor(personal,'__proto__').label,'安全的 ID');
setAnnotation(personal,'limits',{label:'长'.repeat(100),note:'注'.repeat(600)});
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
for(const algorithm of ['layered','stress']){
  const result=await calculateLayout(elk,unfolded,state,algorithm);
  assert.deepEqual(result.checksum,pinned,algorithm+' must respect an exact user pin');
  assert.ok(Object.values(result).every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
  assert.ok(unfolded.boxes.some(b=>!result[b.id].pinned&&(b.x!==result[b.id].x||b.y!==result[b.id].y)));
  applyLayout(unfolded,state,result);
  for(let i=0;i<unfolded.boxes.length;i++)for(let j=i+1;j<unfolded.boxes.length;j++){
    const a=unfolded.boxes[i],b=unfolded.boxes[j];
    assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y,algorithm+' must separate node label bounds');
  }
}
assert.deepEqual(view.model.nodes.find(n=>n.id==='checksum').source,{path:'app/checks.py',symbol:'checksum'},'view operations do not edit model facts');
console.log(JSON.stringify({valid:true,coverage:'unified nodes and edges, real ELK layered/stress, drag/pan, pins, persisted annotations and focus, nested expansion, upgrade, source identity and history boundary'}));
