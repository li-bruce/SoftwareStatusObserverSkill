// Business groups, internal activity states and local source share one graph.
export const colors={ink:0x30454d,muted:0x7d8e96,line:0xb6c7cc,green:0x208b73,orange:0xbc8739,blue:0x477b9c,white:0xffffff};
export const stateLabels={pending:'尚未开始',waiting:'等待可用名额',running:'正在执行',succeeded:'已通过',rejected:'未通过',failed:'执行出错',cancelled:'已取消'};
export function compact(v){if(v===undefined)return '—';if(typeof v==='string')return v;return JSON.stringify(v);}
export function typeName(t){if(Array.isArray(t))return `list[${typeName(t[0])}]`;if(typeof t==='object')return 'record';return ({number:'number',string:'str',boolean:'bool'})[t]||t;}
export function configurations(view){return view.machine.configurations||view.authority.parameters.executions||[];}
export function executionIds(view){const runs=configurations(view);return runs.length?runs.map(x=>x.attempt):[...new Set(view.events.filter(e=>e.node==='read').map(e=>e.attempt))];}
export function currentAttempt(view,choice){return choice==='latest'?(view.authority.parameters.attempt||executionIds(view).at(-1)):choice;}
export function selectedConfiguration(view,choice='latest',step='latest'){
  const run=configurations(view).find(r=>r.attempt===currentAttempt(view,choice));if(!run)return null;
  if(step==='latest')return run;
  const entry=run.journal.find(e=>String(e.seq)===String(step));
  // Use only facts recorded in this frame, never the run's final disposition.
  return entry?{attempt:run.attempt,param_version:run.param_version,
    run_build_id:run.run_build_id,source_status:run.source_status,...entry.after,
    phase:entry.after.phase??entry.phase??null,revision:entry.seq,
    discarded:entry.discarded||[],wait_reasons:entry.wait_reasons||{},selectedFrame:entry}:null;
}
export function selectedEvents(view,choice,step='latest'){
  const id=currentAttempt(view,choice);let events=view.events.filter(e=>e.attempt===id);
  if(step!=='latest'){
    // First recorded boundary for this exact frame. Later reevaluations can share
    // the same activity revision; they must never leak into an earlier view.
    const parent=view.model.machine.execution?.parent;
    const frame=events.find(e=>e.node===parent&&e.outputs?.revision===Number(step));
    events=frame?events.filter(e=>e.seq<=frame.seq):[];
  }
  return events;
}
export function sourceBinding(view,all,id){
  const direct=view?.manifest.bindings[id];if(direct)return direct;
  const node=all?.get(id);
  return node?.field?view?.manifest.bindings[node.event_node||node.parent]:undefined;
}
export function nodeEvents(node,events){return events.filter(e=>e.node===(node.event_node||node.id));}
export function callValues(node,events){
  const calls=nodeEvents(node,events),last=calls.at(-1);
  if(!last)return {inputs:{},outputs:{}};
  const keys=['call_id','run_id','attempt','entity','build_id','model_revision'];
  // Legacy attempt:node IDs are not unique calls; never merge their fields.
  const identified=keys.every(k=>typeof last[k]==='string'&&last[k])&&last.call_id!==`${last.attempt}:${last.node}`;
  const same=identified?calls.filter(e=>keys.every(k=>e[k]===last[k])&&e.basis?.param_version===last.basis?.param_version):[last];
  return same.reduce((values,e)=>({inputs:{...values.inputs,...e.inputs},outputs:{...values.outputs,...e.outputs}}),{inputs:{},outputs:{}});
}
function activityName(view,id){return view.model.nodes.find(n=>n.id===id)?.label||id;}
function activityColor(state){return ({running:'active',waiting:'blocked',rejected:'blocked',failed:'blocked',succeeded:'ok',cancelled:'historical'})[state]||'declared';}
function phaseValue(view,configuration,choice){return configuration?.selectedFrame?configuration.phase:choice==='latest'?view.machine.current:configuration?.phase;}
export function status(node,view,events,choice,configuration=null){
  if(configuration?.source_status==='unbound')return 'historical';
  if(configuration?.disposition==='interrupted'&&(node.execution_role||node.id===view.model.machine.execution?.parent))return 'historical';
  if(node.execution_role==='activity')return configuration?.discarded?.includes(node.id)?'historical':activityColor(configuration?.activities[node.id]);
  if(node.execution_role==='resource')return configuration?(configuration.resources[node.id].available===0?'blocked':'ok'):'declared';
  if(node.execution_role==='join')return ({waiting:'blocked',enabled:'active',passed:'ok',rejected:'blocked'})[configuration?.join.state]||'declared';
  if(node.id===view.model.machine.execution?.parent&&configuration)return Object.values(configuration.activities).includes('running')?'active':configuration.join.state==='passed'?'ok':'blocked';
  if(node.layer==='state')return node.value===phaseValue(view,configuration,choice)?'active':'declared';
  if(node.field){const values=callValues(node,events)[node.direction==='in'?'inputs':'outputs'];if(!(node.field in values))return 'declared';}
  if(node.layer==='business'){
    const states=view.model.nodes.filter(n=>n.parent===node.id&&n.layer!=='state').map(n=>status(n,view,events,choice,configuration));
    return ['active','blocked','ok','historical'].find(s=>states.includes(s))||'declared';
  }
  const last=nodeEvents(node,events).at(-1);if(!last)return 'declared';
  if(view.binding_status.status!=='current'||choice!=='latest'||view.historical||configuration?.selectedFrame||last.basis.param_version!==view.authority.basis.param_version)return 'historical';
  if(node.kind==='decision'&&(last.basis.epoch!==view.authority.basis.epoch||
      (configuration?.qualification?.valid_until!=null&&view.authority.basis.clock>=configuration.qualification.valid_until)))return 'historical';
  if(last.phase==='wait'||last.phase==='error'||last.outputs.allowed===false||last.outputs.safe===false)return 'blocked';
  return last.phase==='enter'?'active':'ok';
}
export function lines(node,view,events,choice,configuration=null){
  if(node.field){const values=callValues(node,events)[node.direction==='in'?'inputs':'outputs'];return [{text:node.field+': '+typeName(node.fieldType),role:'symbol'},{text:node.field in values?compact(values[node.field]):'本次尚未采集',role:node.field in values?'value':'muted'}];}
  const last=nodeEvents(node,events).at(-1),result=[{text:node.signature||node.source?.symbol||node.summary,role:'symbol'}];
  if(node.id==='lifecycle'){
    const phase=phaseValue(view,configuration,choice);
    result.push({text:phase?view.model.machine.labels[phase]:'尚无运行',role:'value'});
    result.push({text:'展开查看本程序的实际状态迁移',role:'muted'});return result;
  }
  if(node.execution_role){
    if(!configuration){result.push({text:'这次运行尚未保存内部状态',role:'muted'});return result;}
    if(node.execution_role==='activity'){
      const state=configuration.activities[node.id];result.push({text:configuration.discarded?.includes(node.id)?'已作废，不再启动':stateLabels[state],role:state==='waiting'||state==='failed'||state==='rejected'?'bad':'good'});
      if(configuration.wait_reasons?.[node.id])result.push({text:configuration.wait_reasons[node.id],role:'muted'});
      if(configuration.disposition==='interrupted')result[result.length-1]={text:'执行已中断；最后记录为「'+stateLabels[state]+'」',role:'muted'};
      result.push({text:`state: ${view.model.machine.execution.activity_state_type||'str'} = ${state}`,role:'value'});
      if(node.id==='privacy')result.push({text:'检查文本是否含有 SECRET: 标记',role:'muted'});
    }else if(node.execution_role==='resource'){
      const r=configuration.resources[node.id];result.push({text:(configuration.disposition==='interrupted'?'中断前：':'')+`可用 ${r.available} / 共 ${r.capacity} 个名额`,role:r.available?'good':'bad'});
      result.push({text:`available: int = ${r.available}`,role:'value'});
      result.push({text:r.holders.length?'正在占用：'+r.holders.map(x=>activityName(view,x)).join('、'):'没有检查占用名额',role:'muted'});
      return result;
    }else{
      const j=configuration.join;result.push({text:({waiting:'还有检查未完成',enabled:'检查已结束，正在确认结果',passed:'两项检查均已通过',rejected:'检查未全部通过，不能提交'})[j.state],role:j.state==='passed'?'good':'bad'});
      if(j.pending.length)result.push({text:'仍需等待：'+j.pending.map(x=>activityName(view,x)).join('、'),role:'muted'});
      result.push({text:'两项结果都通过，才进入「可以提交」',role:'muted'});return result;
    }
  }else if(node.layer==='state'){
    result.push({text:`phase: Phase = ${node.value}`,role:'value'});
    result.push({text:node.value===phaseValue(view,configuration,choice)?'这次运行的流程状态':'可到达的流程状态',role:'muted'});
    if(node.value==='checking'&&configuration){for(const [id,state] of Object.entries(configuration.activities))result.push({text:activityName(view,id)+'：'+stateLabels[state],role:state==='waiting'?'bad':'value'});}
    return result;
  }else if(node.layer==='business'){
    result.push({text:node.summary,role:'muted'});
    if(node.id===view.model.machine.execution?.parent){
      if(configuration){
        if(configuration.disposition==='interrupted')result.push({text:'这次执行已中断；下方是最后保存的状态',role:'bad'});
        for(const [id,state] of Object.entries(configuration.activities))result.push({text:activityName(view,id)+'：'+stateLabels[state],role:state==='waiting'||state==='failed'?'bad':'value'});
        for(const r of Object.values(configuration.resources))result.push({text:`本次可用名额：${r.available} / ${r.capacity}`,role:'value'});
      }else result.push({text:'尚未开始检查',role:'muted'});
    }else{
      const names={'allowed':'允许执行','version_ok':'参数版本仍有效','param_version':'参数版本','length':'文本长度','version':'已提交版本','reason':'不能继续的原因'};
      const reasons={no_current_authorization:'没有有效授权',check_rejected:'检查未全部通过',authorization_or_version_changed:'授权或参数版本已经改变',worker_error:'检查函数发生错误',process_restarted:'进程重启，原检查已中断'};
      const ids=view.model.nodes.filter(n=>n.parent===node.id&&n.layer!=='state').map(n=>n.id);
      for(const id of ids){const e=events.filter(e=>e.node===id).at(-1);if(e)for(const [k,v] of Object.entries(e.outputs).filter(([k])=>names[k]).slice(0,2))result.push({text:`${names[k]}：${v===true?'是':v===false?'否':k==='reason'?(reasons[v]||v):compact(v)}`,role:v===false?'bad':'value'});}
    }
    return result;
  }
  for(const [direction,spec] of Object.entries(node.capture||{})){
    const vals=callValues(node,events)[direction==='in'?'inputs':'outputs'];
    for(const [key,t] of Object.entries(spec)){
      if(!(key in vals)||key==='state')continue;
      result.push({text:`${direction==='in'?'参数':'返回'} ${key}: ${typeName(t)} = ${compact(vals[key])}`,role:vals[key]===false?'bad':'value'});
    }
  }
  if(!last&&!node.execution_role)result.push({text:'没有记录这次调用；可展开查看代码',role:'muted'});
  return result;
}
export function wrapText(text,width=47){const out=[];let row='',units=0;for(const c of text){const size=c.charCodeAt(0)>255?1.8:1;if(c==='\n'||units+size>width){out.push(row);row='';units=0;if(c==='\n')continue;}row+=c;units+=size;}if(row||!out.length)out.push(row);return out;}

