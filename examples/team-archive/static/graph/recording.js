// Read-only replay. This module has no business-command endpoint.
import {applyRuntimeFrame} from './runtime-frames.js';
const copy=value=>structuredClone(value);
const millis=value=>Number.isFinite(Date.parse(value))?Date.parse(value):0;
export function timeline(recording){
  const items=[
    ...recording.events.map(e=>({...e,kind:'probe'})),
    ...recording.commands.map(e=>({...e,kind:'command'})),
  ].sort((a,b)=>millis(a.observed_at)-millis(b.observed_at)||(a.seq??Infinity)-(b.seq??Infinity));
  return [{kind:'start',id:'start',observed_at:recording.started_at},...items,
    ...(recording.status!=='recording'?[{kind:'end',id:'end',observed_at:recording.ended_at}]:[])];
}
export function frame(recording,index,items=timeline(recording)){
  index=Math.max(0,Math.min(items.length-1,index));
  const item=items[index],view=copy(recording.context),known=items.slice(0,index+1).filter(e=>e.kind==='probe');
  view.events.push(...known);
  view.historical=true;view.replay={id:recording.id,index,event:item,gaps:recording.gaps};
  view.binding_status={status:'current',scope:'recorded sources'};
  view.busy=false;
  if(item.kind==='end'){
    Object.assign(view,copy(recording.final));view.binding_status={status:'current',scope:'recorded sources'};
    view.historical=true;
    return view;
  }
  if(!known.length)return view;
  const last=known.at(-1),parent=view.model.machine.execution?.parent;
  if(applyRuntimeFrame(recording,last,view))return view;
  view.authority.parameters.attempt=last.attempt;
  view.authority.parameters.param_version=last.basis?.param_version;
  view.authority.basis=copy(last.basis||{});
  for(const [key,binding] of Object.entries(view.model.presentation?.replay_parameters||{})){
    const actual=known.filter(e=>e.node===binding.node&&e.attempt===last.attempt&&
      Object.hasOwn(e[binding.direction==='in'?'inputs':'outputs']||{},binding.field)).at(-1);
    if(actual&&Object.hasOwn(view.authority.parameters,key))
      view.authority.parameters[key]=copy(actual[binding.direction==='in'?'inputs':'outputs'][binding.field]);
  }
  // Only a matching probe revision proves an internal configuration.
  const configurations=new Map((view.machine.configurations||[]).map(c=>[c.attempt,c]));
  const finalConfigs=new Map((recording.final.machine.configurations||[]).map(c=>[c.attempt,c]));
  for(const e of known){
    if(e.node!==parent||!Number.isInteger(e.outputs?.revision))continue;
    const original=finalConfigs.get(e.attempt),entry=original?.journal?.find(j=>j.seq===e.outputs.revision);
    if(!entry)continue;
    configurations.set(e.attempt,{attempt:e.attempt,param_version:e.basis?.param_version,
      ...copy(entry.after),phase:e.outputs.phase??entry.phase??null,revision:entry.seq,
      journal:copy(original.journal.filter(j=>j.seq<=entry.seq)),
      qualification:{},source_status:'current',run_build_id:recording.build_id});
  }
  view.machine.configurations=[...configurations.values()];
  const configuration=configurations.get(last.attempt);
  const capacities=Object.values(configuration?.resources||{}).map(r=>r.capacity);
  if(capacities.length===1)view.authority.parameters.capacity=capacities[0];
  view.machine.current=configuration?.phase??null;
  view.authority.state=view.machine.current;
  const boundary=millis(item.observed_at)/1000;
  // Wall-clock journals are usable only up to the captured event and revision.
  // Logical/simulated clocks are not silently compared to browser time.
  view.machine.journal=(recording.final.machine.journal||[]).filter(j=>
    j.clock>1e9&&j.clock<=boundary&&configurations.has(j.attempt)&&
    j.activity_revision!=null&&j.activity_revision<=configurations.get(j.attempt).revision);
  const phase=view.machine.journal.filter(j=>j.attempt===last.attempt).at(-1);
  if(phase){view.machine.current=phase.target;view.authority.state=phase.target;if(configuration)configuration.phase=phase.target;}
  return view;
}
export function eventLabel(item,model){
  if(item.kind==='start')return '记录开始 · 初始状态';
  if(item.kind==='end')return '记录结束 · 最后保存的状态';
  const label=model.nodes.find(n=>n.id===item.node)?.label||item.node||item.action;
  if(item.kind==='command')return `操作 ${item.action} · ${item.status==='error'?'失败':'已返回'} · ${label}`;
  const phases={enter:'开始执行',return:'返回结果',decision:'完成判断',change:'状态改变',wait:'等待',error:'执行出错',commit:'写入完成',read:'读取参数'};
  return `${label} · ${phases[item.phase]||item.phase}`;
}
export function transferEdges(event,events,edges,all,configuration=null){
  if(!event||event.kind==='command'||!event.node)return [];
  const dependencies=new Set((event.depends||[]).map(d=>d.event));
  const prior=events.filter(e=>dependencies.has(e.id));
  const parent=event.parent_call_id&&events.find(e=>e.call_id===event.parent_call_id&&e.attempt===event.attempt&&e.run_id===event.run_id);
  if(parent)prior.push(parent);
  const canonical=id=>all.get(id)?.referenceOf||all.get(id)?.event_node||id;
  const activityFrame=Number.isInteger(event.outputs?.revision)?
    configuration?.journal?.find(j=>j.seq===event.outputs.revision):null;
  return edges.filter(edge=>edge.type!=='shared'&&edge.members?.some(member=>{
    const source=canonical(member.from),target=canonical(member.to);
    if(activityFrame?.event==='start'&&edge.type==='resource'&&target===activityFrame.activity)
      return activityFrame.after.resources?.[source]?.holders?.includes(target);
    if(activityFrame?.activity===target&&edge.type==='resource'&&
       activityFrame.before?.resources?.[source]?.holders?.includes(target))
      return !activityFrame.after.resources?.[source]?.holders?.includes(target);
    if(activityFrame?.activity&&edge.type==='join'&&source===activityFrame.activity&&
       activityFrame.before?.activities[source]!==activityFrame.after.activities[source])
      return ['succeeded','failed','rejected'].includes(activityFrame.after.activities[source]);
    if(member.origin==='capture-field')return event.node===canonical(member.from)&&event.node===canonical(member.to)&&
      (all.get(member.from)?.field?Object.hasOwn(event.inputs||{},all.get(member.from).field):Object.hasOwn(event.outputs||{},all.get(member.to)?.field));
    if(edge.type==='call')return target===event.node&&parent?.node===source;
    return member.origin!=='python-ast'&&target===event.node&&prior.some(e=>e.node===source&&
      (event.depends||[]).some(d=>d.event===e.id&&d.type===edge.type));
  })).map(e=>e.id);
}
export async function recordingRequest(path,body){
  const response=await fetch('/api/recordings'+path,body===undefined?{cache:'no-store'}:
    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok)throw Error(value.message||value.error||'记录请求失败');
  return value;
}
