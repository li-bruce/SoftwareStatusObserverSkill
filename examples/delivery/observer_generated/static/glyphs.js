// One geometry source for WebGL nodes and the SVG legend.
export const meanings={
  business:'业务处理过程',function:'函数或方法',
  state:'状态机中的状态',decision:'条件或规则判断',
  resource:'可用量与占用量',data:'输入、返回或数据',
  effect:'写入等执行结果',wait:'等待条件满足',
};
export function glyphShapes(type){
  if(type==='business')return [{kind:'circle',r:29}];
  if(type==='state')return [{kind:'circle',r:24},{kind:'circle',r:19,outline:true}];
  if(type==='decision')return [{kind:'polygon',points:[0,-27,29,0,0,27,-29,0]}];
  if(type==='data')return [{kind:'rect',x:-31,y:-19,w:62,h:38,r:18}];
  if(type==='effect')return [{kind:'rect',x:-23,y:-23,w:46,h:46,r:7}];
  if(type==='resource')return [2,1,0].map(k=>({kind:'rect',x:-25,y:-18+k*5,w:50,h:24,r:7,opaque:true}));
  if(type==='wait')return [{kind:'polygon',points:[-22,-24,22,-24,12,0,22,24,-22,24,-12,0]}];
  return [{kind:'polygon',points:[-30,0,-17,-23,17,-23,30,0,17,23,-17,23]}];
}
export function drawGlyph(g,type,x,y,color){
  for(const s of glyphShapes(type)){
    if(s.kind==='circle')g.circle(x,y,s.r);
    if(s.kind==='rect')g.roundRect(x+s.x,y+s.y,s.w,s.h,s.r);
    if(s.kind==='polygon')g.poly(s.points.map((v,i)=>v+(i%2?y:x)));
    if(!s.outline)g.fill({color:s.opaque?0xffffff:color,alpha:s.opaque?1:.13});
    g.stroke({color,width:1.8});
  }
}
export function legendGlyph(type,style){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','-36 -36 72 72');svg.setAttribute('aria-hidden','true');svg.dataset.glyph=type;
  const color='#'+style.color.toString(16).padStart(6,'0');
  for(const s of glyphShapes(type)){
    const el=document.createElementNS(ns,s.kind==='polygon'?'polygon':s.kind);
    if(s.kind==='circle')el.setAttribute('r',s.r);
    if(s.kind==='rect')for(const [k,v] of Object.entries({x:s.x,y:s.y,width:s.w,height:s.h,rx:s.r}))el.setAttribute(k,v);
    if(s.kind==='polygon')el.setAttribute('points',s.points.join(' '));
    el.setAttribute('stroke',color);el.setAttribute('stroke-width','2');el.setAttribute('fill',s.outline?'none':s.opaque?'white':color);el.setAttribute('fill-opacity',s.opaque?1:.13);svg.append(el);
  }
  const text=document.createElementNS(ns,'text');text.setAttribute('text-anchor','middle');text.setAttribute('y','7');text.setAttribute('font-size','22');text.setAttribute('fill',color);text.textContent=style.glyph;svg.append(text);return svg;
}
export function legendRelation(style){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg'),color='#'+style.color.toString(16).padStart(6,'0');
  svg.setAttribute('viewBox','0 0 44 20');svg.setAttribute('aria-hidden','true');
  const line=document.createElementNS(ns,'path');line.setAttribute('d','M2 10 H34');line.setAttribute('stroke',color);line.setAttribute('stroke-width','2');line.setAttribute('stroke-dasharray',style.dash.join(' '));svg.append(line);
  if(style.arrow!=='none'){
    const arrow=document.createElementNS(ns,'path');
    arrow.setAttribute('d',style.arrow==='bar'?'M36 4 V16':style.arrow==='diamond'?'M40 10 L34 5 L28 10 L34 15 Z':'M31 5 L39 10 L31 15'+(style.arrow==='filled'?' Z':''));
    arrow.setAttribute('stroke',color);arrow.setAttribute('stroke-width','1.8');arrow.setAttribute('fill',style.arrow==='filled'?color:style.arrow==='diamond'?'white':'none');svg.append(arrow);
  }
  return svg;
}