export const nodeTypes={business:{label:'业务',glyph:'B',color:0x5075b5},function:{label:'函数',glyph:'ƒ',color:0x387c88},state:{label:'状态',glyph:'S',color:0x9869a0},decision:{label:'判断',glyph:'?',color:0xaf8029},resource:{label:'资源',glyph:'R',color:0x7b8845},data:{label:'参数',glyph:'x',color:0x627f9c},effect:{label:'结果',glyph:'✓',color:0x2d8a70},wait:{label:'等待',glyph:'…',color:0xb38442}};
export function nodeType(n){return n.layer==='business'?'business':n.kind==='state'?'state':n.execution_role==='resource'?'resource':n.kind==='decision'?'decision':n.kind==='data'?'data':n.kind==='effect'?'effect':n.kind==='wait'?'wait':'function';}

// One typed graph. Folding changes visible nodes, never their identities or facts.
// The old layoutGraph name remains for integrations; coordinates are assigned by layout.js.
export function layoutGraph(view,expanded=new Set(),_sourceOpen=new Set(),_fullSources=new Map(),choice='latest',step='latest'){
  const configuration=selectedConfiguration(view,choice,step),events=selectedEvents(view,choice,step);
  const all=new Map(view.model.nodes.map(n=>[n.id,n])),children=new Map(),rawEdges=[...view.model.edges];
  for(const n of view.model.nodes){
    if(n.layer==='business'||n.kind==='state')continue;
    for(const [direction,fields] of Object.entries(n.capture||{}))for(const [field,fieldType] of Object.entries(fields)){
      const id=`field:${n.id}:${direction}:${field}`;
      all.set(id,{id,label:field,summary:(direction==='in'?'输入参数':'返回值'),kind:'data',layer:'parameter',parent:n.id,
        field,fieldType,direction,event_node:n.event_node||n.id,origin:'capture-field'});
      rawEdges.push({id:`capture:${id}`,from:direction==='in'?id:n.id,to:direction==='in'?n.id:id,type:'data',label:direction==='in'?'输入':'返回',origin:'capture-field'});
    }
  }
  for(const value of view.model.machine.values)if(!all.has('state.'+value)){
    all.set('state.'+value,{id:'state.'+value,label:view.model.machine.labels[value],kind:'state',layer:'state',value,source:view.model.machine.source});
  }
  for(const n of all.values())if(n.parent){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
  const visibleIds=new Set(view.model.graph_roots||view.model.overview.map(x=>x.node));
  // Lifecycle states remain in this canvas, connected to their business owners.
  for(const n of all.values())if(n.kind==='state'&&(!n.parent||expanded.has(n.parent)))visibleIds.add(n.id);
  function reveal(id,seen=new Set()){
    if(seen.has(id))return;seen.add(id);
    if(expanded.has(id))for(const child of children.get(id)||[]){visibleIds.add(child);reveal(child,seen);}
  }
  for(const id of [...visibleIds])reveal(id);
  const boxes=[...visibleIds].filter(id=>all.has(id)).map((id,i)=>{
    const node=all.get(id),type=nodeType(node),rows=lines(node,view,events,choice,configuration);
    return {id,node,type,rows,open:expanded.has(id),kids:children.get(id)||[],state:status(node,view,events,choice,configuration),
      x:80+(i%5)*230,y:70+Math.floor(i/5)*180,w:190,h:type==='state'?105:135};
  });
  const byId=new Map(boxes.map(b=>[b.id,b]));
  function visible(id){const seen=new Set();let n=all.get(id);while(n&&!byId.has(n.id)){if(seen.has(n.id))return null;seen.add(n.id);n=all.get(n.parent);}return n?.id;}
  const edgeMap=new Map();
  for(const e of rawEdges){
    const from=visible(e.from),to=visible(e.to);
    if(!from||!to||from===to)continue;
    if(['python-ast','capture-field'].includes(e.origin)&&(from!==e.from||to!==e.to))continue;
    const source=all.get(e.from),target=all.get(e.to);
    if(!source||!target)continue;
    const sourceEvents=nodeEvents(source,events),targetEvents=nodeEvents(target,events),ids=new Set(sourceEvents.map(x=>x.id));
    let observed=!['python-ast','capture-field'].includes(e.origin)&&e.type!=='contains'&&targetEvents.some(x=>(x.depends||[]).some(d=>ids.has(d.event)));
    let label=e.type==='contains'?(target.kind==='state'?'涉及状态':'包含'):e.label;
    if(configuration&&e.type==='resource'){
      const state=configuration.activities[e.to];observed=!!state&&state!=='pending';
      label=state==='running'?`占用 ${e.units} 个名额`:state==='waiting'?'名额已用完，正在等待':['succeeded','failed','rejected'].includes(state)?'已归还名额':e.label;
    }
    if(configuration&&e.type==='join'){
      const state=configuration.activities[e.from];observed=['succeeded','failed','rejected'].includes(state);
      label=state==='succeeded'?'这项检查已通过':state==='failed'?'检查出错':state==='rejected'?'检查未通过':'等待这项检查结束';
    }
    const current=choice==='latest'&&view.binding_status.status==='current'&&(!sourceEvents.length||sourceEvents.at(-1)?.basis.param_version===view.authority.basis.param_version);
    // Different relation types sharing endpoints remain separate edges.
    const key=from+'>'+to+':'+e.type;
    if(edgeMap.has(key)){const found=edgeMap.get(key);found.labels.add(label);found.observed ||= observed;}
    else edgeMap.set(key,{...e,from,to,labels:new Set([label]),observed,current});
  }
  const attempt=currentAttempt(view,choice);
  for(const t of view.model.machine.transitions){
    const sources=Array.isArray(t.source)?t.source:[t.source];
    for(const source of view.model.machine.values.filter(v=>sources.some(s=>s===v||v.startsWith(s+'_')))){
      const target=t.dest||source,from='state.'+source,to='state.'+target;
      if(!byId.has(from)||!byId.has(to))continue;
      // Activity-only frames do not attest lifecycle transitions at that time.
      const observed=step==='latest'&&(view.machine.journal||[]).some(j=>j.event===t.trigger&&j.source===source&&j.target===target&&j.attempt===attempt);
      const id='transition:'+t.trigger+':'+source;
      edgeMap.set(id,{id,from,to,type:'transition',event:t.trigger,labels:new Set([view.model.machine.event_labels?.[t.trigger]||t.trigger]),observed,current:choice==='latest'});
    }
  }
  const graph={boxes,byId,edges:[...edgeMap.values()],events,configuration,children,all};
  return graphBounds(graph);
}
export function graphBounds(graph){
  const boxes=graph.boxes;
  graph.minX=boxes.length?Math.min(...boxes.map(b=>b.x))-55:0;
  graph.minY=boxes.length?Math.min(...boxes.map(b=>b.y))-55:0;
  graph.width=(boxes.length?Math.max(...boxes.map(b=>b.x+b.w)):100)-graph.minX+55;
  graph.height=(boxes.length?Math.max(...boxes.map(b=>b.y+b.h)):100)-graph.minY+55;
  return graph;
}
