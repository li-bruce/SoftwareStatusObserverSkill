// Layout preferences are local view data. They never change model or runtime facts.
import {graphBounds} from './graph-core.js';
export const layoutKey = model => 'business-observer.layout.v2:'+(model.presentation?.layout_id||model.presentation?.subject||model.intent);
export function emptyLayout(){return {schema:2,positions:Object.create(null),expanded:[],camera:null,algorithm:'stress'};}
const coordinate = n => typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<1e7;
export function readLayout(storage,key){
  const clean=emptyLayout();
  try{
    const value=JSON.parse(storage.getItem(key));
    if(value?.schema!==2)return {state:clean,available:true,restored:false};
    for(const [id,p] of Object.entries(value.positions||{}))if(coordinate(p?.x)&&coordinate(p?.y))clean.positions[id]={x:p.x,y:p.y,pinned:p.pinned===true};
    clean.expanded=Array.isArray(value.expanded)?value.expanded.filter(x=>typeof x==='string'):[];
    if(['layered','stress'].includes(value.algorithm))clean.algorithm=value.algorithm;
    if(coordinate(value.camera?.x)&&coordinate(value.camera?.y)&&value.camera.scale>=.12&&value.camera.scale<=3)clean.camera=value.camera;
    return {state:clean,available:true,restored:true};
  }catch{return {state:clean,available:false,restored:false};}
}
export function writeLayout(storage,key,state){try{storage.setItem(key,JSON.stringify(state));return true;}catch{return false;}}
function overlaps(a,b,gap=22){return a.x<b.x+b.w+gap&&a.x+a.w+gap>b.x&&a.y<b.y+b.h+gap&&a.y+a.h+gap>b.y;}
function freePosition(node,x,y,placed){
  if(!placed.some(p=>overlaps({...node,x,y},p)))return {x,y};
  for(let ring=1;ring<=placed.length+2;ring++){
    const count=Math.max(8,ring*8);
    for(let i=0;i<count;i++){
      const angle=i*2*Math.PI/count,dx=x+Math.cos(angle)*ring*115,dy=y+Math.sin(angle)*ring*100;
      if(!placed.some(p=>overlaps({...node,x:dx,y:dy},p)))return {x:dx,y:dy};
    }
  }
  return {x,y:y+(placed.length+2)*200};
}
export function placeIncremental(graph,state){
  const placed=[];
  for(const b of graph.boxes){const p=state.positions[b.id];if(p){b.x=p.x;b.y=p.y;b.pinned=p.pinned;placed.push(b);}}
  for(const b of graph.boxes){
    if(state.positions[b.id])continue;
    const parent=graph.byId.get(b.node.parent),near=parent&&placed.includes(parent)?parent:null;
    const point=freePosition(b,near?near.x+230:b.x,near?near.y:b.y,placed);
    Object.assign(b,point,{pinned:false});state.positions[b.id]={...point,pinned:false};placed.push(b);
  }
  return graphBounds(graph);
}
export function setPosition(graph,state,id,x,y){
  if(!coordinate(x)||!coordinate(y)||!graph.byId.has(id))return false;
  const b=graph.byId.get(id),pinned=!!state.positions[id]?.pinned;
  state.positions[id]={x,y,pinned};Object.assign(b,{x,y,pinned});graphBounds(graph);return true;
}
export function togglePin(graph,state,id){
  const b=graph.byId.get(id);if(!b)return;
  const next=!state.positions[id]?.pinned;
  state.positions[id]={x:b.x,y:b.y,pinned:next};b.pinned=next;return next;
}
export function topologyKey(graph){return JSON.stringify([graph.boxes.map(b=>b.id).sort(),graph.edges.map(e=>[e.id,e.from,e.to,e.type]).sort()]);}

// ELK performs the global layered/stress layout. A constrained merge preserves
// exact user pins and removes overlaps with those pins. It is not yFiles.
export async function calculateLayout(elk,graph,state,algorithm='layered'){
  if(!['layered','stress'].includes(algorithm))throw Error('Unknown layout algorithm');
  const input={id:'root',layoutOptions:{'elk.algorithm':algorithm,'elk.direction':'RIGHT','elk.randomSeed':'42',
      'elk.spacing.nodeNode':'65','elk.spacing.componentComponent':'100','elk.layered.spacing.nodeNodeBetweenLayers':'110',
      'elk.edgeRouting':'ORTHOGONAL','elk.stress.desiredEdgeLength':'240','elk.stress.iterationLimit':'250'},
    children:graph.boxes.map(b=>({id:b.id,width:b.w,height:b.h,x:b.x,y:b.y})),
    edges:graph.edges.filter(e=>graph.byId.has(e.from)&&graph.byId.has(e.to)).map((e,i)=>({id:'e'+i,sources:[e.from],targets:[e.to]}))};
  const output=await elk.layout(input),proposed=new Map(output.children.map(n=>[n.id,n]));
  const result=Object.create(null),placed=[],pins=graph.boxes.filter(b=>state.positions[b.id]?.pinned);
  let dx=60,dy=60;
  if(pins.length){const p=proposed.get(pins[0].id);dx=pins[0].x-p.x;dy=pins[0].y-p.y;}
  for(const b of pins){result[b.id]={x:b.x,y:b.y,pinned:true};placed.push({...b});}
  for(const b of graph.boxes){
    if(result[b.id])continue;
    const p=proposed.get(b.id);if(!p||!coordinate(p.x)||!coordinate(p.y))throw Error('Layout returned invalid coordinates');
    const point=freePosition(b,p.x+dx,p.y+dy,placed);
    result[b.id]={...point,pinned:false};placed.push({...b,...point});
  }
  return result;
}
export function applyLayout(graph,state,positions){
  for(const b of graph.boxes){const p=positions[b.id];if(p){state.positions[b.id]={...p};Object.assign(b,p);}}
  return graphBounds(graph);
}

// A small shared gesture controller makes node drag distinct from canvas pan,
// including pointer cancellation, scale conversion and lost capture.
export class GraphGesture {
  start(pointer,{node=null,pan,scale}){this.active={pointerId:pointer.pointerId,x:pointer.x,y:pointer.y,node:node?{id:node.id,x:node.x,y:node.y}:null,pan:{...pan},scale,moved:false};}
  move(pointer){
    const a=this.active;if(!a||a.pointerId!==pointer.pointerId)return null;
    const dx=pointer.x-a.x,dy=pointer.y-a.y;if(Math.hypot(dx,dy)>4)a.moved=true;if(!a.moved)return null;
    return a.node?{kind:'node',id:a.node.id,x:a.node.x+dx/a.scale,y:a.node.y+dy/a.scale}:{kind:'pan',x:a.pan.x+dx,y:a.pan.y+dy};
  }
  end(pointerId){if(this.active?.pointerId!==pointerId)return null;const old=this.active;this.active=null;return old;}
}
