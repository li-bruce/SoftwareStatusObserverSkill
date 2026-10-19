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
  return entry?{...run,...entry.after,revision:entry.seq,selectedFrame:entry}:null;
}
export function selectedEvents(view,choice,step='latest'){
  const id=currentAttempt(view,choice);let events=view.events.filter(e=>e.attempt===id);
  if(step!=='latest'){
    const frame=events.filter(e=>e.node==='flow.checks'&&e.outputs.revision<=Number(step)).at(-1);
    events=frame?events.filter(e=>e.seq<=frame.seq):[];
  }
  return events;
}
export function nodeEvents(node,events){return events.filter(e=>e.node===(node.event_node||node.id));}
function activityName(view,id){return view.model.nodes.find(n=>n.id===id)?.label||id;}
function activityColor(state){return ({running:'active',waiting:'blocked',rejected:'blocked',failed:'blocked',succeeded:'ok',cancelled:'historical'})[state]||'declared';}
export function status(node,view,events,choice,configuration=null){
  if(configuration?.disposition==='interrupted'&&(node.execution_role||node.id===view.model.machine.execution?.parent))return 'historical';
  if(node.execution_role==='activity')return activityColor(configuration?.activities[node.id]);
  if(node.execution_role==='resource')return configuration?(configuration.resources[node.id].available===0?'blocked':'ok'):'declared';
  if(node.execution_role==='join')return ({waiting:'blocked',enabled:'active',passed:'ok',rejected:'blocked'})[configuration?.join.state]||'declared';
  if(node.id===view.model.machine.execution?.parent&&configuration)return Object.values(configuration.activities).includes('running')?'active':configuration.join.state==='passed'?'ok':'blocked';
  if(node.layer==='state')return node.value===(configuration?.phase||view.machine.current)?'active':'declared';
  if(node.layer==='business'){
    const states=view.model.nodes.filter(n=>n.parent===node.id&&n.layer!=='state').map(n=>status(n,view,events,choice,configuration));
    return ['active','blocked','ok','historical'].find(s=>states.includes(s))||'declared';
  }
  const last=nodeEvents(node,events).at(-1);if(!last)return 'declared';
  if(view.binding_status.status!=='current'||choice!=='latest'||last.basis.param_version!==view.authority.basis.param_version)return 'historical';
  if(last.phase==='wait'||last.phase==='error'||last.outputs.allowed===false||last.outputs.safe===false)return 'blocked';
  return last.phase==='enter'?'active':'ok';
}
export function lines(node,view,events,choice,configuration=null){
  const last=nodeEvents(node,events).at(-1),result=[{text:node.signature||node.source?.symbol||node.summary,role:'symbol'}];
  if(node.execution_role){
    if(!configuration){result.push({text:'这次运行尚未保存内部状态',role:'muted'});return result;}
    if(node.execution_role==='activity'){
      const state=configuration.activities[node.id];result.push({text:stateLabels[state],role:state==='waiting'||state==='failed'||state==='rejected'?'bad':'good'});
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
    result.push({text:node.value===(configuration?.phase||view.machine.current)?'这次运行的流程状态':'可到达的流程状态',role:'muted'});
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
    const vals=last?.[direction==='in'?'inputs':'outputs']||{};
    for(const [key,t] of Object.entries(spec)){
      if(!(key in vals)||key==='state')continue;
      result.push({text:`${direction==='in'?'参数':'返回'} ${key}: ${typeName(t)} = ${compact(vals[key])}`,role:vals[key]===false?'bad':'value'});
    }
  }
  if(!last&&!node.execution_role)result.push({text:'没有记录这次调用；可展开查看代码',role:'muted'});
  return result;
}
export function wrapText(text,width=47){const out=[];let row='',units=0;for(const c of text){const size=c.charCodeAt(0)>255?1.8:1;if(c==='\n'||units+size>width){out.push(row);row='';units=0;if(c==='\n')continue;}row+=c;units+=size;}if(row||!out.length)out.push(row);return out;}
export function layoutGraph(view,expanded,sourceOpen,fullSources,choice,step='latest'){
  const configuration=selectedConfiguration(view,choice,step),events=selectedEvents(view,choice,step),all=new Map(view.model.nodes.map(n=>[n.id,n])),children=new Map();
  for(const n of all.values())if(n.parent&&!(view.model.machine.execution&&n.layer==='state')){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
  const boxes=[],byId=new Map(),base=340;
  function measure(id){
    const n=all.get(id),kids=children.get(id)||[],open=expanded.has(id)&&kids.length;
    const rows=lines(n,view,events,choice,configuration).flatMap(r=>wrapText(r.text).map(text=>({...r,text})));
    const item={id,node:n,rows,open,kids:[],state:status(n,view,events,choice,configuration),w:base,h:55+rows.length*19+35};
    if(open){
      item.kids=kids.map(measure);const cw=Math.max(base,...item.kids.map(x=>x.w));
      const count=item.kids.length>1?2:1;item.w=count*cw+(count-1)*80+40;
      let y=item.h+28;for(let i=0;i<item.kids.length;i+=count){const row=item.kids.slice(i,i+count);for(let j=0;j<row.length;j++){row[j].rx=20+j*(cw+80);row[j].ry=y;}y+=Math.max(...row.map(c=>c.h))+66;}item.h=y+8;
    }
    if(sourceOpen.has(id)){
      const binding=view.manifest.bindings[id];
      const raw=fullSources.get(id)||binding?.snippet||'没有保存这段源码';
      const start=fullSources.has(id)?1:binding?.line||1;
      item.code=raw.split('\n').flatMap((s,i)=>wrapText(`${start+i}  ${s}`,80));
      item.codeY=item.h+8;item.w=Math.max(item.w,690);item.h+=item.code.length*18+66;
    }
    return item;
  }
  const roots=(view.model.graph_roots||view.model.overview.map(x=>x.node)).map(measure);
  // A stable two-row route leaves room to unfold a local subgraph without replacing context.
  const positions=[[0,0],[1,0],[2,0],[2,1],[1,1]],colWidths=[360,360,360],rowHeights=[0,0];
  roots.forEach((r,i)=>{const [c,row]=positions[i]||[i,0];colWidths[c]=Math.max(colWidths[c]||0,r.w);rowHeights[row]=Math.max(rowHeights[row]||0,r.h);});
  function place(item,x,y){item.x=x;item.y=y;boxes.push(item);byId.set(item.id,item);for(const c of item.kids)place(c,x+c.rx,y+c.ry);}
  roots.forEach((r,i)=>{const [c,row]=positions[i]||[i,0];place(r,55+colWidths.slice(0,c).reduce((a,b)=>a+b+190,0),45+(row?rowHeights[0]+170:0));});
  function visible(id){let n=all.get(id);while(n&&!byId.has(n.id))n=all.get(n.parent);return n?.id;}
  const edgeMap=new Map();
  const evById=new Map(view.events.map(e=>[e.id,e]));
  const actual=new Set();
  for(const e of events)for(const d of e.depends||[]){const p=evById.get(d.event);if(p&&p.attempt===e.attempt)actual.add(p.node+'>'+e.node);}
  for(const e of view.model.edges){
    if(e.type==='contains')continue;
    const from=visible(e.from),to=visible(e.to);
    if(!from||!to||from===to)continue;
    // A hidden helper call must not look like a business or resource dependency.
    if(e.origin==='python-ast'&&(from!==e.from||to!==e.to))continue;
    const key=from+'>'+to;
    const source=all.get(e.from),target=all.get(e.to),sourceEvents=nodeEvents(source,events),targetEvents=nodeEvents(target,events);
    const sourceIds=new Set(sourceEvents.map(x=>x.id));
    let observed=targetEvents.some(x=>(x.depends||[]).some(d=>sourceIds.has(d.event)));
    // Do not infer a true branch from mere adjacency or another guard reference.
    if(e.type==='flow')observed=observed&&targetEvents.length>0;
    if(!sourceEvents.length&&!targetEvents.length)observed=false;
    const last=sourceEvents.at(-1);
    const field=e.field||e.label;
    const value=last?.outputs?.[field]??last?.inputs?.[field];
    let label=e.label+(value!==undefined?` = ${compact(value)}`:'');
    if(configuration&&e.type==='resource'){
      const state=configuration.activities[e.to];observed=state!=='pending';
      label=state==='running'?'正在占用 '+e.units+' 个名额':state==='waiting'?'名额已用完，正在等待':['succeeded','failed','rejected'].includes(state)?'检查结束，名额已归还':e.label;
    }
    if(configuration&&e.type==='join'){
      const state=configuration.activities[e.from];observed=['succeeded','failed','rejected'].includes(state);
      label=state==='succeeded'?'这项检查已通过':state==='failed'?'检查出错，不能提交':state==='rejected'?'这项检查未通过':'等待这项检查结束';
    }
    const current=!!configuration&&['resource','join'].includes(e.type)||choice==='latest'&&view.binding_status.status==='current'&&sourceEvents.at(-1)?.basis.epoch===view.authority.basis.epoch&&sourceEvents.at(-1)?.basis.clock===view.authority.basis.clock;
    if(edgeMap.has(key)){const found=edgeMap.get(key);found.labels.add(label);if(observed){found.current=found.observed?found.current&&current:current;found.observed=true;}}
    else edgeMap.set(key,{...e,from,to,labels:new Set([label]),observed,current});
  }
  return {boxes,byId,edges:[...edgeMap.values()],events,children,all,width:Math.max(...boxes.map(b=>b.x+b.w))+65,height:Math.max(...boxes.map(b=>b.y+b.h))+65};
}
export function layoutMachine(view,choice,sourceOpen=new Set(),fullSources=new Map(),step='latest'){
  const def=view.model.machine,configuration=selectedConfiguration(view,choice,step),values=def.values,boxes=[],byId=new Map();
  const positions=view.model.machine_layout||{};
  for(const [i,v] of values.entries()){const [x,y]=(view.model.machine_layout||positions)[v]||[i%3,Math.floor(i/3)],node={id:'state.'+v,label:def.labels[v],kind:'state',layer:'state',value:v,source:def.source};
    const rows=lines(node,view,selectedEvents(view,choice,step),choice,configuration);
    for(const t of def.transitions){const sources=Array.isArray(t.source)?t.source:[t.source];if(view.model.presentation.inline_machine_events?.includes(t.trigger)&&sources.some(s=>s===v||v.startsWith(s+'_')))rows.push({text:t.trigger+' → '+(t.dest||'保持状态'),role:'muted'});}
    const b={id:node.id,node,x:60+x*540,y:50+y*310,w:340,h:90+rows.length*19,rows,state:v===(configuration?.phase||view.machine.current)?'active':'declared',kids:[]};
    if(sourceOpen.has(b.id)){const binding=view.manifest.bindings[b.id];const raw=fullSources.get(b.id)||binding?.snippet||'';b.code=raw.split('\n').flatMap((s,i)=>wrapText(`${(fullSources.has(b.id)?1:binding?.line||1)+i}  ${s}`,80));b.codeY=b.h+8;b.w=690;b.h+=70+b.code.length*18;}
    boxes.push(b);byId.set(b.id,b);}
  const widths=[340,340,340],heights=[];
  boxes.forEach((b,i)=>{const [c,r]=positions[b.node.value]||[i%3,Math.floor(i/3)];widths[c]=Math.max(widths[c],b.w);heights[r]=Math.max(heights[r]||0,b.h);});
  boxes.forEach((b,i)=>{const [c,r]=positions[b.node.value]||[i%3,Math.floor(i/3)];b.x=60+widths.slice(0,c).reduce((a,w)=>a+w+200,0);b.y=50+heights.slice(0,r).reduce((a,h)=>a+h+140,0);});
  const edges=[];
  for(const t of def.transitions){
    const sources=Array.isArray(t.source)?t.source:[t.source];
    for(const s of sources)for(const v of values.filter(v=>v===s||v.startsWith(s+'_'))){
      const to=t.dest||v,guard=[...(Array.isArray(t.conditions)?t.conditions:t.conditions?[t.conditions]:[]),...(t.unless?['!'+t.unless]:[])].join(' && ');
      const attempt=currentAttempt(view,choice);
      const seen=view.machine.journal.some(j=>j.event===t.trigger&&j.source===v&&j.target===to&&j.attempt===attempt);
      if(view.model.presentation.inline_machine_events?.includes(t.trigger)&&!seen)continue;
      edges.push({id:t.trigger+':'+v,from:'state.'+v,to:'state.'+to,type:'transition',labels:new Set([(def.event_labels?.[t.trigger]||t.trigger)+(guard?'（本次检查全部通过）':'')]),observed:seen,current:choice==='latest',event:t.trigger});
    }
  }
  return {boxes,byId,edges,events:selectedEvents(view,choice),children:new Map(),width:Math.max(...boxes.map(b=>b.x+b.w))+50,height:Math.max(...boxes.map(b=>b.y+b.h))+50};
}
