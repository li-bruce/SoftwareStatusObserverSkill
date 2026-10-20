import {colors as C,executionIds,layoutGraph,selectedConfiguration,configurations,stateLabels,nodeTypes,sourceBinding} from './graph-core.js';
import {layoutKey,readLayout,writeLayout,placeIncremental,setPosition,togglePin,calculateLayout,applyLayout,topologyKey,GraphGesture,annotationFor,displayName,setAnnotation,pickHit,searchNodes,ancestorsToReveal} from './layout.js';
const $=id=>document.getElementById(id),app=new PIXI.Application(),scene=new PIXI.Container();
// The bundled ELK entry defaults to its Node fallback unless a factory is supplied.
const layoutWorker=new Worker(new URL('./elk-worker.min.js',import.meta.url));
const elk=new ELK({workerFactory:()=>layoutWorker}),gesture=new GraphGesture();
let version='live',caseChoice='normal',choice='latest',step='latest',view=null,graph=null,selected=null;
let scale=1,pan={x:0,y:0},expanded=new Set(),preferences=null,storageKey=null,first=true,lastKey='',dirty=false;
let layoutEpoch=0,layoutBusy=false,layoutError=null,undo=null,detailMode=null,saveTimer=null,drawCount=0;
const hits=[],fullSources=new Map(),metrics={nodes:0,edges:0,texts:0};
let storage;try{storage=window.localStorage;}catch{storage={getItem(){throw Error('storage unavailable');},setItem(){throw Error('storage unavailable');}};}
await app.init({resizeTo:$('viewport'),preference:'webgl',antialias:true,background:0xf6f8fa,resolution:Math.min(devicePixelRatio,2),autoDensity:true,autoStart:false});
$('canvas-host').appendChild(app.canvas);app.stage.addChild(scene);app.canvas.setAttribute('aria-hidden','true');
$('renderer').textContent='PixiJS / WebGL · ELK';
function visible(x,y,w,h){return x+w>=-pan.x/scale-60&&y+h>=-pan.y/scale-60&&x<=(-pan.x+app.screen.width)/scale+60&&y<=(-pan.y+app.screen.height)/scale+60;}
function text(value,x,y,size=12,color=C.ink,align='left',weight='400'){
  const t=new PIXI.Text({text:String(value),style:{fontFamily:'Segoe UI, Microsoft YaHei, sans-serif',fontSize:size,fill:color,fontWeight:weight}});
  t.anchor.set(align==='center'?.5:0,0);t.position.set(x,y);scene.addChild(t);metrics.texts++;return t;
}
function short(value,count=27){const chars=[...String(value)];return chars.length>count?chars.slice(0,count-1).join('')+'…':String(value);}
function shade(b){return ({active:0x22876e,ok:0x22876e,blocked:0xbd8237,historical:0x688aa8})[b.state]||nodeTypes[b.type].color;}
function point(b){return {x:b.x+b.w/2,y:b.y+31};}
function drawEdges(){
  const lanes=new Map(),labelBoxes=[];
  for(const e of graph.edges){
    const a=graph.byId.get(e.from),b=graph.byId.get(e.to);if(!a||!b)continue;
    const p=point(a),q=point(b),key=[e.from,e.to].sort().join('|'),index=lanes.get(key)||0;lanes.set(key,index+1);
    const highlight=e.from===selected||e.to===selected,col=e.observed?(e.current?0x328c75:0x718fa7):e.type==='transition'?0xa3a0b7:e.type==='contains'?0xc1ccd5:0xa8b9c7;
    const dx=q.x-p.x,dy=q.y-p.y,length=Math.hypot(dx,dy)||1,offset=(index+1)*18;
    let start,end,c1,c2,mid;
    if(a===b){start={x:p.x-18,y:p.y-18};end={x:p.x+18,y:p.y-18};c1={x:p.x-68,y:p.y-95-offset};c2={x:p.x+68,y:p.y-95-offset};mid={x:p.x,y:p.y-75-offset};}
    else{
      start={x:p.x+dx/length*28,y:p.y+dy/length*28};end={x:q.x-dx/length*28,y:q.y-dy/length*28};
      c1={x:start.x+dx*.32-dy/length*offset,y:start.y+dy*.32+dx/length*offset};
      c2={x:end.x-dx*.32-dy/length*offset,y:end.y-dy*.32+dx/length*offset};
      mid={x:(start.x+3*c1.x+3*c2.x+end.x)/8,y:(start.y+3*c1.y+3*c2.y+end.y)/8};
    }
    if(!visible(Math.min(p.x,q.x)-120,Math.min(p.y,q.y)-120,Math.abs(dx)+240,Math.abs(dy)+240))continue;
    const g=new PIXI.Graphics().moveTo(start.x,start.y).bezierCurveTo(c1.x,c1.y,c2.x,c2.y,end.x,end.y).stroke({color:col,width:highlight?2.2:e.observed?1.9:1,alpha:highlight||e.observed?1:e.type==='contains'?.4:.62});scene.addChild(g);metrics.edges++;
    const angle=Math.atan2(end.y-c2.y,end.x-c2.x);
    if(e.type!=='contains'){const arrow=new PIXI.Graphics().poly([end.x,end.y,end.x-7*Math.cos(angle-.5),end.y-7*Math.sin(angle-.5),end.x-7*Math.cos(angle+.5),end.y-7*Math.sin(angle+.5)]).fill(col);scene.addChild(arrow);}
    if(highlight||e.observed&&scale>.4||scale>.5&&e.type!=='contains'){
      const font=11.5/Math.sqrt(Math.min(1,scale)),label=short([...e.labels].join(' / '),highlight?44:24),w=Math.min(390,[...label].reduce((n,c)=>n+(c.charCodeAt(0)>255?font:font*.57),0)+12),h=font+7;
      // Put labels along the curve where they avoid nodes and previous labels.
      const candidates=[.5,.32,.68,.2,.8].map(t=>({x:(1-t)**3*start.x+3*(1-t)**2*t*c1.x+3*(1-t)*t*t*c2.x+t**3*end.x,y:(1-t)**3*start.y+3*(1-t)**2*t*c1.y+3*(1-t)*t*t*c2.y+t**3*end.y}));
      const collision=(x,y,b)=>x-w/2<b.x+b.w&&x+w/2>b.x&&y-h/2<b.y+b.h&&y+h/2>b.y;
      const candidate=candidates.find(p=>!graph.boxes.some(b=>collision(p.x,p.y,b))&&!labelBoxes.some(b=>collision(p.x,p.y,b)))||(highlight?mid:null);
      if(candidate){mid=candidate;const bg=new PIXI.Graphics().roundRect(mid.x-w/2,mid.y-h/2,w,h,4).fill({color:0xf6f8fa,alpha:.96});scene.addChild(bg);text(label,mid.x,mid.y-font/2,font,highlight?0x4c6d85:0x6a8294,'center');labelBoxes.push({x:mid.x-w/2,y:mid.y-h/2,w,h});hits.push({x:mid.x-w/2,y:mid.y-h/2,w,h,edge:e});}
    }
  }
}
function drawNode(b){
  if(!visible(b.x-10,b.y-10,b.w+20,b.h+30))return;metrics.nodes++;
  const p=point(b),style=nodeTypes[b.type],stroke=shade(b),g=new PIXI.Graphics(),r=b.type==='business'?29:24;
  if(selected===b.id)g.circle(p.x,p.y,r+7).stroke({color:0x6497c5,width:1.5,alpha:.65});
  if(b.type==='business'||b.type==='state'){g.circle(p.x,p.y,r).fill(0xffffff).stroke({color:stroke,width:b.state==='declared'?1.7:2.5});if(b.type==='state')g.circle(p.x,p.y,r-5).stroke({color:stroke,width:1});}
  else if(b.type==='decision'||b.type==='data'){g.poly([p.x,p.y-r-3,p.x+r+5,p.y,p.x,p.y+r+3,p.x-r-5,p.y]).fill(0xffffff).stroke({color:stroke,width:1.8});}
  else if(b.type==='resource'){for(let k=2;k>=0;k--)g.roundRect(p.x-25,p.y-18+k*5,50,24,7).fill(0xffffff).stroke({color:stroke,width:1.5});}
  else{g.poly([p.x-30,p.y,p.x-17,p.y-23,p.x+17,p.y-23,p.x+30,p.y,p.x+17,p.y+23,p.x-17,p.y+23]).fill(0xffffff).stroke({color:stroke,width:1.8});}
  scene.addChild(g);text(b.type==='business'?'业务':style.glyph,p.x,p.y-11,b.type==='business'?13:19,stroke,'center','600');
  if(b.pinned){const pin=new PIXI.Graphics().circle(p.x+29,p.y-24,5).fill(0x4f7598);scene.addChild(pin);}
  const annotation=annotationFor(preferences,b.id);
  if(annotation.label||annotation.note)text('✎',p.x-35,p.y-31,14,0x5075b5,'center');
  if(b.kids.length){text(b.open?'−':'+',p.x+38,p.y-4,16,0x467795,'center');hits.push({x:p.x+27,y:p.y-14,w:24,h:26,expand:b.id});}
  text(short(displayName(b.node,preferences),19),p.x,b.y+65,14/Math.sqrt(Math.min(1,scale)),0x2b4658,'center',b.type==='business'?'600':'500');
  if(scale>.48){
    let rows;
    if(b.type==='state')rows=b.rows.filter(r=>r.role==='value').slice(0,1);
    else if(b.type==='business')rows=b.rows.filter(r=>['value','good','bad'].includes(r.role)).slice(0,2);
    else if(b.node.field)rows=b.rows.slice(0,2);
    else rows=[b.rows[0],...b.rows.filter(r=>r!==b.rows[0]&&['good','bad','value'].includes(r.role))].filter(Boolean).slice(0,2);
    rows.forEach((row,i)=>text(short(row.text,29),p.x,b.y+91+i*18,11.5/Math.sqrt(Math.min(1,scale)),row.role==='bad'?0xa76d2c:row.role==='good'?0x327e6b:0x637c8d,'center'));
    if(annotation.note)text(short('备注：'+annotation.note.replace(/\s+/g,' '),27),p.x,b.y+b.h-19,11.5/Math.sqrt(Math.min(1,scale)),0x5075b5,'center');
  }
  hits.push({id:b.id,x:b.x,y:b.y+5,w:b.w,h:b.h-4,cx:p.x,cy:p.y,r:r+6});
}
function draw(){
  dirty=false;if(!graph)return;
  for(const c of scene.removeChildren())c.destroy({children:true,texture:true,textureSource:true});
  scene.position.set(pan.x,pan.y);scene.scale.set(scale);hits.length=0;metrics.nodes=metrics.edges=metrics.texts=0;
  drawEdges();for(const b of graph.boxes)drawNode(b);app.renderer.render(app.stage);drawCount++;
  $('zoom').value=Math.round(scale*100)+'%';updateSemanticGeometry();positionDetail();
}
function schedule(){if(!dirty){dirty=true;requestAnimationFrame(draw);}}
function save(){
  if(!preferences)return;preferences.expanded=[...expanded];preferences.camera={x:pan.x,y:pan.y,scale};preferences.focus=selected;
  const saved=writeLayout(storage,storageKey,preferences);
  if(!layoutBusy)$('layout-status').textContent=layoutError||(saved?'视图已保存':'本次视图未能保存');
}
function saveSoon(){clearTimeout(saveTimer);saveTimer=setTimeout(save,180);}
window.addEventListener('pagehide',save);
function cancelLayout(){layoutEpoch++;layoutBusy=false;layoutError=null;$('arrange').disabled=false;}
function project(){
  if(!view)return;
  graph=layoutGraph(view,expanded,new Set(),new Map(),choice,step);
  for(const b of graph.boxes){b.baseHeight=b.h;b.h+=annotationFor(preferences,b.id).note?22:0;}
  placeIncremental(graph,preferences);
  updateSemantic();updateActions();updateDetail();schedule();
}
async function arrange(initial=false){
  if(!graph)return;const epoch=++layoutEpoch,key=topologyKey(graph),scope=storageKey,algorithm=$('layout').value;
  const previous=JSON.stringify(preferences.positions),camera={scale,pan:{...pan}};
  layoutBusy=true;layoutError=null;$('arrange').disabled=true;$('layout-status').textContent='正在布局…';
  try{
    const positions=await calculateLayout(elk,graph,preferences,algorithm);
    if(epoch!==layoutEpoch||scope!==storageKey||!graph||key!==topologyKey(graph))return;
    undo={positions:previous,camera};$('undo-layout').disabled=false;
    applyLayout(graph,preferences,positions);preferences.algorithm=algorithm;fit();
  }catch(error){if(epoch===layoutEpoch){console.error(error);layoutError='布局失败，保留原位置';}}
  finally{if(epoch===layoutEpoch){layoutBusy=false;$('arrange').disabled=false;save();updateActions();schedule();}}
}
function fit(){if(!graph)return;scale=Math.max(.12,Math.min(1.05,(app.screen.width-45)/graph.width,(app.screen.height-45)/graph.height));pan={x:(app.screen.width-graph.width*scale)/2-graph.minX*scale,y:(app.screen.height-graph.height*scale)/2-graph.minY*scale};schedule();saveSoon();}
function zoom(factor,point={x:app.screen.width/2,y:app.screen.height/2}){const next=Math.max(.12,Math.min(3,scale*factor));pan.x=point.x-(point.x-pan.x)*next/scale;pan.y=point.y-(point.y-pan.y)*next/scale;scale=next;schedule();saveSoon();}
function select(id){selected=id;detailMode=null;$('node-details').hidden=true;updateActions();schedule();saveSoon();}
function toggle(id){if(!graph?.children.has(id))return;cancelLayout();selected=id;if(expanded.has(id))expanded.delete(id);else expanded.add(id);project();save();}
function pin(){if(!selected)return;cancelLayout();togglePin(graph,preferences,selected);updateActions();save();schedule();}
function updateActions(){
  const b=graph?.byId.get(selected),binding=sourceBinding(view,graph?.all,selected);
  $('node-expand').disabled=!b?.kids.length;$('node-expand').textContent=b?.open?'收起':'展开';
  $('pin').disabled=!b;$('pin').textContent=b?.pinned?'取消固定':'固定节点';$('annotate').disabled=!b;$('details').disabled=!b;$('source').disabled=!binding;
  $('selection').textContent=b?`${nodeTypes[b.type].label} · ${displayName(b.node,preferences)}`+(binding?` · ${binding.path}:${binding.line}`:''):'拖动节点调整布局；双击展开内部关系。';
}
function updateSemantic(){
  const host=$('semantic'),focused=document.activeElement?.dataset.nodeId;host.replaceChildren();
  for(const b of graph.boxes){const button=document.createElement('button'),name=displayName(b.node,preferences);button.textContent=name;button.dataset.nodeId=b.id;button.dataset.nodeType=b.type;button.setAttribute('aria-label',name);button.setAttribute('aria-expanded',String(!!b.open));button.onclick=()=>select(b.id);button.onfocus=()=>{if(selected!==b.id)select(b.id);};host.appendChild(button);}
  if(focused){const el=[...host.children].find(e=>e.dataset.nodeId===focused);el?.focus({preventScroll:true});}
}
function updateSemanticGeometry(){
  const r=app.canvas.getBoundingClientRect();
  for(const el of $('semantic').children){const b=graph.byId.get(el.dataset.nodeId);if(b){const p=point(b);el.dataset.x=b.x;el.dataset.y=b.y;el.dataset.pinned=String(!!b.pinned);el.dataset.screenX=r.left+p.x*scale+pan.x;el.dataset.screenY=r.top+p.y*scale+pan.y;}}
}
function updateDetail(){
  const b=graph?.byId.get(selected);if(!b||!detailMode){$('node-details').hidden=true;return;}
  const annotation=annotationFor(preferences,b.id),editing=detailMode==='annotation';
  $('node-details').hidden=false;$('detail-title').textContent=displayName(b.node,preferences);
  $('annotation-form').hidden=!editing;
  const rows=[...(annotation.label||editing?[{text:'原名：'+b.node.label}]:[]),
    ...(editing?[{text:'节点：'+b.id}]:b.rows),...(!editing&&annotation.note?[{text:'备注：'+annotation.note}]:[])];
  $('detail-rows').replaceChildren(...rows.map(r=>{const p=document.createElement('p');p.textContent=r.text;return p;}));
  const binding=sourceBinding(view,graph.all,selected),source=detailMode==='source'&&binding;
  $('source-code').hidden=!source;$('full-source').hidden=!source;
  if(source){const key=view.manifest.build_id+':'+binding.path,full=fullSources.get(key);$('detail-title').textContent=`${binding.path}:${binding.line} · ${view.manifest.build_id.slice(0,8)}`;$('source-code').textContent=full??binding.snippet;$('full-source').hidden=!!full;}
  positionDetail();
}
function positionDetail(){
  if($('node-details').hidden||!graph?.byId.has(selected))return;
  const b=graph.byId.get(selected),p=point(b),panel=$('node-details'),w=panel.offsetWidth,h=panel.offsetHeight;
  panel.style.left=Math.max(10,Math.min(app.screen.width-w-10,p.x*scale+pan.x+45))+'px';
  panel.style.top=Math.max(10,Math.min(app.screen.height-h-12,p.y*scale+pan.y-30))+'px';
}
function showDetail(mode){detailMode=mode;updateDetail();}
function editAnnotation(){
  if(!graph?.byId.has(selected))return;const b=graph.byId.get(selected),annotation=annotationFor(preferences,selected);
  $('node-name').value=annotation.label;$('node-name').placeholder=b.node.label;$('node-note').value=annotation.note;
  showDetail('annotation');$('node-name').focus({preventScroll:true});
}
function saveAnnotation(){
  const b=graph?.byId.get(selected);if(!b||detailMode!=='annotation')return;
  cancelLayout();const annotation=setAnnotation(preferences,selected,{label:$('node-name').value,note:$('node-note').value});
  b.h=b.baseHeight+(annotation.note?22:0);placeIncremental(graph,preferences);
  for(const el of $('semantic').children){const node=graph.byId.get(el.dataset.nodeId)?.node;if(node){const name=displayName(node,preferences);el.textContent=name;el.setAttribute('aria-label',name);}}
  updateActions();updateDetail();save();schedule();
}
$('node-name').oninput=saveAnnotation;$('node-note').oninput=saveAnnotation;
$('restore-name').onclick=()=>{$('node-name').value='';saveAnnotation();};
$('annotation-form').onsubmit=e=>{e.preventDefault();saveAnnotation();detailMode=null;updateDetail();$('viewport').focus({preventScroll:true});};
$('full-source').onclick=async()=>{
  const id=selected,build=view.manifest.build_id,binding=sourceBinding(view,graph.all,id),requestedVersion=version;
  const response=await fetch('/api/source?path='+encodeURIComponent(binding.path)+'&version='+encodeURIComponent(requestedVersion));if(!response.ok)return;
  const data=await response.json();if(view?.manifest.build_id!==build||data.build_id!==build||version!==requestedVersion)return;
  fullSources.set(build+':'+binding.path,data.source);if(selected===id)updateDetail();
};
function hitAt(e){const r=app.canvas.getBoundingClientRect();return pickHit(hits,(e.clientX-r.left-pan.x)/scale,(e.clientY-r.top-pan.y)/scale);}
app.canvas.addEventListener('pointerdown',e=>{
  if(e.button!==0||gesture.active)return;
  const hit=hitAt(e);cancelLayout();app.canvas.setPointerCapture(e.pointerId);
  if(hit?.id)select(hit.id);
  gesture.start({pointerId:e.pointerId,x:e.clientX,y:e.clientY},{node:hit?.id?graph.byId.get(hit.id):null,pan,scale});
  gesture.active.hit=hit;app.canvas.style.cursor=hit?.id?'grabbing':'move';
});
app.canvas.addEventListener('pointermove',e=>{
  const move=gesture.move({pointerId:e.pointerId,x:e.clientX,y:e.clientY});if(!move)return;
  if(move.kind==='node')setPosition(graph,preferences,move.id,move.x,move.y);else pan={x:move.x,y:move.y};schedule();
});
function endDrag(e,cancelled=false){
  const gestureEnd=gesture.end(e.pointerId);if(!gestureEnd)return;app.canvas.style.cursor='default';
  if(!gestureEnd.moved&&!cancelled){const h=gestureEnd.hit;if(h?.expand)toggle(h.expand);else if(h?.edge){selected=null;updateActions();$('selection').textContent=[...h.edge.labels].join(' · ')+(h.edge.observed?' · 有运行记录':' · 声明关系');}else if(!h)select(null);}
  save();schedule();
}
app.canvas.addEventListener('pointerup',e=>endDrag(e));app.canvas.addEventListener('pointercancel',e=>endDrag(e,true));app.canvas.addEventListener('lostpointercapture',e=>endDrag(e,true));
app.canvas.addEventListener('dblclick',e=>{const h=hitAt(e);if(h?.id)toggle(h.id);});
app.canvas.addEventListener('wheel',e=>{e.preventDefault();const r=app.canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),{x:e.clientX-r.left,y:e.clientY-r.top});},{passive:false});
$('viewport').addEventListener('keydown',e=>{
  if(e.target.closest('#node-details'))return;
  if(e.key==='0')fit();if(e.key==='+'||e.key==='=')zoom(1.15);if(e.key==='-')zoom(1/1.15);
  if(e.key.toLowerCase()==='p')pin();if(e.key==='Enter'&&selected){e.preventDefault();toggle(selected);}
  if(e.key==='Escape'){detailMode=null;select(null);}
  const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];
  if(delta){e.preventDefault();const b=graph?.byId.get(selected),distance=e.shiftKey?80:20;cancelLayout();if(b)setPosition(graph,preferences,b.id,b.x+delta[0]*distance,b.y+delta[1]*distance);else{pan.x-=delta[0]*50;pan.y-=delta[1]*50;}save();schedule();}
});
$('fit').onclick=fit;$('zoom-in').onclick=()=>zoom(1.2);$('zoom-out').onclick=()=>zoom(1/1.2);$('arrange').onclick=()=>arrange();
$('undo-layout').onclick=()=>{if(!undo)return;cancelLayout();preferences.positions=Object.assign(Object.create(null),JSON.parse(undo.positions));scale=undo.camera.scale;pan=undo.camera.pan;undo=null;$('undo-layout').disabled=true;project();save();};
$('collapse').onclick=()=>{cancelLayout();expanded.clear();detailMode=null;project();save();};
$('expand').onclick=()=>{cancelLayout();for(const id of view.model.graph_roots)expanded.add(id);project();save();};
$('node-expand').onclick=()=>toggle(selected);$('pin').onclick=pin;$('details').onclick=()=>showDetail('values');$('source').onclick=()=>showDetail('source');$('close-detail').onclick=()=>{detailMode=null;updateDetail();};
$('annotate').onclick=editAnnotation;
function showSearch(){
  const list=$('search-results');list.replaceChildren();
  if(!graph||!$('node-search').value.trim()){list.hidden=true;return;}
  const results=searchNodes(graph.all,preferences,$('node-search').value);
  for(const result of results){
    const button=document.createElement('button');button.type='button';
    const title=document.createElement('strong'),description=document.createElement('span');
    const parent=graph.all.get(result.node.parent),context=parent?displayName(parent,preferences):'';
    title.textContent=result.name;
    description.textContent=result.node.field?[context,result.node.direction==='in'?'输入':'输出',result.node.fieldType].filter(Boolean).join(' · '):[context,result.node.source?.symbol||result.node.id].filter(Boolean).join(' · ');
    button.append(title,description);button.onclick=()=>revealResult(result.node.id);list.append(button);
  }
  if(!results.length){const empty=document.createElement('p');empty.textContent='没有找到节点';list.append(empty);}
  list.hidden=false;
}
function revealResult(id){
  if(!graph?.all.has(id))return;
  cancelLayout();for(const parent of ancestorsToReveal(graph.all,id))expanded.add(parent);
  project();select(id);
  const box=graph.byId.get(id);
  if(box){scale=Math.max(.8,scale);const p=point(box);pan={x:app.screen.width/2-p.x*scale,y:app.screen.height/2-p.y*scale};}
  $('search-results').hidden=true;save();schedule();$('viewport').focus({preventScroll:true});
}
$('node-search').oninput=showSearch;$('node-search').onfocus=showSearch;
$('node-search').onkeydown=e=>{
  if(e.key==='Escape')$('search-results').hidden=true;
  if(e.key==='Enter'){e.preventDefault();const first=graph&&searchNodes(graph.all,preferences,e.target.value,1)[0];if(first)revealResult(first.node.id);}
};
document.addEventListener('pointerdown',e=>{if(!e.target.closest('.graph-search'))$('search-results').hidden=true;});
$('attempt').onchange=e=>{choice=e.target.value;step='latest';lastKey='';project();};$('step').onchange=e=>{step=e.target.value;project();updateFacts();};
new ResizeObserver(()=>{app.renderer.resize($('viewport').clientWidth,$('viewport').clientHeight);schedule();}).observe($('viewport'));
function updateFacts(){
  if(!view)return;const state=selectedConfiguration(view,choice,step),p=view.authority.parameters;
  const phase=step!=='latest'?state?.phase:choice==='latest'?view.machine.current:state?.phase;
  $('phase').textContent=phase?'流程状态：'+view.model.machine.labels[phase]:step!=='latest'?'回看内部活动；该时刻未记录流程状态':'尚无运行记录';
  $('context').textContent=`参数版本 ${state?.param_version||p.param_version} · 本次名额 ${Object.values(state?.resources||{})[0]?.capacity??p.capacity??'—'}`+(step!=='latest'?` · 第 ${step} 步`:'');
}
function frameLabel(entry){const name=view.model.nodes.find(n=>n.id===entry.activity)?.label||entry.activity;return `${entry.seq} · ${entry.event==='join'?(entry.after.join.state==='passed'?'两项检查通过':'检查未全部通过'):entry.event==='abort'?'检查已停止':name+'：'+(stateLabels[entry.after.activities[entry.activity]]||entry.event)}`;}
async function poll(){
  const requestedVersion=version,requestedCase=caseChoice;
  try{
    const r=await fetch('/api/view?version='+encodeURIComponent(version)+'&case='+encodeURIComponent(caseChoice),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
    const next=await r.json();if(version!==requestedVersion||caseChoice!==requestedCase)return;
    const key=JSON.stringify([version,caseChoice,next.manifest.build_id,next.events.at(-1)?.id,next.machine.current,next.authority.basis,next.binding_status.status,next.busy,choice,next.machine.configurations?.map(r=>[r.attempt,r.revision,r.phase])]);
    view=next;$('empty').hidden=true;$('title').textContent=(view.model.presentation.subject||'程序')+' · 运行图';
    const nextStorageKey=layoutKey(next.layout_id?{...view.model,presentation:{...view.model.presentation,layout_id:next.layout_id}}:view.model);
    if(nextStorageKey!==storageKey){cancelLayout();const restored=readLayout(storage,nextStorageKey);preferences=restored.state;storageKey=nextStorageKey;selected=preferences.focus;expanded=new Set(restored.restored?preferences.expanded:view.model.presentation.default_expanded||[]);if(preferences.camera){scale=preferences.camera.scale;pan={x:preferences.camera.x,y:preferences.camera.y};}first=true;$('layout').value=preferences.algorithm;}
    const cases=next.available_cases||[];if(JSON.stringify([cases,version])!==$('case').dataset.options){$('case').replaceChildren(...cases.map(v=>new Option(v==='live'?'当前操作':next.case_names?.[v]||v,v)));$('case').dataset.options=JSON.stringify([cases,version]);if(cases.includes(caseChoice))$('case').value=caseChoice;}
    const gaps=next.health.errors+next.health.dropped+(next.health.parse_errors||0)+(next.health.truncated||0);
    $('connection').textContent=gaps?'有 '+gaps+' 条记录缺失':next.historical?'保存的运行':'已连接';
    const stale=next.binding_status.status!=='current';$('binding').textContent=stale?'程序尚未加载新代码':'代码版本 '+next.manifest.build_id.slice(0,8);$('binding').classList.toggle('stale',stale);
    if(key!==lastKey){
      lastKey=key;const run=selectedConfiguration(view,choice);
      $('step').replaceChildren(new Option('最新状态','latest'),...(run?.journal||[]).map(e=>new Option(frameLabel(e),String(e.seq))));if(run?.journal.some(e=>String(e.seq)===step))$('step').value=step;else step='latest';
      const select=$('attempt');select.replaceChildren(new Option('当前运行','latest'));const runs=configurations(view);
      if(runs.length)runs.forEach((run,i)=>select.add(new Option(`第 ${i+1} 次 · 版本 ${run.param_version}`+(run.disposition==='superseded'?'（旧版本）':run.disposition==='interrupted'?'（中断）':''),run.attempt)));else for(const id of executionIds(view))select.add(new Option('运行 '+id,id));select.value=choice;
      const hasPositions=Object.keys(preferences.positions).length>0;project();
      if(first){first=false;if(!hasPositions)arrange(true);else if(!preferences.camera)fit();}saveSoon();
    }
    updateFacts();
  }catch(error){console.error(error);$('connection').textContent='暂时无法连接程序';if(!view){$('empty').hidden=false;$('empty').textContent='正在等待程序连接。';}}
  finally{setTimeout(poll,400);}
}
function changeView(){cancelLayout();choice='latest';step='latest';lastKey='';detailMode=null;view=null;graph=null;for(const c of scene.removeChildren())c.destroy({children:true});app.renderer.render(app.stage);$('node-details').hidden=true;}
$('version').onchange=e=>{version=e.target.value;caseChoice='normal';changeView();};$('case').onchange=e=>{caseChoice=e.target.value;changeView();};
fetch('/api/versions').then(r=>r.json()).then(v=>$('version').replaceChildren(...v.versions.map(x=>new Option(x==='live'?'当前程序':x,x)))).catch(()=>{});
// Read-only debugging data; UI actions use the same pointer/keyboard handlers as users.
window.graphDebug={get graph(){return graph;},get view(){return view;},get camera(){return {scale,pan:{...pan}};},get metrics(){return {...metrics,drawCount,webgl:!!app.renderer.gl};},get layoutBusy(){return layoutBusy;}};
poll();
