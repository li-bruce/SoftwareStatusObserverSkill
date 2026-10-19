import {colors as C,compact,executionIds,layoutGraph,layoutMachine} from './graph-core.js';
const $=id=>document.getElementById(id);
const app=new PIXI.Application();
let view=null,graph=null,choice='latest',mode='behavior',expanded=new Set(),sourceOpen=new Set(),fullSources=new Map();
let scale=1,pan={x:0,y:0},first=true,dirty=false,drawCount=0,lastKey='',scene=new PIXI.Container(),selected=null;
const hits=[],metrics={frames:[],nodes:0,edges:0,texts:0};
await app.init({resizeTo:$('viewport'),preference:'webgl',antialias:true,background:0xf3f5f6,resolution:Math.min(devicePixelRatio,2),autoDensity:true,autoStart:false});
$('canvas-host').appendChild(app.canvas);app.stage.addChild(scene);
const gl=app.renderer.gl;
$('renderer').textContent=`PixiJS ${PIXI.VERSION} · ${gl?'WebGL':'无 WebGL'}`;
app.canvas.setAttribute('aria-hidden','true');
function visible(x,y,w,h){return x+w>=-pan.x/scale-40&&y+h>=-pan.y/scale-40&&x<=(-pan.x+app.screen.width)/scale+40&&y<=(-pan.y+app.screen.height)/scale+40;}
function text(txt,x,y,size=12,color=C.ink,weight='400',width){
  if(!visible(x,y,width||Math.min(700,txt.length*size*.85),size+8))return;
  const t=new PIXI.Text({text:txt,style:{fontFamily:'Segoe UI, Microsoft YaHei, sans-serif',fontSize:size,fill:color,fontWeight:weight}});t.position.set(x,y);scene.addChild(t);metrics.texts++;return t;
}
function rect(x,y,w,h,fill,stroke=0,r=8,alpha=1){const g=new PIXI.Graphics().roundRect(x,y,w,h,r).fill({color:fill,alpha});if(stroke)g.stroke({color:stroke,width:1});scene.addChild(g);return g;}
function color(state){return ({ok:C.green,active:C.green,blocked:C.orange,historical:C.blue})[state]||C.muted;}
function button(label,x,y,w,action){rect(x,y,w,25,0xf0f5f5,0xd5e1e3,4);text(label,x+7,y+5,11,C.ink);hits.push({x,y,w,h:25,action});}
function drawEdges(){
  let lane=0;
  for(const e of graph.edges){
    const a=graph.byId.get(e.from),b=graph.byId.get(e.to);if(!a||!b)continue;
    const ac={x:a.x+a.w/2,y:a.y+(a.open?70:a.h/2)},bc={x:b.x+b.w/2,y:b.y+(b.open?70:b.h/2)};
    let p,q,mx,my,g=new PIXI.Graphics();const color=e.observed?(e.current?C.green:C.blue):C.line;
    if(a.id===b.id){p={x:a.x+a.w*.7,y:a.y};q={x:a.x+a.w*.3,y:a.y};my=a.y-24;mx=a.x+a.w/2;g.moveTo(p.x,p.y).bezierCurveTo(p.x,my-22,q.x,my-22,q.x,q.y);}
    else if(Math.abs(bc.x-ac.x)>Math.abs(bc.y-ac.y)*.8){const dir=bc.x>ac.x?1:-1;p={x:dir>0?a.x+a.w:a.x,y:ac.y};q={x:dir>0?b.x:b.x+b.w,y:bc.y};mx=(p.x+q.x)/2;my=(p.y+q.y)/2;g.moveTo(p.x,p.y).bezierCurveTo(mx,p.y,mx,q.y,q.x,q.y);}
    else {const dir=bc.y>ac.y?1:-1;p={x:ac.x,y:dir>0?a.y+a.h:a.y};q={x:bc.x,y:dir>0?b.y:b.y+b.h};mx=(p.x+q.x)/2;my=(p.y+q.y)/2;g.moveTo(p.x,p.y).bezierCurveTo(p.x,my,q.x,my,q.x,q.y);}
    if(!visible(Math.min(p.x,q.x)-100,Math.min(p.y,q.y)-50,Math.abs(p.x-q.x)+200,Math.abs(p.y-q.y)+100)){g.destroy();continue;}
    g.stroke({color,width:e.observed?2.5:1.1,alpha:e.observed?1:.75});scene.addChild(g);metrics.edges++;
    const angle=Math.atan2(q.y-my,q.x-mx);const arrow=new PIXI.Graphics().poly([q.x,q.y,q.x-7*Math.cos(angle-.5),q.y-7*Math.sin(angle-.5),q.x-7*Math.cos(angle+.5),q.y-7*Math.sin(angle+.5)]).fill(color);scene.addChild(arrow);
    if(scale>.43){
      const labels=[...e.labels],shown=labels.slice(0,3).map(l=>l.length>32?l.slice(0,30)+'…':l);
      if(labels.length>3)shown.push(`含 ${labels.length} 项依赖 · 展开节点查看`);
      const width=Math.min(245,Math.max(75,...shown.map(l=>l.length*6.3+16))),height=shown.length*17+9,ly=my-height/2;
      rect(mx-width/2,ly,width,height,0xf8fbfb,0xdce7e8,4,.97);shown.forEach((label,i)=>text(label,mx-width/2+7,ly+5+i*17,10.5,e.observed?color:C.muted));
      hits.push({x:mx-width/2,y:ly,w:width,h:height,action:()=>{selected=e.id;$('selection').textContent=labels.join(' · ')+' | '+(e.observed?'有显式运行引用':'声明关系，尚无本次运行引用');}});
    }
  }
}
function drawNode(b){
  if(!visible(b.x,b.y,b.w,b.h))return;metrics.nodes++;
  const n=b.node,accent=color(b.state),hasKids=(graph.children?.get(b.id)?.length||0)>0;
  if(!b.open)rect(b.x,b.y,b.w,b.h,n.layer==='state'?0xf0f6f4:C.white,b.state==='declared'?0xd1dfe3:accent);
  else rect(b.x,b.y,b.w,Math.min(54+b.rows.length*19,b.h),0xf8fcfb,0,7);
  rect(b.x,b.y,4,Math.min(46,b.h),accent,0,2);
  text(n.label,b.x+15,b.y+14,16,C.ink,'600',b.w-35);
  const layer={business:'业务',program:'程序',state:'状态',predicate:'条件'}[n.layer]||'程序';
  text(layer,b.x+b.w-47,b.y+17,11,C.muted);
  hits.push({id:b.id,x:b.x,y:b.y,w:b.w,h:43,action:()=>toggle(b.id)});
  let y=b.y+48;
  if(scale>.36){for(const row of b.rows){const tint={muted:C.muted,good:C.green,bad:C.orange,symbol:C.blue,value:C.ink}[row.role]||C.ink;text(row.text,b.x+15,y,row.role==='symbol'?12:12,tint,row.role==='symbol'?'600':'400',b.w-30);y+=19;}}
  else text(n.source?.symbol||n.value||'',b.x+15,y,13,C.muted);
  const actionY=b.y+55+b.rows.length*19;
  if(hasKids)button(b.open?'− 收起局部图':`＋ 展开 ${graph.children.get(b.id).length} 个节点`,b.x+15,actionY,145,()=>toggle(b.id));
  if(view.manifest.bindings[b.id])button(sourceOpen.has(b.id)?'− 源码':'{ } 源码',b.x+(hasKids?174:15),actionY,84,()=>toggleSource(b.id));
  if(b.code){
    const cy=b.y+b.codeY;rect(b.x+12,cy,b.w-24,b.h-b.codeY-12,0xeff3f4,0xd9e3e6,6);
    const binding=view.manifest.bindings[b.id];text(`${binding.path}:${binding.line} · 加载版本 ${view.manifest.build_id.slice(0,8)}`,b.x+22,cy+13,12,C.blue,'600');
    if(!fullSources.has(b.id))button('完整文件',b.x+b.w-103,cy+7,80,()=>loadFullSource(b.id));
    b.code.forEach((line,i)=>text(line,b.x+22,cy+44+i*18,11.5,C.ink,'400',b.w-40));
  }
}
function draw(){
  dirty=false;if(!graph)return;const started=performance.now();
  const old=scene.removeChildren();for(const c of old)c.destroy({children:true,texture:true,textureSource:true});
  scene.position.set(pan.x,pan.y);scene.scale.set(scale);hits.length=0;metrics.nodes=metrics.edges=metrics.texts=0;
  for(const b of graph.boxes)if(b.open&&visible(b.x,b.y,b.w,b.h))rect(b.x-1,b.y-1,b.w+2,b.h+2,0xeaf0f1,0xc3d4d8,10);
  drawEdges();for(const b of graph.boxes)drawNode(b);
  app.renderer.render(app.stage);drawCount++;metrics.frames.push(performance.now()-started);if(metrics.frames.length>160)metrics.frames.shift();
  $('zoom').value=Math.round(scale*100)+'%';
}
function schedule(){if(!dirty){dirty=true;requestAnimationFrame(draw);}}
function project(){const previous=graph?.byId.get(selected),anchor=previous?{x:previous.x*scale+pan.x,y:previous.y*scale+pan.y}:null;graph=mode==='machine'?layoutMachine(view,choice,sourceOpen,fullSources):layoutGraph(view,expanded,sourceOpen,fullSources,choice);const next=graph.byId.get(selected);if(anchor&&next){pan.x=anchor.x-next.x*scale;pan.y=anchor.y-next.y*scale;}updateSemantic();schedule();}
function anchorMutate(id,fn){const old=graph.byId.get(id),screen=old?{x:old.x*scale+pan.x,y:old.y*scale+pan.y}:null;fn();project();const next=graph.byId.get(id);if(next&&screen){pan.x=screen.x-next.x*scale;pan.y=screen.y-next.y*scale;}schedule();}
function toggle(id){selected=id;if(mode==='machine'){toggleSource(id);return;}if(graph.children?.has(id))anchorMutate(id,()=>expanded.has(id)?expanded.delete(id):expanded.add(id));else toggleSource(id);$('selection').textContent='当前节点 · '+graph.byId.get(id)?.node.label;}
function toggleSource(id){if(!view.manifest.bindings[id])return;anchorMutate(id,()=>sourceOpen.has(id)?sourceOpen.delete(id):sourceOpen.add(id));}
async function loadFullSource(id){const b=view.manifest.bindings[id];const r=await fetch('/api/source?path='+encodeURIComponent(b.path));if(!r.ok)return;const data=await r.json();if(data.build_id!==view.manifest.build_id)return;anchorMutate(id,()=>fullSources.set(id,data.source));}
function fit(){if(!graph)return;scale=Math.max(.18,Math.min(1.12,(app.screen.width-40)/graph.width,(app.screen.height-35)/graph.height));pan={x:(app.screen.width-graph.width*scale)/2,y:(app.screen.height-graph.height*scale)/2};schedule();}
function zoom(factor,point={x:app.screen.width/2,y:app.screen.height/2}){const next=Math.max(.15,Math.min(2.4,scale*factor));pan.x=point.x-(point.x-pan.x)*next/scale;pan.y=point.y-(point.y-pan.y)*next/scale;scale=next;schedule();}
function updateSemantic(){
  const host=$('semantic');host.replaceChildren();
  for(const b of graph.boxes){const button=document.createElement('button');button.textContent=b.node.label;button.setAttribute('aria-expanded',String(!!b.open));button.onclick=()=>{toggle(b.id);};host.appendChild(button);}
  const crumb=$('breadcrumbs');crumb.replaceChildren();
  let n=view.model.nodes.find(n=>n.id===selected),chain=[];
  while(n){chain.unshift(n);n=view.model.nodes.find(x=>x.id===n.parent);}
  for(const item of chain){const button=document.createElement('button');button.textContent=item.label;button.onclick=()=>{const b=graph.byId.get(item.id);if(b){scale=Math.max(.5,Math.min(1,(app.screen.width-80)/b.w,(app.screen.height-80)/b.h));pan={x:40-b.x*scale,y:45-b.y*scale};selected=item.id;updateSemantic();schedule();}};crumb.appendChild(button);}
}
let dragging=null;
app.canvas.addEventListener('pointerdown',e=>{app.canvas.setPointerCapture(e.pointerId);dragging={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y,moved:false};});
app.canvas.addEventListener('pointermove',e=>{if(!dragging)return;const dx=e.clientX-dragging.x,dy=e.clientY-dragging.y;if(Math.hypot(dx,dy)>4)dragging.moved=true;if(dragging.moved){pan={x:dragging.px+dx,y:dragging.py+dy};schedule();}});
app.canvas.addEventListener('pointerup',e=>{if(dragging&&!dragging.moved){const r=app.canvas.getBoundingClientRect(),x=(e.clientX-r.left-pan.x)/scale,y=(e.clientY-r.top-pan.y)/scale;const hit=hits.slice().reverse().find(h=>x>=h.x&&x<=h.x+h.w&&y>=h.y&&y<=h.y+h.h);if(hit)hit.action();}dragging=null;});
app.canvas.addEventListener('pointercancel',()=>dragging=null);
app.canvas.addEventListener('wheel',e=>{e.preventDefault();const r=app.canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),{x:e.clientX-r.left,y:e.clientY-r.top});},{passive:false});
$('viewport').addEventListener('keydown',e=>{if(e.key==='0')fit();if(e.key==='+'||e.key==='=')zoom(1.15);if(e.key==='-')zoom(1/1.15);if(e.key==='Escape'){$('collapse').click();}const d={ArrowLeft:[55,0],ArrowRight:[-55,0],ArrowUp:[0,55],ArrowDown:[0,-55]}[e.key];if(d){pan.x+=d[0];pan.y+=d[1];schedule();e.preventDefault();}});
$('fit').onclick=fit;$('zoom-in').onclick=()=>zoom(1.2);$('zoom-out').onclick=()=>zoom(1/1.2);
$('collapse').onclick=()=>{expanded.clear();sourceOpen.clear();project();fit();};
$('expand').onclick=()=>{for(const id of view.model.graph_roots)expanded.add(id);project();fit();};
for(const value of ['behavior','machine'])$(value+'-mode').onclick=()=>{mode=value;for(const m of ['behavior','machine'])$(m+'-mode').classList.toggle('active',m===value);project();fit();};
$('attempt').onchange=e=>{choice=e.target.value;project();};
new ResizeObserver(()=>{app.renderer.resize($('viewport').clientWidth,$('viewport').clientHeight);schedule();}).observe($('viewport'));
async function poll(){
  try{const r=await fetch('/api/view',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const next=await r.json();
    const key=JSON.stringify([next.events.at(-1)?.id,next.machine.current,next.machine.journal.at(-1)?.seq,next.authority.basis,next.binding_status.status,next.busy]);view=next;
    const gaps=next.health.errors+next.health.dropped+(next.health.parse_errors||0)+(next.health.truncated||0);
    $('connection').textContent=gaps?'采集缺口 '+gaps:'● 实时连接';$('phase').textContent=(next.model.machine.state_type||'State')+' = '+next.machine.current;
    const p=next.authority.parameters;$('context').textContent=Object.entries(next.model.machine.context).map(([k,s])=>`${k}: ${s.type==='integer'?'int':s.type} = ${compact(p[k])}`).join(' · ');
    const stale=next.binding_status.status!=='current';$('binding').textContent=stale?'源码已变更 · 当前图仍对应加载版本':'代码 '+next.manifest.build_id.slice(0,8);$('binding').classList.toggle('stale',stale);
    if(key!==lastKey){lastKey=key;const select=$('attempt');select.replaceChildren(new Option('跟随最新执行','latest'));for(const id of executionIds(view).reverse())select.add(new Option('历史 · '+id,id));select.value=choice;project();if(first){fit();if(scale<.72){scale=.8;pan={x:Math.max(15,(app.screen.width-graph.width*scale)/2),y:20};schedule();}first=false;}}
  }catch(e){console.error(e);$('connection').textContent='加载失败 · '+e.message;$('empty').textContent=e.message;if(!view)$('empty').hidden=false;}
  finally{setTimeout(poll,400);}
}
// Readable geometry and metrics are used by the local browser tests, not to synthesize observations.
window.graphDebug={get view(){return view;},get graph(){return graph;},get expanded(){return [...expanded];},get sourceOpen(){return [...sourceOpen];},get metrics(){return {...metrics,drawCount,webgl:!!gl};},get camera(){return {scale,pan};},center(id){const b=graph.byId.get(id),r=app.canvas.getBoundingClientRect();return {x:r.left+(b.x+Math.min(120,b.w/2))*scale+pan.x,y:r.top+(b.y+25)*scale+pan.y};},focus(id){const b=graph.byId.get(id);scale=.9;pan={x:30-b.x*scale,y:25-b.y*scale};schedule();},async benchmark(count=2000){const original=graph;const nodes=[];for(let i=0;i<count;i++){nodes.push({id:'synthetic.'+i,node:{id:'synthetic.'+i,label:'规模夹具 '+i,kind:'function',layer:'program',source:{symbol:'fixture.compute'}},x:(i%50)*390,y:Math.floor(i/50)*210,w:340,h:150,rows:[{text:'value: number = '+i,role:'value'}],kids:[],state:'declared'});}graph={boxes:nodes,byId:new Map(nodes.map(n=>[n.id,n])),edges:nodes.slice(1).map((n,i)=>({from:nodes[i].id,to:n.id,type:'data',labels:new Set(['fixture']),observed:false})),children:new Map(),width:19500,height:Math.ceil(count/50)*210};const saved={scale,pan:{...pan}};scale=.8;pan={x:0,y:0};const times=[];for(let i=0;i<35;i++){pan.x=-i*33;const st=performance.now();draw();times.push(performance.now()-st);await new Promise(requestAnimationFrame);}const stats={synthetic:true,count,edges:graph.edges.length,visibleNodes:metrics.nodes,webgl:!!gl,medianMs:times.sort((a,b)=>a-b)[17],p95Ms:times[33]};graph=original;scale=saved.scale;pan=saved.pan;schedule();return stats;}};
poll();
