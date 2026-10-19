// Pure graph projection. Containment, dependency and execution evidence remain separate.
export const colors = {ink:0x30454d,muted:0x7d8e96,line:0xb6c7cc,green:0x208b73,orange:0xbc8739,blue:0x477b9c,white:0xffffff};
export function compact(v){if(v===undefined)return '—';if(typeof v==='string')return v;return JSON.stringify(v);}
export function typeName(t){if(Array.isArray(t))return `list[${typeName(t[0])}]`;if(typeof t==='object')return 'record';return ({number:'number',string:'str',boolean:'bool'})[t]||t;}
export function executionIds(view){return [...new Set(view.events.filter(e=>e.node==='read').map(e=>e.attempt))];}
export function selectedEvents(view,choice){const id=choice==='latest'?executionIds(view).at(-1):choice;return view.events.filter(e=>e.attempt===id);}
export function nodeEvents(node,events){let found=events.filter(e=>e.node===(node.event_node||node.id));if(node.event_stage){found=found.filter(e=>e.inputs?.stage===node.event_stage);}if(node.call_stage){found=found.filter(e=>(e.parent_call_id||e.call_id||'').includes(':'+node.call_stage+':authorize'));}return found;}
export function status(node,view,events,choice){
  if(node.layer==='business'){
    const kids=view.model.nodes.filter(n=>n.parent===node.id&&n.layer!=='state');
    const states=kids.map(n=>status(n,view,events,choice));
    return ['active','blocked','ok','historical'].find(s=>states.includes(s))||'declared';
  }
  if(node.layer==='state')return choice==='latest'&&node.value===view.machine.current?'active':'declared';
  const list=nodeEvents(node,events),last=list.at(-1);
  if(!last)return 'declared';
  if(view.binding_status.status!=='current'||choice!=='latest'||last.basis.epoch!==view.authority.basis.epoch||last.basis.clock!==view.authority.basis.clock||last.basis.param_version!==view.authority.basis.param_version)return 'historical';
  if(node.field){const vals=list.map(e=>e.outputs[node.field]);return vals.some(Boolean)?'ok':'blocked';}
  if(last.phase==='error')return 'blocked';
  if(node.aggregate)return list.some(e=>e.outputs[node.aggregate.result_field])?'ok':'blocked';
  if(last.phase==='wait'||last.outputs.allowed===false)return 'blocked';
  if(last.phase==='enter')return 'active';
  return 'ok';
}
export function lines(node,view,events,choice){
  const list=nodeEvents(node,events),last=list.at(-1),result=[];
  const kind={action:'动作',function:'函数',decision:'判定',effect:'提交',state:'状态',data:'数据',wait:'等待'}[node.kind]||node.kind;
  result.push({text:node.source?.symbol||node.summary,role:'symbol'});
  if(node.layer==='state'){
    result.push({text:`Phase: enum = ${node.value}`,role:'value'});
    result.push({text:choice==='latest'&&node.value===view.machine.current?'● 当前持久化状态':'声明的状态值',role:'muted'});
    return result;
  }
  if(node.layer==='business'){
    result.push({text:node.summary,role:'muted'});
    const group=node.summary_nodes||view.model.nodes.filter(n=>n.parent===node.id&&n.kind!=='state').map(n=>n.event_node||n.id);
    for(const id of group){const e=events.filter(e=>e.node===id).at(-1);if(e){for(const [k,v] of Object.entries(e.outputs||{}).slice(0,4))result.push({text:`${k} = ${compact(v)}`,role: v===false?'bad':'value'});}}
    if(!events.length)result.push({text:'尚未执行 · 展开查看程序结构',role:'muted'});
    return result;
  }
  if(node.field){
    result.push({text:node.predicate,role:'muted'});
    if(list.length)for(const e of list){
      for(const k of node.field_inputs||[])result.push({text:`${e.outputs.id} · ${k} = ${compact(e.inputs[k])}`,role:'value'});
      result.push({text:`${e.outputs.id} → ${node.field}: bool = ${e.outputs[node.field]}`,role:e.outputs[node.field]?'good':'bad'});
    }
    else result.push({text:`${node.field}: bool = 未观测`,role:'muted'});
    return result;
  }
  if(node.aggregate&&list.length){
    result.push({text:'单条 ALL / 候选 ANY',role:'muted'});
    result.push({text:`ANY ${node.aggregate.result_field}: bool = ${list.some(e=>e.outputs[node.aggregate.result_field])}`,role:list.some(e=>e.outputs[node.aggregate.result_field])?'good':'bad'});
    for(const e of list){const failing=Object.entries(e.outputs).filter(([k,v])=>typeof v==='boolean'&&!v&&k!==node.aggregate.result_field).map(([k])=>k);const ok=e.outputs[node.aggregate.result_field];result.push({text:`${e.outputs[node.aggregate.id_field]}: ${node.aggregate.result_field} = ${ok} ${failing.length?'· '+failing.join(', '):''}`,role:ok?'good':'bad'});}
  }
  const machineContext=view.model.machine.context;
  for(const [direction,spec] of Object.entries(node.snapshot_fields?{}:node.capture||{})){
    const vals=last?.[direction==='in'?'inputs':'outputs']||{};
    for(const [key,t] of Object.entries(spec).filter(([k])=>(k in vals||!last)&&(!node.inline_fields||node.inline_fields.includes(k)))){
      const type=machineContext[key]?.type==='integer'?'int':machineContext[key]?.type==='enum'?'enum['+machineContext[key].values.join('|')+']':typeName(t);
      const value=key==='grants'&&Array.isArray(vals[key])?`${vals[key].length} 条候选`:compact(vals[key]);
      result.push({text:`${direction==='in'?'←':'→'} ${key}: ${type} = ${value}`,role:vals[key]===false?'bad':'value'});
    }
  }
  if(node.snapshot_fields){
    const read=events.find(e=>e.node===node.snapshot_fields.event_node);
    for(const [k,v] of Object.entries(read?.outputs||(!events.length?view.authority.parameters:{})).filter(([k])=>k in machineContext)){const spec=machineContext[k];result.push({text:`${k}: ${spec.type} = ${compact(v)} ${spec.values?'['+spec.values.join('|')+']':spec.min!==undefined?'['+spec.min+'..'+(spec.max??'∞')+']':''}`,role:'value'});}
  }
  if(last)result.push({text:`#${last.seq} · ${last.phase} · v${last.basis.param_version} · ${choice==='latest'?'本次执行':'历史执行'}`,role:'muted'});
  else result.push({text:`${kind} · 尚未观测`,role:'muted'});
  return result;
}
export function wrapText(text,width=47){
  const out=[];let row='',units=0;
  for(const c of text){const size=c.charCodeAt(0)>255?1.8:1;if(c==='\n'||units+size>width){out.push(row);row='';units=0;if(c==='\n')continue;}row+=c;units+=size;}
  if(row||!out.length)out.push(row);return out;
}
export function layoutGraph(view,expanded,sourceOpen,fullSources,choice){
  const events=selectedEvents(view,choice),all=new Map(view.model.nodes.map(n=>[n.id,n])),children=new Map();
  for(const n of all.values())if(n.parent){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
  const boxes=[],byId=new Map(),base=340;
  function measure(id){
    const n=all.get(id),kids=children.get(id)||[],open=expanded.has(id)&&kids.length;
    const rows=lines(n,view,events,choice).flatMap(r=>wrapText(r.text).map(text=>({...r,text})));
    const item={id,node:n,rows,open,kids:[],state:status(n,view,events,choice),w:base,h:55+rows.length*19+35};
    if(open){
      item.kids=kids.map(measure);const cw=Math.max(base,...item.kids.map(x=>x.w));
      const count=item.kids.length>1?2:1;item.w=count*cw+(count-1)*80+40;
      let y=item.h+28;for(let i=0;i<item.kids.length;i+=count){const row=item.kids.slice(i,i+count);for(let j=0;j<row.length;j++){row[j].rx=20+j*(cw+80);row[j].ry=y;}y+=Math.max(...row.map(c=>c.h))+66;}item.h=y+8;
    }
    if(sourceOpen.has(id)){
      const binding=view.manifest.bindings[id];
      const raw=fullSources.get(id)||binding?.snippet||'No captured source';
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
    const label=e.label+(value!==undefined?` = ${compact(value)}`:'');
    const current=choice==='latest'&&view.binding_status.status==='current'&&sourceEvents.at(-1)?.basis.epoch===view.authority.basis.epoch&&sourceEvents.at(-1)?.basis.clock===view.authority.basis.clock;
    if(edgeMap.has(key)){const found=edgeMap.get(key);found.labels.add(label);if(observed){found.current=found.observed?found.current&&current:current;found.observed=true;}}
    else edgeMap.set(key,{...e,from,to,labels:new Set([label]),observed,current});
  }
  return {boxes,byId,edges:[...edgeMap.values()],events,children,all,width:Math.max(...boxes.map(b=>b.x+b.w))+65,height:Math.max(...boxes.map(b=>b.y+b.h))+65};
}
export function layoutMachine(view,choice,sourceOpen=new Set(),fullSources=new Map()){
  const def=view.model.machine,values=def.values,boxes=[],byId=new Map();
  const positions=view.model.machine_layout||{};
  for(const [i,v] of values.entries()){const [x,y]=(view.model.machine_layout||positions)[v]||[i%3,Math.floor(i/3)],node={id:'state.'+v,label:def.labels[v],kind:'state',layer:'state',value:v,source:def.source};
    const rows=[{text:`Phase = ${v}`,role:'value'},{text:choice==='latest'&&v===view.machine.current?'● 当前持久化状态':'声明',role:'muted'}];
    for(const t of def.transitions){const sources=Array.isArray(t.source)?t.source:[t.source];if(view.model.presentation.inline_machine_events?.includes(t.trigger)&&sources.some(s=>s===v||v.startsWith(s+'_')))rows.push({text:t.trigger+' → '+(t.dest||'保持状态'),role:'muted'});}
    const b={id:node.id,node,x:60+x*540,y:50+y*310,w:340,h:90+rows.length*19,rows,state:choice==='latest'&&v===view.machine.current?'active':'declared',kids:[]};
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
      const attempt=choice==='latest'?executionIds(view).at(-1):choice;
      const seen=view.machine.journal.some(j=>j.event===t.trigger&&j.source===v&&j.target===to&&j.attempt===attempt);
      if(view.model.presentation.inline_machine_events?.includes(t.trigger)&&!seen)continue;
      edges.push({id:t.trigger+':'+v,from:'state.'+v,to:'state.'+to,type:'transition',labels:new Set([t.trigger+(guard?' ['+guard+']':'')]),observed:seen,current:choice==='latest',event:t.trigger});
    }
  }
  return {boxes,byId,edges,events:selectedEvents(view,choice),children:new Map(),width:Math.max(...boxes.map(b=>b.x+b.w))+50,height:Math.max(...boxes.map(b=>b.y+b.h))+50};
}
