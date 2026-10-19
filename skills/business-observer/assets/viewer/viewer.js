'use strict';
const $ = id => document.getElementById(id);
const statusNames = {true:'满足',false:'未满足',unknown:'未检查',stale:'已变化'};
const stateNames = {ready:'待交付',waiting:'等待处理',done:'已完成',cancelled:'已取消'};
const outcomeNames = {delivered:'交付完成',waiting:'等待处理',already_done:'已经完成',changed:'已更新',observed:'开始任务',cancelled:'已取消'};
let signature='', data, view='business', selected=null, automatic=true, busy=false, latest=new Map(), scoped=[];
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function options(select,items,fallback){const previous=select.value;select.replaceChildren(...items.map(([value,label])=>{const o=el('option',label);o.value=value;return o;}));select.value=items.some(x=>x[0]===previous)?previous:(fallback??items[0]?.[0]??'');}
function badge(status,label){return el('span',label||statusNames[status],'badge '+status);}
function eventVersion(e){return e.payload.basis_version??e.payload.version??0;}
function authoritySummary(){const a=data.authority;if(!a)return {};return a.summary||{state:a.facts?.state,version:a.facts?.version,clock:a.facts?.clock,effect_count:Array.isArray(a.deliveries)?a.deliveries.length:undefined};}
function currentClock(){if($('attempt').value!=='current')return latest.get(data.clock_node||'f_clock')?.payload.value;return authoritySummary().clock;}
function statusOf(node){
  const e=latest.get(node.id);if(!e)return 'unknown';const p=e.payload;
  if(data.binding_status!=='current')return 'stale';
  if($('attempt').value==='current'&&node.kind!=='effect'&&authoritySummary().version!==undefined&&eventVersion(e)!==authoritySummary().version)return 'stale';
  if(p.valid_until!==null&&p.valid_until!==undefined&&currentClock()!==undefined&&currentClock()>=p.valid_until)return 'stale';
  if(['unknown','cache','intermediate','inferred'].includes(p.quality))return 'unknown';
  if(['decision','transition','effect'].includes(e.kind)&&p.status!==undefined)return Object.hasOwn(statusNames,p.status)?p.status:'unknown';
  if(e.kind==='transition'||e.kind==='effect'){
    if(['waiting','denied','rejected','failed','blocked','cancelled'].includes(p.outcome))return 'false';
    if(['committed','delivered','completed','already_done','changed','observed'].includes(p.outcome))return 'true';
    return 'unknown';
  }
  return p.quality==='committed'?'true':'unknown';
}
function nodeById(id){return data.model.nodes.find(n=>n.id===id);}
function copy(n){return data.presentation?.nodes?.[n.id]||{};}
function label(n){return copy(n).label||n.label;}
function statusLabel(n){
  const s=statusOf(n);
  if(['object','state'].includes(n.kind)&&!latest.has(n.id))return '';
  if(s==='unknown')return n.kind==='condition'?'未检查':'暂无记录';
  if(s==='stale')return '已变化';
  if(n.kind==='condition')return statusNames[s];
  if(n.kind==='fact')return s==='true'?'已记录':'待确认';
  if(n.kind==='wait')return s==='false'?'等待中':'已记录';
  return s==='true'?'已完成':'未完成';
}
function selectNode(id){selected=id;renderGraph();renderDetail();}
function selectView(next){view=next;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.view===view)));$('focus-wrap').hidden=view!=='dependency';renderGraph();}
function primaryConditions(){
  const roots=data.model.edges.filter(e=>e.type==='requires'&&e.target===$('action-focus').value).map(e=>nodeById(e.source)).filter(Boolean);
  const result=roots.flatMap(n=>n.operator==='all'?(n.dependencies||[]).map(nodeById).filter(d=>d?.kind==='condition'):[n]);
  return result.length?result:roots;
}
function conditionButton(n){const b=el('button',undefined,'condition');b.dataset.node=n.id;b.append(el('span',label(n)),badge(statusOf(n)));b.onclick=()=>{selected=n.id;$('focus').value=n.id;selectView('dependency');renderDetail();};return b;}
function filteredEvents(){return data.events.filter(e=>e.build_id===data.manifest.build_id&&e.run_id===$('run').value&&e.entity_id===$('entity').value).sort((a,b)=>eventVersion(a)-eventVersion(b)||a.seq-b.seq);}
function outcome(r){return data.presentation?.outcomes?.[r?.outcome]||outcomeNames[r?.outcome]||'查看结果';}
function commandLabel(r){return data.presentation?.commands?.[r?.command]||'任务操作';}
function refreshFilters(){
  const events=data.events.filter(e=>e.build_id===data.manifest.build_id);
  const runs=[...new Set(events.map(e=>e.run_id))];options($('run'),runs.map(r=>[r,r.slice(0,10)]),data.health?.run_id);
  const inRun=events.filter(e=>e.run_id===$('run').value);const entities=[...new Set(inRun.map(e=>e.entity_id))];options($('entity'),entities.map(e=>[e,e]));
  scoped=filteredEvents();const attempts=[...new Set(scoped.map(e=>e.attempt_id))].reverse();
  options($('attempt'),[['current','当前'],...attempts.map((a,i)=>{const r=data.authority?.receipts?.find(r=>r.attempt_id===a);return [a,String(attempts.length-i)+' · '+commandLabel(r)+' · '+outcome(r)];})],'current');
  const root=data.model.edges.find(e=>e.type==='requires'&&e.target===$('action-focus').value)?.source;
  options($('focus'),data.model.nodes.filter(n=>n.kind==='condition').map(n=>[n.id,label(n)]),root);
}
function renderSummary(){
  const summary=authoritySummary(), conditions=primaryConditions(), historical=$('attempt').value!=='current';
  const stateLabel=data.presentation?.states?.[summary.state]||stateNames[summary.state]||summary.state||'状态未接入';
  $('business-state').textContent=stateLabel;$('business-state').className='state-pill '+(summary.state||'');
  let message='',next='';
  if(historical){const r=data.authority?.receipts?.find(r=>r.attempt_id===$('attempt').value);message='历史操作：'+commandLabel(r)+'，'+outcome(r)+'。';next='顶部状态显示当前结果。';}
  else if(summary.state==='done'){message='任务已完成。';next='';}
  else if(summary.state==='cancelled'){message='任务已取消。';}
  else if(conditions.some(n=>statusOf(n)==='stale')){message='条件已更新，需要再试一次。';next='原来的检查结果已不适用。';}
  else {
    const blocked=conditions.filter(n=>statusOf(n)==='false');
    if(blocked.length){message=blocked.map(n=>copy(n).failure||label(n)+'尚未满足').join('；')+'。';next='处理后，再尝试执行。';}
    else if(!conditions.some(n=>latest.has(n.id))){message='还没有尝试执行。';next=data.workbench?'在操作页尝试一次，查看结果。':'';}
    else if(conditions.some(n=>statusOf(n)==='unknown')){message='还有条件未确认。';}
    else{message='上次检查的条件已满足。';next=data.workbench?'在操作页查看执行结果。':'';}
  }
  $('goal').textContent=message;$('next-step').textContent=next;$('next-step').hidden=!next;$('back-current').hidden=!historical;
}
function render(){
  if(!data)return;
  options($('action-focus'),data.model.nodes.filter(n=>n.kind==='action').map(n=>[n.id,label(n)]),data.model.edges.find(e=>e.type==='requires')?.target);
  refreshFilters();latest=new Map();for(const e of scoped){if($('attempt').value==='current'||e.attempt_id===$('attempt').value)latest.set(e.node_id,e);}
  $('title').textContent=data.presentation?.title||data.model.title;document.title=$('title').textContent;
  $('purpose').textContent=data.presentation?.purpose||'';$('purpose').hidden=!$('purpose').textContent;
  $('workbench').hidden=!data.workbench;
  if(typeof data.workbench==='string'&&data.workbench.startsWith('/')&&!data.workbench.startsWith('//'))$('workbench').href=data.workbench;
  const summary=authoritySummary(), decisions=data.model.nodes.filter(n=>n.kind==='condition'&&latest.has(n.id));
  $('effect-count').textContent=summary.effect_count===undefined?'未独立核对':String(summary.effect_count);
  $('basis-state').textContent=!decisions.length?'尚无判定':decisions.some(n=>statusOf(n)==='stale')?'已变化，须重新判定':$('attempt').value==='current'?'最近一次判定':'历史尝试快照';
  $('build-state').textContent={current:'内容对应',stale:'源码已变化',unknown:'对应未知'}[data.binding_status]||'未知';
  $('clock').textContent=summary.version!==undefined?'事实版本 '+summary.version+' · 业务时钟 '+(summary.clock??'未接入'):'当前权威版本未接入';
  const alerts=[],tech=[],h=data.health||{};
  if(data.binding_status!=='current')alerts.push('程序已更新，请重启后查看最新结果。');
  if(h.enabled===false)alerts.push('当前未记录操作，流程图可能没有最新结果。');
  if(h.dropped||h.errors||data.authority?.observer_errors)alerts.push('部分操作记录缺失，请到任务页核对结果。');
  if(h.queued)tech.push('待写记录：'+h.queued);
  if(h.dropped||h.errors)tech.push('丢弃：'+h.dropped+'；写入错误：'+h.errors);
  if(h.enabled===null)tech.push('正在浏览文件，未接入实时采集健康状态。');
  if(data.ingestion?.malformed||data.ingestion?.truncated)tech.push('记录包含未完成行或已截取尾部。');
  if(data.events.some(e=>e.build_id!==data.manifest.build_id))tech.push('其他源码版本的事件未叠加到当前图。');
  $('alerts').replaceChildren(...alerts.map(t=>el('div',t,'alert')));
  $('technical-alerts').replaceChildren(...tech.map(t=>el('li',t)));
  $('condition-list').replaceChildren(...primaryConditions().map(conditionButton));
  document.querySelector('.conditions').hidden=!primaryConditions().length;
  $('unknowns').replaceChildren(...[...new Set([...data.model.scope.unknowns,...data.manifest.unknowns])].map(s=>el('li',s)));
  renderSummary();renderGraph();renderDetail();renderTimeline();
}
function positions(){
  let visible=[],pos=new Map();
  if(view==='business'){
    const action=nodeById($('action-focus').value);if(!action)return {visible,pos};
    const related=new Set([action.id]);for(const e of data.model.edges){if(e.source===action.id)related.add(e.target);if(e.target===action.id)related.add(e.source);}
    visible=data.model.nodes.filter(n=>related.has(n.id)&&(n.level===0||n.kind==='condition')&&(n.kind!=='action'||n.id===action.id));
    const guards=visible.filter(n=>n.kind==='condition');guards.forEach((n,i)=>pos.set(n.id,{x:304,y:14+i*100}));
    const actionY=Math.max(116,guards.length*100+14);pos.set(action.id,{x:304,y:actionY});
    visible.filter(n=>['object','state'].includes(n.kind)).sort((a,b)=>(a.kind==='state'?0:1)-(b.kind==='state'?0:1)).forEach((n,i)=>pos.set(n.id,{x:28,y:actionY+i*105}));
    visible.filter(n=>['effect','wait'].includes(n.kind)).sort((a,b)=>(a.kind==='effect'?0:1)-(b.kind==='effect'?0:1)).forEach((n,i)=>pos.set(n.id,{x:592,y:actionY+i*135}));
  }else{
    const focus=nodeById($('focus').value);if(!focus)return {visible,pos};
    const deps=(focus.dependencies||[]).map(nodeById).filter(Boolean);
    const downstream=data.model.edges.filter(e=>e.source===focus.id&&['supports','requires'].includes(e.type)).map(e=>nodeById(e.target));
    visible=[...deps,focus,...downstream];deps.forEach((n,i)=>pos.set(n.id,{x:28,y:20+i*100}));pos.set(focus.id,{x:304,y:20+Math.max(0,deps.length-1)*50});downstream.forEach((n,i)=>pos.set(n.id,{x:592,y:20+i*100}));
  }
  return {visible:[...new Map(visible.map(n=>[n.id,n])).values()],pos};
}
function renderGraph(){
  if(!data)return;
  $('graph').hidden=view==='facts';$('fact-table').hidden=view!=='facts';
  $('action-wrap').hidden=view!=='business'||data.model.nodes.filter(n=>n.kind==='action').length<2;
  $('map-caption').textContent=view==='business'?'点击节点，查看业务说明':view==='dependency'?(nodeById($('focus').value)?.operator==='any'?'满足任意一项即可':nodeById($('focus').value)?.operator==='all'?'需要全部满足':'查看这项条件的依据'):'点击一项查看详情';
  if(view==='facts'){renderFacts();return;}
  const {visible,pos}=positions(),ids=new Set(visible.map(n=>n.id)),inner=el('div',undefined,'graph-inner');
  const height=Math.max(350,...[...pos.values()].map(p=>p.y+125));inner.style.width='800px';inner.style.height=height+'px';
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 800 '+height);svg.setAttribute('aria-hidden','true');
  const defs=document.createElementNS(ns,'defs'),marker=document.createElementNS(ns,'marker');
  for(const [k,v] of Object.entries({id:'arrow',viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'}))marker.setAttribute(k,v);
  const arrow=document.createElementNS(ns,'path');arrow.setAttribute('d','M 0 0 L 10 5 L 0 10 z');arrow.setAttribute('fill','#9cafb8');marker.append(arrow);defs.append(marker);svg.append(defs);
  for(const e of data.model.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))){
    const a=pos.get(e.source),b=pos.get(e.target);let x1=a.x+172,y1=a.y+36,x2=b.x,y2=b.y+36;
    if(a.x===b.x){x1=a.x+86;x2=b.x+86;y1=a.y+(b.y>a.y?72:0);y2=b.y+(b.y>a.y?0:72);}else if(a.x>b.x){x1=a.x;x2=b.x+172;}
    const line=document.createElementNS(ns,'path'),reverse=data.model.edges.some(other=>other.source===e.target&&other.target===e.source)&&a.y>b.y;
    let labelX=(x1+x2)/2+5,labelY=(y1+y2)/2-8;
    if(reverse){x1=a.x+86;y1=a.y+72;x2=b.x+86;y2=b.y+72;line.setAttribute('d','M '+x1+' '+y1+' C '+x1+' '+(height-12)+', '+x2+' '+(height-12)+', '+x2+' '+y2);labelX=(x1+x2)/2;labelY=height-28;}
    else{line.setAttribute('d','M '+x1+' '+y1+' C '+((x1+x2)/2)+' '+y1+', '+((x1+x2)/2)+' '+y2+', '+x2+' '+y2);if(a.x===b.x)labelX+=58;}
    line.setAttribute('class','edge');line.setAttribute('marker-end','url(#arrow)');svg.append(line);
    const text=document.createElementNS(ns,'text');text.setAttribute('x',String(labelX));text.setAttribute('y',String(labelY));text.setAttribute('text-anchor','middle');text.setAttribute('class','edge-label');text.textContent=data.presentation?.edge_labels?.[e.label]||e.label;svg.append(text);
  }
  inner.append(svg);
  for(const n of visible){
    const b=el('button',undefined,'node'+(selected===n.id?' selected':'')),p=pos.get(n.id),s=statusLabel(n);
    b.style.left=p.x+'px';b.style.top=p.y+'px';b.dataset.node=n.id;b.dataset.status=statusOf(n);b.setAttribute('aria-label',label(n)+(s?'，'+s:''));
    if(n.operator==='any')b.append(el('small','满足任一项'));
    if(n.operator==='all')b.append(el('small','需要全部满足'));
    b.append(el('b',label(n)));if(s)b.append(el('span',s,'node-status'));
    b.onclick=()=>{selected=n.id;if(view==='dependency'&&n.kind==='condition')$('focus').value=n.id;renderGraph();renderDetail();};inner.append(b);
  }
  $('graph').replaceChildren(inner);
}
function factValue(n,e){
  if(!e)return '暂无记录';
  const p=e.payload,c=copy(n);
  const format=(v,i)=>{const key=String(v);return c.field_values?.[i]?.[key]??c.values?.[key]??data.presentation?.values?.[key]??(v===null?'未知':v===true?'是':v===false?'否':key);};
  return Array.isArray(p.value)?p.value.map((v,i)=>(c.fields?.[i]?c.fields[i]+'：':'')+format(v,i)).join('；'):format(p.value);
}
function renderFacts(){
  const table=el('table'),head=el('tr');['信息','当前记录','状态'].forEach(t=>head.append(el('th',t)));table.append(head);
  for(const n of data.model.nodes.filter(n=>n.kind==='fact')){
    const row=el('tr'),cell=el('td'),b=el('button',label(n));b.dataset.node=n.id;b.onclick=()=>selectNode(n.id);cell.append(b);
    row.append(cell,el('td',factValue(n,latest.get(n.id))));const state=el('td');state.append(badge(statusOf(n),statusLabel(n)));row.append(state);table.append(row);
  }
  $('fact-table').replaceChildren(table);
}
function renderDetail(){
  const n=nodeById(selected),aside=$('detail');aside.hidden=!n;document.querySelector('.workspace').classList.toggle('has-detail',Boolean(n));if(!n)return;
  const e=latest.get(n.id),c=copy(n),heading=el('div',undefined,'detail-heading'),close=el('button','×');
  close.setAttribute('aria-label','关闭说明');close.onclick=()=>{selected=null;renderGraph();renderDetail();};
  heading.append(el('h2',label(n)),close);aside.replaceChildren(heading);
  if(statusLabel(n))aside.append(badge(statusOf(n),statusLabel(n)));
  aside.append(el('p',c.description||n.description,'description'));
  if(n.kind==='fact')aside.append(el('p',factValue(n,e),'result'));
  if(n.kind==='condition'&&statusOf(n)==='false'&&c.failure)aside.append(el('p',c.failure,'result'));
  if(n.kind==='condition'&&statusOf(n)==='stale')aside.append(el('p','相关信息已变化，需要重新检查。','result'));
  if(n.dependencies?.length){aside.append(el('h3',n.operator==='any'?'满足任一项即可':n.operator==='all'?'需要全部满足':'相关信息'));const group=el('div');for(const id of n.dependencies){const b=el('button',label(nodeById(id)),'dependency-link');b.onclick=()=>selectNode(id);group.append(b);}aside.append(group);}
  const technical=el('details',undefined,'technical');technical.append(el('summary','技术记录'));
  technical.append(el('p','节点 '+n.id+' · 语义来源 '+n.origin,'meta'));
  if(e)technical.append(el('p','事务 '+e.tx_id+' · 事件 '+e.event_id,'meta'),el('pre',JSON.stringify(e.payload,null,2)));
  else technical.append(el('p','当前范围内无事件。'));
  for(const b of data.manifest.bindings.filter(b=>b.node===n.id)){const d=el('details'),sum=el('summary',b.path+':'+b.line);sum.setAttribute('aria-label','查看源码 '+b.symbol);d.append(sum,el('p',b.symbol+' · 文件 SHA256 '+b.file_sha256,'meta'),el('pre',b.snippet));technical.append(d);}
  technical.append(el('p','build '+data.manifest.build_id+' · 模型 '+data.model.revision,'meta'));aside.append(technical);
}
function renderTimeline(){
  const groups=new Map();for(const e of scoped){if(!groups.has(e.attempt_id))groups.set(e.attempt_id,[]);groups.get(e.attempt_id).push(e);}
  const rows=[...groups.entries()].reverse().slice(0,40).map(([id,es])=>{
    const r=data.authority?.receipts?.find(r=>r.attempt_id===id),row=el('div',undefined,'timeline-row'),b=el('button',commandLabel(r)+' · '+outcome(r));
    b.onclick=()=>{$('attempt').value=id;render();};const date=new Date(es[es.length-1].observed_at);
    row.append(el('small',Number.isNaN(date.getTime())?'':date.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})),b);return row;
  });
  $('timeline').replaceChildren(...(rows.length?rows:[el('p','暂无操作记录。')]));$('event-count').textContent=scoped.length+' 条事件 · '+groups.size+' 次操作';
}
async function refresh(){
  if(busy)return;busy=true;let received=false;
  try{const response=await fetch('/api/view',{cache:'no-store'});if(!response.ok)throw Error('unavailable');data=await response.json();received=true;const next=JSON.stringify(data);if(next!==signature){render();signature=next;}$('connection').textContent='';$('connection').dataset.state='connected';$('updated').textContent='读取于 '+new Date().toLocaleTimeString('zh-CN');}
  catch(_){$('connection').textContent=received?'暂时无法显示结果':'连接已断开，显示上次结果';$('connection').dataset.state=received?'invalid':'disconnected';}
  finally{busy=false;}
}
$('refresh').onclick=refresh;
$('auto').onclick=()=>{automatic=!automatic;$('auto').textContent='自动刷新：'+(automatic?'开':'关');$('auto').setAttribute('aria-pressed',String(automatic));};
for(const id of ['run','entity','attempt'])$(id).onchange=render;
$('focus').onchange=()=>{selected=$('focus').value;renderGraph();renderDetail();};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>selectView(b.dataset.view));
$('action-focus').onchange=()=>{selected=null;render();};
$('back-current').onclick=()=>{$('attempt').value='current';render();};
refresh();setInterval(()=>{if(automatic&&!document.hidden)refresh();},1800);
