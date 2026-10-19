'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const val = x => typeof x === 'object' ? JSON.stringify(x) : String(x ?? '—');
const brief = o => Object.entries(o || {}).map(([k,v])=>`${k}=${val(v)}`).join(' · ');
let view, selected=null, tab='values', mode='overview', choice='latest', eventChoice=null, caseChoice='live', renderKey='';
function eventsForAttempt(){
  const all = view.events;
  const attempts = [...new Set(all.filter(e=>e.phase!=='change').map(e=>e.attempt))];
  const id = choice==='latest' ? attempts.at(-1) : choice;
  return all.filter(e=>e.attempt===id);
}
function current(e){
  const b = view.authority.basis;
  return !!e && e.build_id===view.manifest.build_id && e.entity===view.authority.entity && ['param_version','epoch','clock'].every(k=>e.basis[k]===b[k]);
}
function chosenEvent(node){
  const exact = view.events.find(e=>e.id===eventChoice && e.node===node);
  return exact || eventsForAttempt().filter(e=>e.node===node).at(-1);
}
function status(e){
  if(!e)return 'unknown';
  if(!current(e) && choice==='latest' && !view.historical)return 'stale';
  if(e.phase==='enter')return 'running';
  if(e.phase==='wait' || e.outputs.allowed===false || e.outputs.eligible===false)return 'failed';
  return 'observed';
}
function selectNode(id, eventId=null){ selected=id;eventChoice=eventId;renderGraph();renderInspector(); if(innerWidth<1120)$('inspector').scrollIntoView({block:'start',behavior:'auto'}); }
function selectEvent(id){const e=view.events.find(x=>x.id===id);if(!e)return;choice=e.attempt;eventChoice=id;selected=e.node;render();}
function render(){
  const a=view.authority,b=a.basis;
  if(!view.model.nodes.some(n=>n.id===selected))selected=view.model.default_node||view.model.overview[0].node;
  const presentation=view.model.presentation||{};
  $('subject').textContent=presentation.subject||view.model.title||'业务流程';document.title=(presentation.subject||'业务')+' · 行为调试';
  const panel=$('command-panel');panel.hidden=!presentation.command_panel_url;if(presentation.command_panel_url?.startsWith('/'))panel.href=presentation.command_panel_url;
  if(view.available_cases){$('case').innerHTML=view.available_cases.map(c=>`<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');$('case').value=caseChoice;}
  $('entity').textContent=a.entity;
  $('state').textContent=presentation.states?.[a.state]||a.state;
  $('basis').textContent=`参数 v${b.param_version} · 事实 ${b.epoch} · 时钟 ${b.clock}`;
  $('build').textContent=`build ${view.manifest.build_id.slice(0,8)} · ${view.binding_status.status==='current'?'源码已绑定':'源码已变化'}`;
  const h=view.health; const gap=(h.errors||0)+(h.dropped||0)+(h.parse_errors||0)+(h.truncated||0);
  $('health').textContent=gap?`观测缺口 ${gap}`:h.enabled===false?'探针已关闭':`${h.written||0} 条已记录`;
  const notices=[];
  if(view.historical)notices.push(view.case_label || '历史冻结现场');
  if(view.binding_status.status!=='current')notices.push(`磁盘源码已变化：${(view.binding_status.changed_files||[]).join(', ')}；当前运行与源码面板仍为加载时版本。`);
  if(gap)notices.push('采集不完整，缺失节点与连线不能视为已执行。');
  const latest=eventsForAttempt().at(-1);
  if(latest&&!current(latest)&&choice==='latest'&&!view.historical)notices.push('参数、关系、审批或时钟已变化；最近一次判定已失效，需重新执行求值。');
  $('notice').hidden=!notices.length;$('notice').textContent=notices.join(' ');
  const attempts=[...new Set(view.events.filter(e=>e.phase!=='change').map(e=>e.attempt))].reverse();
  $('attempt').innerHTML='<option value="latest">当前 / 最近一次</option>'+attempts.map(id=>{const ev=view.events.filter(e=>e.attempt===id);return `<option value="${esc(id)}">${esc(id)} · ${esc(ev.at(-1)?.node)} · v${ev[0].basis.param_version}</option>`;}).join('');
  $('attempt').value=choice;
  $('context').textContent=choice==='latest'&&!view.historical?'跟随实际事件 · 每 400 ms 更新':'历史尝试 · 显示当时输入与判定';
  $('event-count').textContent=`${eventsForAttempt().length} 条 / 当前选择`;
  renderGraph();renderInspector();renderEvents();
}
function renderGraph(){
  const nodes=Object.fromEntries(view.model.nodes.map(n=>[n.id,n]));
  let layout=view.model.overview;
  if(mode==='deps')layout=view.model.views?.dependencies||view.model.nodes.map((n,i)=>({node:n.id,x:25+(i%3)*270,y:40+Math.floor(i/3)*220}));
  const byId=Object.fromEntries(layout.map(n=>[n.node,n]));
  const evs=eventsForAttempt(), observed=new Set();const eventById=Object.fromEntries(view.events.map(e=>[e.id,e]));
  evs.forEach(e=>e.depends.forEach(d=>{const prev=eventById[d.event];if(prev&&prev.attempt===e.attempt&&(view.historical||choice!=='latest'||(current(e)&&current(prev))))observed.add(`${prev.node}:${e.node}`);}));
  const visible=view.model.edges.filter(e=>byId[e.from]&&byId[e.to]&&e.type!=='contains'&&(mode==='deps'?e.type!=='flow':e.type==='flow'));
  const height=Math.max(455,...layout.map(p=>p.y+185));
  const paths=visible.map(e=>{
    const a=byId[e.from],b=byId[e.to];let path,lx,ly;
    if(mode==='overview'&&e.overview_route){path=e.overview_route.path;lx=e.overview_route.x;ly=e.overview_route.y;}
    else if(a.y===b.y){const right=b.x>a.x;const x1=right?a.x+235:a.x,x2=right?b.x:b.x+235;path=`M ${x1} ${a.y+72} L ${x2} ${b.y+72}`;lx=(x1+x2)/2;ly=a.y+62;}
    else if(a.x===b.x){path=`M ${a.x+117} ${a.y+144} L ${b.x+117} ${b.y}`;lx=a.x+153;ly=(a.y+144+b.y)/2;}
    else {const right=b.x>a.x,x1=right?a.x+235:a.x,x2=right?b.x:b.x+235;path=`M ${x1} ${a.y+72} C ${(x1+x2)/2} ${a.y+72} ${(x1+x2)/2} ${b.y+72} ${x2} ${b.y+72}`;lx=(x1+x2)/2;ly=(a.y+b.y)/2+57;}
    const active=observed.has(`${e.from}:${e.to}`);
    return `<path class="edge ${active?'observed':''}" d="${esc(path)}" marker-end="url(#${active?'arrow-live':'arrow'})" data-edge="${esc(e.id)}"><title>${esc(e.label)}</title></path><text class="edge-label" x="${lx}" y="${ly}" text-anchor="middle">${esc(e.short_label||e.label)}</text>`;
  }).join('');
  $('graph').style.height=height+'px';
  $('graph').innerHTML=`<svg class="graph-edge" viewBox="0 0 835 ${height}" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#b8c8d8"/></marker><marker id="arrow-live" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#087d79"/></marker></defs>${paths}</svg>`+layout.map(p=>{
    const n=nodes[p.node],e=chosenEvent(n.id);let s=status(e),inText=e?brief(e.inputs):Object.keys(n.capture?.in||{}).join(' · '),outText=e?(e.phase==='enter'?'执行中…':brief(e.outputs)):'尚未观测';
    if(n.aggregate&&e){const c=n.aggregate,calls=evs.filter(x=>x.node===n.id&&x.parent_call_id===e.parent_call_id),good=calls.filter(x=>x.outputs[c.result_field]);inText=`候选 ${calls.length} 条 · ${c.input_field}=${e.inputs[c.input_field]}`;outText=`${c.label}=[${good.map(x=>x.outputs[c.id_field]).join(', ')}]`;if(s!=='stale')s=good.length?'observed':'failed';}
    return `<button class="node ${selected===n.id?'selected':''}" data-node="${esc(n.id)}" data-status="${s}" style="left:${p.x}px;top:${p.y}px" aria-label="${esc(n.label)} ${esc(n.source?.symbol)}"><span class="label">${esc(n.label)}<span class="badge">${({unknown:'未观测',observed:'已观测',stale:'已失效',failed:'未满足',running:'运行中'})[s]}</span></span><code>${esc(n.source?.symbol)}()</code><span class="value" title="${esc(inText)}">${esc(inText)}</span><span class="result" title="${esc(outText)}">→ ${esc(outText)}</span></button>`;
  }).join('');
  $('graph').querySelectorAll('[data-node]').forEach(b=>b.onclick=()=>selectNode(b.dataset.node));
  $('overview').classList.toggle('active',mode==='overview');$('dependencies').classList.toggle('active',mode==='deps');
  $('route-end').textContent=evs.length?`最后观测：${nodes[evs.at(-1).node]?.label || evs.at(-1).node}`:'尚未执行';
}
function fields(o){
  if(!Object.keys(o||{}).length)return '<p class="subtle">无记录</p>';
  return '<table class="fields">'+Object.entries(o).map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(val(v))}</td></tr>`).join('')+'</table>';
}
function renderInspector(){
  const n=view.model.nodes.find(n=>n.id===selected);if(!n)return;
  const e=chosenEvent(selected),binding=view.manifest.bindings[selected];
  $('node-kind').textContent=`${n.kind} · ${n.id}`;$('node-title').textContent=n.label;$('node-function').textContent=n.source?.symbol+'()';$('node-summary').textContent=n.summary;
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  if(tab==='source'){
    $('detail').innerHTML=binding?`<div class="source-head"><code>${esc(binding.path)}:${binding.line}</code><p class="subtle">加载时源码 · build ${view.manifest.build_id.slice(0,8)}</p></div><pre class="code">${binding.snippet.split('\n').map((line,i)=>`<span class="line"><span class="ln">${binding.line+i}</span>${esc(line)}</span>`).join('')}</pre><div class="detail-section"><h3>静态调用（语法证据）</h3><div class="json">${esc(binding.calls.join('\n'))}</div></div>`:'<div class="empty">没有源码绑定。</div>';
    return;
  }
  if(tab==='deps'){
    const refs=e?.depends || [];
    const runtime=refs.map(r=>{const from=view.events.find(x=>x.id===r.event);return `<button class="dep-link" data-event="${esc(r.event)}">${esc(from?.node||'缺失事件')} → ${esc(n.id)} <strong>${esc(r.type)}</strong><small>${esc(r.event)} · ${esc(from?brief(from.outputs):'观测缺口')}</small></button>`}).join('');
    const declared=view.model.edges.filter(x=>(x.to===n.id||x.from===n.id)&&x.type!=='contains').map(x=>`<button class="dep-link" data-target="${esc(x.from===n.id?x.to:x.from)}">${esc(x.from)} — ${esc(x.type)} → ${esc(x.to)}<small>${esc(x.label)} · 模型声明</small></button>`).join('');
    $('detail').innerHTML=`<div class="detail-section"><h3>本次显式事件依赖</h3>${runtime||'<p class="subtle">本次没有已记录引用。</p>'}</div><div class="detail-section"><h3>模型连接</h3>${declared}</div>`;
    bindDetail();return;
  }
  let html=n.predicate?`<div class="detail-section"><h3>判定 / 计算关系</h3><div class="predicate">${esc(n.predicate)}</div></div>`:'';
  if(e){
    html+=`<div class="detail-section"><div class="stamp"><span>${esc(e.phase)} · #${e.seq}</span><span>参数 v${e.basis.param_version} / 事实 ${e.basis.epoch}</span><span class="${!current(e)?'flag':''}">${view.historical||choice!=='latest'?'历史事实':current(e)?'与当前事实一致':'已失效'}</span></div><h3>输入</h3>${fields(e.inputs)}<h3 style="margin-top:16px">输出</h3>${fields(e.outputs)}</div>`;
  }else html+='<div class="empty">此尝试尚未观测到该节点。图中的关系仍是声明。</div>';
  if(n.candidate_table){
    const c=n.candidate_table,matches=eventsForAttempt().filter(x=>x.node===c.node&&(!e||x.parent_call_id===e.call_id));
    html+=`<div class="detail-section"><h3>${esc(c.title)}</h3>${matches.length?'<table class="grants"><tr><th>候选</th>'+c.columns.map(col=>`<th>${esc(col.label)}</th>`).join('')+'</tr>'+matches.map(m=>'<tr><td><button class="grant-link" data-event="'+esc(m.id)+'">'+esc(m.outputs[c.id_field])+'</button></td>'+c.columns.map(col=>`<td class="${m.outputs[col.field]?'yes':'no'}">${m.outputs[col.field]?'✓':'×'}</td>`).join('')+'</tr>').join('')+'</table>':'<p class="subtle">本次没有候选求值记录。</p>'}</div>`;
  }
  if(n.aggregate){
    const calls=eventsForAttempt().filter(x=>x.node===n.id),cfg=n.aggregate;
    html+=`<div class="detail-section"><h3>本次函数调用 · 点击核对每条候选</h3>${calls.map(c=>`<button class="dep-link" data-event="${esc(c.id)}">${esc(c.outputs[cfg.id_field])} · ${c.outputs[cfg.result_field]?'有效':'不满足'}<small>${esc(c.call_id)} · #${c.seq}</small></button>`).join('')}</div>`;
  }
  if(n.kind==='wait')html+=`<div class="detail-section"><h3>等待原因</h3>${(e?.inputs.reasons||[]).map(r=>`<p>${esc(n.reason_labels?.[r]||r)}</p>`).join('')}<h3>恢复条件</h3><p>${esc(n.resume||'等待条件变化后重新求值')}</p>${n.inspect_target?`<button class="inspect-action" data-target="${esc(n.inspect_target)}">查看关联判定</button>`:''}</div>`;
  html+=`<div class="detail-section"><button id="locate-source">定位源码 · ${esc(binding?.path)}:${binding?.line}</button></div>`;
  $('detail').innerHTML=html;bindDetail();$('locate-source').onclick=()=>{tab='source';renderInspector();};
}
function bindDetail(){
  $('detail').querySelectorAll('[data-event]').forEach(b=>b.onclick=()=>selectEvent(b.dataset.event));
  $('detail').querySelectorAll('[data-target]').forEach(b=>b.onclick=()=>selectNode(b.dataset.target));
}
function renderEvents(){
  $('events').innerHTML=eventsForAttempt().slice().reverse().map(e=>`<button class="event ${eventChoice===e.id?'selected':''}" data-event="${esc(e.id)}"><span>#${e.seq}</span><span>${esc(e.node)}</span><span>${esc(e.phase)}</span><span>${esc(brief(e.outputs)||'调用开始')}</span></button>`).join('')||'<div class="empty">在实验操作台执行任务，运行事件会出现在这里。</div>';
  $('events').querySelectorAll('[data-event]').forEach(b=>b.onclick=()=>selectEvent(b.dataset.event));
}
$('overview').onclick=()=>{mode='overview';renderGraph();};$('dependencies').onclick=()=>{mode='deps';renderGraph();};
$('attempt').onchange=e=>{choice=e.target.value;eventChoice=null;render();};
$('case').onchange=e=>{caseChoice=e.target.value;choice='latest';eventChoice=null;renderKey='';};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;renderInspector();});
async function poll(){
  try{
    const expectedCase=caseChoice;const response=await fetch('/api/view?case='+encodeURIComponent(expectedCase),{cache:'no-store'});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const next=await response.json();if(expectedCase!==caseChoice)return;
    const key=JSON.stringify([caseChoice,next.manifest.build_id,next.manifest.model_hash,next.model.revision,next.events.at(-1)?.id,next.authority,next.health,next.binding_status,next.busy]);
    view=next;$('connection').textContent=view.historical?'冻结现场':'● 已连接';
    if(key!==renderKey){renderKey=key;render();}
  }catch(e){$('connection').textContent='连接失败 · '+e.message;}
  finally{setTimeout(poll,400);}
}
poll();
