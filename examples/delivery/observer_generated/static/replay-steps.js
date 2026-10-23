// Observation facts and display steps are independent. No business commands.
import {runtimeFrame,runtimeChanges} from './runtime-frames.js';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const cached=new WeakMap();
const boFieldKey=(event,direction,field)=>[event.run_id,event.entity,event.attempt,event.node,event.call_id||'unidentified',direction,field].join('|');
function boVisibleChange(change,owner,all){
  if(owner.type!=='business')return true;
  if(change.node===(owner.node.referenceOf||owner.node.event_node||owner.id))return true;
  if(['state','resource','business'].includes(change.kind))return true;
  const source=all.get(change.node);
  return source?.parent===owner.id&&((change.kind==='decision'&&['allowed','passed','reason','reasons'].includes(change.field))||source.kind==='effect');
}
export const boKinds={state:{label:'状态',color:0x9869a0},value:{label:'值',color:0x207e7d},
  decision:{label:'判断',color:0xaf8029},resource:{label:'资源',color:0x7b8845},business:{label:'业务',color:0x5075b5},call:{label:'调用',color:0x2476ad}};
export function boValue(value){return value===undefined?'未记录':typeof value==='string'?value:JSON.stringify(value);}
export function boFacts(recording,items){
  if(cached.has(recording))return cached.get(recording);
  const model=recording.context.model,nodes=new Map(model.nodes.map(n=>[n.id,n]));
  const configurations=new Map((recording.final.machine.configurations||[]).map(c=>[c.attempt,c]));
  const previous=new Map(),changes=[],phaseByAttempt=new Map();
  let priorMachine=recording.context.machine;
  for(const configuration of recording.context.machine.configurations||[])phaseByAttempt.set(configuration.attempt,configuration.phase);
  for(const event of recording.context.events||[])for(const [direction,values] of Object.entries({in:event.inputs||{},out:event.outputs||{}}))
    for(const [field,value] of Object.entries(values))previous.set(boFieldKey(event,direction,field),value);
  for(const event of items){
    const delta=[],put=(node,field,before,after,kind='value',direction=null,attempt=event.attempt)=>{
      if(same(before,after))return;
      delta.push({node,field,before,after,kind,direction,event:event.id,attempt});
    };
    if(event.kind==='probe'){
      for(const [direction,values] of Object.entries({in:event.inputs||{},out:event.outputs||{}})){
        for(const [field,value] of Object.entries(values)){
          const key=boFieldKey(event,direction,field);
          const before=previous.get(key);previous.set(key,value);
          if(['revision','activities','resources','join','phase'].includes(field)&&event.node===model.machine.execution?.parent)continue;
          put(event.node,field,before,value,event.phase==='decision'?'decision':'value',direction);
        }
      }
      const exact=runtimeFrame(recording,event);
      if(exact){
        runtimeChanges(priorMachine||{},exact.machine,model.presentation?.runtime_owner||model.machine.execution?.parent||event.node,put);
        priorMachine=exact.machine;
        for(const cfg of exact.machine.configurations||[])phaseByAttempt.set(cfg.attempt,cfg.phase);
      }else if(recording.runtime_frames)priorMachine=null;
      if(!recording.runtime_frames&&event.node===model.machine.execution?.parent&&Number.isInteger(event.outputs?.revision)){
        const entry=configurations.get(event.attempt)?.journal?.find(j=>j.seq===event.outputs.revision);
        if(entry){
          const before=entry.before||{},after=entry.after||{};
          for(const [node,value] of Object.entries(after.activities||{}))put(node,'活动',before.activities?.[node],value,'state');
          for(const [node,value] of Object.entries(after.resources||{}))for(const field of ['available','capacity','holders'])
            put(node,field,before.resources?.[node]?.[field],value[field],'resource');
          const join=model.nodes.find(n=>n.execution_role==='join');
          if(join)put(join.id,'汇合',before.join?.state,after.join?.state,'state');
          const phase=event.outputs.phase??after.phase??entry.phase;
          if(phase!==undefined){
            put(event.node,'流程',phaseByAttempt.get(event.attempt),phase,'business');
            phaseByAttempt.set(event.attempt,phase);
          }
        }
      }
    }
    if(event.kind==='end'){
      if(recording.runtime_frames)runtimeChanges(priorMachine||{},recording.final.machine,
        model.presentation?.runtime_owner||model.machine.execution?.parent,put);
      const attempt=recording.final.authority?.parameters?.attempt,phase=recording.final.machine.current;
      if(!recording.runtime_frames&&attempt&&phase!==undefined)put(model.machine.execution?.parent,'流程',phaseByAttempt.get(attempt),phase,'business');
    }
    changes.push(delta);
  }
  const value={changes,nodes};cached.set(recording,value);return value;
}
export function boOwners(all,visible){
  const shown=new Map();
  for(const b of visible){const key=b.node.referenceOf||b.node.event_node||b.id;
    if(!shown.has(key))shown.set(key,[]);shown.get(key).push(b);}
  return (id,change=null)=>{
    if(change?.direction){const field=visible.filter(b=>b.node.field===change.field&&b.node.direction===change.direction&&(b.node.event_node||b.node.parent)===id);if(field.length)return field;}
    const seen=new Set();
    while(id&&!seen.has(id)){seen.add(id);if(shown.has(id))return shown.get(id);id=all.get(id)?.parent;}
    return [];
  };
}
export function boStepPlan(recording,items,all,visible,{mode='view'}={}){
  const facts=boFacts(recording,items),owners=boOwners(all,visible),plan=[0];
  const stateNodes=visible.filter(b=>b.type==='state');
  for(let i=1;i<items.length;i++){
    const event=items[i],delta=facts.changes[i];
    if(event.kind==='end'){plan.push(i);continue;}
    if(mode==='events'){plan.push(i);continue;}
    const direct=owners(event.node),node=all.get(event.node);
    const changed=delta.some(c=>owners(c.node,c).some(b=>boVisibleChange(c,b,all)))||
      delta.some(c=>c.kind==='business'&&stateNodes.some(b=>b.node.value===c.before||b.node.value===c.after));
    const call=['enter','return','error','wait','commit'].includes(event.phase)&&direct.some(b=>
      b.type!=='data'&&(b.type!=='business'||event.phase!=='return')&&
      (b.type==='business'||(b.node.referenceOf||b.node.event_node||b.id)===event.node));
    const command=event.kind==='command'&&direct.some(b=>b.type==='business');
    if(changed||call||command)plan.push(i);
  }
  return plan;
}
export function boStepDetail(recording,items,index,previousIndex,all,visible,{mode='view'}={}){
  const facts=boFacts(recording,items),owners=boOwners(all,visible),rows=[];
  for(let i=Math.max(1,previousIndex+1);i<=index;i++)for(const change of facts.changes[i]){
    let targets=owners(change.node,change);
    if(!targets.length&&change.kind==='business')targets=visible.filter(b=>b.type==='state'&&(b.node.value===change.before||b.node.value===change.after));
    for(const owner of targets)if(mode==='events'||boVisibleChange(change,owner,all))rows.push({...change,owner:owner.id,label:owner.node.label,sourceLabel:all.get(change.node)?.label||change.node});
  }
  return {rows,rawCount:index-previousIndex,event:items[index],from:previousIndex+1,to:index};
}
export function boTransferLabel(edge,event,configuration){
  if(edge.type==='resource'){
    const entry=configuration?.journal?.find(j=>j.seq===event.outputs?.revision);
    const pair=(edge.members||[]).map(m=>[entry?.before?.resources?.[m.from],entry?.after?.resources?.[m.from]]).find(([a,b])=>a&&b);
    return pair?`${pair[1].available>pair[0].available?'归还':'占用'} · 名额 ${pair[0].available} → ${pair[1].available}`:'资源占用';
  }
  if(edge.type==='join')return '检查结果 → 汇合';
  if(edge.type==='call'){
    const returned=['return','decision','error'].includes(event.phase),values=returned?event.outputs:event.inputs;
    const fields=Object.entries(values||{}).slice(0,2).map(([k,v])=>`${k}=${boValue(v)}`).join(', ');
    return `${returned?'返回':'调用'} · ${fields||'未采集参数'}`;
  }
  if(edge.type==='transition')return '状态迁移';
  if(edge.type==='guard')return `判断 · ${boValue(event.outputs?.allowed??event.outputs?.passed??event.outputs?.ok)}`;
  if(edge.type==='flow')return '业务继续';
  const field=(edge.members||[]).find(m=>m.origin==='capture-field');
  if(field){const parts=(field.from.startsWith('field:')?field.from:field.to).split(':'),key=parts.at(-1),direction=parts.at(-2);const v=(direction==='in'?event.inputs:event.outputs)?.[key];return `${direction==='in'?'输入':'返回'} ${key}: ${Array.isArray(v)?'list':typeof v} = ${boValue(v)}`;}
  const [key,value]=Object.entries(event.outputs||{}).find(([k])=>!['revision','activities','resources','join'].includes(k))||[];
  return key?`${key}: ${typeof value} = ${boValue(value)}`:'数据';
}
