// View selection is a projection. It cannot add permission, call or runtime facts.
import {nodeType} from './graph-core.js';
const types=['business','function','state','decision','resource','data','effect','wait'];
const edges=['call','flow','transition','guard','data','resource','join','shared','other'];
export const presets=[
  {id:'overview',label:'分层全图',hierarchical:true,nodes:types,edges},
  {id:'business',label:'业务流',nodes:['business'],edges:['flow','guard','data','join']},
  {id:'states',label:'状态机',nodes:['state'],edges:['transition']},
  {id:'functions',label:'函数与参数',nodes:['function','decision','data'],edges:['call','data']},
  {id:'permission',label:'权限判断',nodes:['business','decision','function','data','wait'],edges:['guard','data','call','flow'],scope:'permission'},
  {id:'resources',label:'并发与资源',nodes:['function','resource','decision','state','wait','data'],edges:['resource','join','transition','data'],scope:'execution'},
  {id:'data',label:'数据依赖',nodes:['function','decision','data','effect'],edges:['data','guard','call']},
  {id:'runtime',label:'实际运行',nodes:types,edges,scope:'observed'},
  {id:'blocked',label:'等待与异常',nodes:types,edges,scope:'blocked'},
  {id:'shared',label:'共享关系',nodes:types,edges:['shared'],scope:'shared'},
];
export function cleanProfile(value){
  const strings=(values,allowed)=>Array.isArray(values)?[...new Set(values.filter(x=>allowed.includes(x)))]:allowed.slice();
  return {nodes:strings(value?.nodes,types),edges:strings(value?.edges,edges),
    regions:strings(value?.regions,types),depth:Number.isInteger(value?.depth)?value.depth:'all',
    scope:['all','permission','execution','observed','blocked','shared'].includes(value?.scope)?value.scope:'all',
    query:typeof value?.query==='string'?value.query.trim().slice(0,100):'',hierarchical:value?.hierarchical===true};
}
export function profileFor(id,custom=[]){return cleanProfile(presets.find(p=>p.id===id)||custom.find(p=>p.id===id)||presets[0]);}
export function matchingNodes(all,view,events,profile,statusOf){
  const profileTypes=new Set(profile.nodes),selected=new Set(),execution=view.model.machine.execution||{};
  const scopeNodes=new Set(),raw=view.model.edges;
  if(profile.scope==='permission'){
    for(const n of all.values())if(n.semantic_roles?.includes('permission'))scopeNodes.add(n.id);
    for(const e of raw)if(['guard','data'].includes(e.type)&&(scopeNodes.has(e.to)||scopeNodes.has(e.from))){scopeNodes.add(e.from);scopeNodes.add(e.to);}
  }
  if(profile.scope==='execution'){
    for(const n of all.values())if(n.execution_role)scopeNodes.add(n.id);
    for(const n of [...(execution.activities||[]),...(execution.resources||[]),execution.join].filter(Boolean))scopeNodes.add(n.id);
    if(execution.within)scopeNodes.add('state.'+execution.within);
  }
  const eventIds=new Set(events.map(e=>e.node));
  for(const n of all.values()){
    const canonical=n.referenceOf||n.id,type=nodeType(n);
    let inScope=profile.scope==='all';
    if(['permission','execution'].includes(profile.scope))inScope=scopeNodes.has(canonical)||scopeNodes.has(n.event_node)||scopeNodes.has(n.parent);
    if(profile.scope==='observed')inScope=eventIds.has(n.event_node||canonical);
    if(profile.scope==='blocked')inScope=statusOf(n)==='blocked';
    if(profile.scope==='shared')inScope=!!n.referenceOf||[...all.values()].some(ref=>ref.referenceOf===n.id||ref.referenceOf&&ref.parent===n.id);
    const query=profile.query.toLocaleLowerCase();
    const matches=!query||[n.label,n.id,n.source?.symbol,n.summary].join(' ').toLocaleLowerCase().includes(query);
    if(profileTypes.has(type)&&inScope&&matches)selected.add(n.id);
  }
  for(const id of selected){const n=all.get(id);if(n.referenceOf&&!selected.has(n.parent))selected.delete(id);}
  return selected;
}
export function sharedMemberships(model){
  const memberships=[...(model.presentation?.memberships||[])],execution=model.machine.execution;
  if(execution?.within){
    const group='state.'+execution.within;
    for(const n of [...(execution.activities||[]),...(execution.resources||[]),execution.join].filter(Boolean))
      memberships.push({group,member:n.id,reason:'该状态的内部执行配置',evidence:'machine.execution'});
  }
  const seen=new Set();
  return memberships.filter(m=>{const key=m.group+'\0'+m.member;if(m.group===m.member||seen.has(key))return false;seen.add(key);return true;});
}
