// Graph drawing owns Pixi objects and hit geometry, but no fetching, storage or UI commands.
import {colors as C,nodeTypes} from './graph-core.js';
import {annotationFor,displayName,edgePorts,relationStyles} from './layout.js';
import {drawGlyph,glyphAppearance} from './glyphs.js';
import {boKinds} from './replay-steps.js';

export function short(value,count=27){const chars=[...String(value)];return chars.length>count?chars.slice(0,count-1).join('')+'…':String(value);}
export function bezierAt(path,t){
  const {start:a,c1:b,c2:c,end:d}=path,u=1-t;
  return {x:u*u*u*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t*t*t*d.x,y:u*u*u*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t*t*t*d.y};
}
export function nodePoint(graph,presentation,b){
  const region=presentation?.regions.has(b.id)&&!presentation.glyphs.has(b.id)?graph.regions.find(r=>r.id===b.id):null;
  return region?{x:region.cx,y:region.cy}:{x:b.x+b.w/2,y:b.y+31};
}

export function createGraphRenderer({PIXI,app,scene,metrics,hits,edgePaths,onMetrics=()=>{}}){
  let graph,presentation,focusContext,preferences,selected,scale,pan;
  let renderedEdges,boDetail,boTransfers,formatChange,formatValue,contextLost;
  let drawCount=0;
  const point=box=>nodePoint(graph,presentation,box);
  function visible(x,y,w,h){return x+w>=-pan.x/scale-60&&y+h>=-pan.y/scale-60&&x<=(-pan.x+app.screen.width)/scale+60&&y<=(-pan.y+app.screen.height)/scale+60;}
  // Objects keep stable owner/slot keys across redraws. Only a small inactive
  // reserve survives folding or panning; shared Pixi textures are never force-freed.
  const renderPool=new Map(),allocations={graphics:0,text:0};
  let renderScope='',renderSlot=0;
  function scope(key){renderScope=key;renderSlot=0;}
  function retained(kind,create){
    const key=renderScope+':'+kind+':'+renderSlot++;
    let item=renderPool.get(key);
    if(!item){item={object:create(),frame:drawCount};renderPool.set(key,item);allocations[kind]++;}
    item.frame=drawCount;const object=item.object;
    object.alpha=1;object.scale.set(1);object.position.set(0);
    return object;
  }
  function graphic(){return retained('graphics',()=>new PIXI.Graphics()).clear();}
  function text(value,x,y,size=12,color=C.ink,align='left',weight='400'){
    const t=retained('text',()=>new PIXI.Text({text:'',resolution:1})),label=String(value);
    const styleKey=[size,color,weight].join(':');
    if(t._observerStyle!==styleKey){t.style={fontFamily:'Segoe UI, Microsoft YaHei, sans-serif',fontSize:size,fill:color,fontWeight:weight};t._observerStyle=styleKey;}
    if(t.text!==label)t.text=label;
    t.anchor.set(align==='center'?.5:0,0);t.position.set(x,y);scene.addChild(t);metrics.texts++;return t;
  }
  function trimPool(){
    const idle=[...renderPool].filter(([,item])=>item.frame!==drawCount).sort((a,b)=>b[1].frame-a[1].frame);
    for(const [key,item] of idle.slice(128)){item.object.destroy();renderPool.delete(key);}
    onMetrics({drawCount:String(drawCount+1),poolSize:String(renderPool.size),activeObjects:String(renderPool.size-Math.min(128,idle.length)),createdGraphics:String(allocations.graphics),createdText:String(allocations.text),contextLost:String(contextLost)});
  }
  function clear(){scene.removeChildren();for(const item of renderPool.values())item.object.destroy();renderPool.clear();}
  function drawRegions(){
    const labels=[];
    for(const r of graph.regions||[]){
      if(!presentation.regions.has(r.id)||!visible(r.x,r.y,r.w,r.h))continue;
      scope('region:'+r.id);
      const owner=graph.byId.get(r.id),color=nodeTypes[owner.type].color;
      const highlighted=focusContext.regions.has(r.id),dim=focusContext.active&&!highlighted;
      const core=annotationFor(preferences,owner.node.referenceOf||r.id).core;
      const shape=graphic().circle(r.cx,r.cy,r.radius).fill({color:0xffffff,alpha:.88})
        .circle(r.cx,r.cy,r.radius).fill({color,alpha:dim?.045:selected===r.id?.3:core?.26:highlighted?.22:.14+Math.min(r.depth,3)*.02})
        .stroke({color,width:highlighted?2.3:1.3,alpha:dim?.2:highlighted?.8:.45});
      scene.addChild(shape);
      hits.push({cx:r.cx,cy:r.cy,radius:r.radius,region:r.id,border:true});
      labels.push({r,owner,color,dim});
    }
    // Draw titles after every enclosure so a child fill cannot cover its parent title.
    const occupied=[];
    for(const {r,owner,color,dim} of labels){
      scope('region-title:'+r.id);
      const font=Math.max(13,11/scale),name=(annotationFor(preferences,owner.node.referenceOf||r.id).core?'★ ':'')+short(displayName(owner.node,preferences),22);
      const label=text(`${name} · ${nodeTypes[owner.type].label} · ${owner.kids.length}`,0,0,font,color,'center','500');
      const w=label.width+16/scale,h=font+8/scale;
      const candidates=[-90,-120,-60,-150,-30,90,180,0].map(deg=>{
        const angle=deg*Math.PI/180,cx=r.cx+Math.cos(angle)*r.radius,cy=r.cy+Math.sin(angle)*r.radius;
        return {x:cx-w/2,y:cy-h/2,w,h,cx,cy};
      });
      const box=candidates.find(a=>!occupied.some(b=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y))||candidates[0];
      occupied.push(box);
      const background=graphic().roundRect(box.x,box.y,w,h,4/scale).fill({color:0xffffff,alpha:dim?.55:.94});
      scene.addChild(background);scene.removeChild(label);scene.addChild(label);
      label.position.set(box.cx,box.cy-font/2);label.alpha=dim?.28:1;
      hits.push({x:box.x,y:box.y,w,h,region:r.id});
      boDrawChange(owner,box.cx,box.y+box.h+4/scale);
    }
  }

  function strokeRelation(g,path,style,width,alpha){
    const {start,end,c1,c2}=path;
    if(!style.dash.length){g.moveTo(start.x,start.y).bezierCurveTo(c1.x,c1.y,c2.x,c2.y,end.x,end.y).stroke({color:style.color,width,alpha});return;}
    const length=Math.hypot(start.x-c1.x,start.y-c1.y)+Math.hypot(c1.x-c2.x,c1.y-c2.y)+Math.hypot(c2.x-end.x,c2.y-end.y);
    const steps=Math.max(24,Math.min(700,Math.ceil(length/6)));let previous=start,index=0,remaining=style.dash[0];
    for(let i=1;i<=steps;i++){
      const next=bezierAt(path,i/steps);let from=previous,distance=Math.hypot(next.x-from.x,next.y-from.y);
      while(distance>1e-6){
        const part=Math.min(distance,remaining),to={x:from.x+(next.x-from.x)*part/distance,y:from.y+(next.y-from.y)*part/distance};
        if(index%2===0)g.moveTo(from.x,from.y).lineTo(to.x,to.y);
        remaining-=part;distance-=part;from=to;
        if(remaining<1e-6){index=(index+1)%style.dash.length;remaining=style.dash[index];}
      }
      previous=next;
    }
    g.stroke({color:style.color,width,alpha});
  }
  function drawEdges(foreground,labelBoxes){
    const lanes=new Map();
    for(const e of renderedEdges){
      const a=graph.byId.get(e.from),b=graph.byId.get(e.to);if(!a||!b)continue;
      const p=point(a),q=point(b),key=[e.from,e.to].sort().join('|'),index=lanes.get(key)||0;lanes.set(key,index+1);
      if(!!e.crossing!==foreground)continue;
      scope('edge:'+e.id);
      const highlight=[...e.edgeIds].some(id=>focusContext.edges.has(id)),dim=focusContext.active&&!highlight,style=relationStyles[e.type]||relationStyles.other,col=style.color;
      const dx=q.x-p.x,dy=q.y-p.y,length=Math.hypot(dx,dy)||1,offset=(index+1)*20;
      let start,end,c1,c2,mid;
      if(a===b){start={x:p.x-18,y:p.y-18};end={x:p.x+18,y:p.y-18};c1={x:p.x-68,y:p.y-95-offset};c2={x:p.x+68,y:p.y-95-offset};mid={x:p.x,y:p.y-75-offset};}
      else{
        ({start,end}=edgePorts(graph,e,Math.max(32,15/scale)));const sx=end.x-start.x,sy=end.y-start.y;
        c1={x:start.x+sx*.32-dy/length*offset,y:start.y+sy*.32+dx/length*offset};
        c2={x:end.x-sx*.32-dy/length*offset,y:end.y-sy*.32+dx/length*offset};
        mid={x:(start.x+3*c1.x+3*c2.x+end.x)/8,y:(start.y+3*c1.y+3*c2.y+end.y)/8};
      }
      if(!visible(Math.min(p.x,q.x)-120,Math.min(p.y,q.y)-120,Math.abs(dx)+240,Math.abs(dy)+240))continue;
      const path={start,end,c1,c2};edgePaths.set(e.id,path);const alpha=dim?.1:highlight?.95:.65,g=graphic();
      if(foreground&&!dim)strokeRelation(g,path,{color:0xf6f8fa,dash:[]},Math.max(5,3/scale),.9);
      strokeRelation(g,path,{...style,dash:style.dash.map(n=>n/Math.min(1,scale))},Math.max(highlight?2.3:e.observed?2:1.5,(highlight?1.5:1)/scale),alpha);scene.addChild(g);metrics.edges++;
      const angle=Math.atan2(end.y-c2.y,end.x-c2.x);
      const af=Math.max(1,.6/scale),arrow=graphic(),left={x:end.x-10*af*Math.cos(angle-.45),y:end.y-10*af*Math.sin(angle-.45)},right={x:end.x-10*af*Math.cos(angle+.45),y:end.y-10*af*Math.sin(angle+.45)};
      if(style.arrow==='filled')arrow.poly([end.x,end.y,left.x,left.y,right.x,right.y]).fill(col);
      else if(style.arrow==='diamond')arrow.poly([end.x,end.y,left.x,left.y,end.x-18*af*Math.cos(angle),end.y-18*af*Math.sin(angle),right.x,right.y]).fill(0xffffff).stroke({color:col,width:1.5*af});
      else if(style.arrow==='bar')arrow.moveTo(end.x-7*af*Math.cos(angle+Math.PI/2),end.y-7*af*Math.sin(angle+Math.PI/2)).lineTo(end.x+7*af*Math.cos(angle+Math.PI/2),end.y+7*af*Math.sin(angle+Math.PI/2)).stroke({color:col,width:3*af});
      else if(style.arrow!=='none')arrow.moveTo(left.x,left.y).lineTo(end.x,end.y).lineTo(right.x,right.y).stroke({color:col,width:1.8});
      arrow.alpha=alpha;scene.addChild(arrow);
      if(e.observed&&!dim){const marker=bezierAt(path,.72);scene.addChild(graphic().circle(marker.x,marker.y,4).fill(e.current?0x238065:0x8a949e));}
      if(!dim&&scale>.24&&(highlight||scale>.38)){
        const font=Math.max(11.5/Math.sqrt(Math.min(1,scale)),10/scale),description=e.members.length>1?`${style.label} × ${e.members.length}`:scale<.45?style.label:style.label+' · '+[...e.labels].join(' / ');
        const payload=boTransfers.get(e.id);
        const caption=payload?(scale<.45?(e.type==='data'?(payload.label.startsWith('输入')?'输入':'返回'):style.label):payload.label):description;
        const label=short(caption,payload?40:highlight?34:23),w=Math.min(340,[...label].reduce((n,c)=>n+(c.charCodeAt(0)>255?font:font*.57),0)+12),h=font+7;
        // Put labels along the curve where they avoid nodes and previous labels.
        const candidates=[.5,.32,.68,.2,.8].map(t=>({x:(1-t)**3*start.x+3*(1-t)**2*t*c1.x+3*(1-t)*t*t*c2.x+t**3*end.x,y:(1-t)**3*start.y+3*(1-t)**2*t*c1.y+3*(1-t)*t*t*c2.y+t**3*end.y}));
        const collision=(x,y,b)=>x-w/2<b.x+b.w&&x+w/2>b.x&&y-h/2<b.y+b.h&&y+h/2>b.y;
        const candidate=candidates.find(p=>!graph.boxes.some(b=>presentation.glyphs.has(b.id)&&collision(p.x,p.y,b))&&!labelBoxes.some(b=>collision(p.x,p.y,b)));
        if(candidate){mid=candidate;const bg=graphic().roundRect(mid.x-w/2,mid.y-h/2,w,h,4).fill({color:0xffffff,alpha:.94});scene.addChild(bg);text(label,mid.x,mid.y-font/2,font,col,'center');labelBoxes.push({x:mid.x-w/2,y:mid.y-h/2,w,h});hits.push({x:mid.x-w/2,y:mid.y-h/2,w,h,edge:e});}
      }
    }
  }
  function drawNode(b){
    if(!presentation.glyphs.has(b.id)||!visible(b.x-10,b.y-10,b.w+20,b.h+30))return;metrics.nodes++;scope('node:'+b.id);
    const p=point(b),style=nodeTypes[b.type],stroke=nodeTypes[b.type].color,g=graphic(),r=b.type==='business'?29:24;
    const size=Math.max(1,11/(r*scale)),glyphFont=Math.max(b.type==='business'?13:19,10/scale);
    if(focusContext.active&&focusContext.nodes.has(b.id)&&selected!==b.id)g.circle(p.x,p.y,r+5).stroke({color:0x5d87b1,width:1.6,alpha:.65});
    if(selected===b.id)g.circle(p.x,p.y,r+8).stroke({color:0x356ba4,width:3,alpha:1});
    const appearance=glyphAppearance(stroke,{core:annotationFor(preferences,b.node.referenceOf||b.id).core,
      selected:selected===b.id,related:focusContext.nodes.has(b.id)});
    drawGlyph(g,b.type,p.x,p.y,stroke,appearance);
    g.scale.set(size);g.position.set(p.x*(1-size),p.y*(1-size));scene.addChild(g);
    text(style.glyph,p.x,p.y-glyphFont*.55,glyphFont,appearance.ink,'center','600');
    if(b.state!=='declared'){
      const statusColor=({active:0x22876e,ok:0x22876e,blocked:0xbd8237,historical:0x8192a2})[b.state]||0x8192a2;
      const badgeX=p.x+23*size,badgeY=p.y+21*size,font=Math.max(11,8/scale);
      scene.addChild(graphic().circle(badgeX,badgeY,Math.max(8,6/scale)).fill(0xffffff).stroke({color:statusColor,width:Math.max(1.5,.8/scale)}));
      text(b.state==='ok'?'✓':b.state==='active'?'▶':b.state==='blocked'?'!':'·',badgeX,badgeY-font*.6,font,statusColor,'center','600');
    }
    if(b.node.referenceOf)text('↗',p.x-29*size,p.y-26*size,Math.max(14,10/scale),stroke,'center','600');
    if(b.pinned){const pin=graphic().circle(p.x+29,p.y-24,5).fill(0x4f7598);scene.addChild(pin);}
    const annotation=annotationFor(preferences,b.node.referenceOf||b.id);
    if(annotation.label||annotation.note)text('✎',p.x-35,p.y-31,14,0x5075b5,'center');
    if(annotation.core)text('★',p.x-32,p.y+20,14,0xb18c3c,'center');
    if(b.kids.length){text(b.open?'−':'+ '+b.kids.length,p.x+52*size,p.y-5,Math.max(14,9/scale),0x467795,'center');hits.push({x:p.x+34*size,y:p.y-15*size,w:42*size,h:28*size,expand:b.id});}
    if(scale>.24||b.type==='business'||presentation.glyphs.size<=30)text(short(displayName(b.node,preferences),scale<.45?15:19),p.x,p.y+r*size+7/scale,Math.max(14/Math.sqrt(Math.min(1,scale)),10/scale),0x2b4658,'center',b.type==='business'?'600':'500');
    if(scale>.48){
      let rows;
      if(b.type==='state')rows=b.rows.filter(r=>r.role==='value').slice(0,1);
      else if(b.type==='business')rows=b.rows.filter(r=>['value','good','bad'].includes(r.role)).slice(0,2);
      else if(b.node.field)rows=b.rows.slice(0,2);
      else rows=[b.rows[0],...b.rows.filter(r=>r!==b.rows[0]&&['good','bad','value'].includes(r.role))].filter(Boolean).slice(0,2);
      rows.forEach((row,i)=>text(short(row.text,29),p.x,b.y+91+i*18,11.5/Math.sqrt(Math.min(1,scale)),row.role==='bad'?0xa76d2c:row.role==='good'?0x327e6b:0x637c8d,'center'));
      if(annotation.note)text(short('备注：'+annotation.note.replace(/\s+/g,' '),27),p.x,b.y+b.h-19,11.5/Math.sqrt(Math.min(1,scale)),0x5075b5,'center');
    }else if(presentation.glyphs.size<=30){
      const row=b.rows.find(r=>['good','bad'].includes(r.role))||b.rows.find(r=>r.role==='value');
      if(row)text(short(row.text,22),p.x,p.y+r*size+20/scale,Math.max(11,9/scale),row.role==='bad'?0xa76d2c:row.role==='good'?0x327e6b:0x637c8d,'center');
    }
    boDrawChange(b,p.x,b.y+b.h+3);
    hits.push({id:b.id,x:b.x,y:b.y+5,w:b.w,h:b.h-4,cx:p.x,cy:p.y,r:(r+6)*size});
  }
  function boDrawChange(box,x,y){
    const rows=boDetail?.rows.filter(r=>r.owner===box.id)||[];if(!rows.length)return;
    const row=rows.find(r=>r.kind==='business')||rows.find(r=>r.kind==='state')||rows.find(r=>r.kind==='resource'&&r.field==='available')||rows.at(-1);
    const font=Math.max(11,9/scale),value=scale<.48?(box.type==='business'?short(formatChange(row),24):'→ '+short(formatValue(row.after),9)):short(formatChange(row),34)+(rows.length>1?` (+${rows.length-1})`:'');
    const label=text(value,x,y,font,boKinds[row.kind].color,'center','500');
    const back=graphic().roundRect(x-label.width/2-5,y-3,label.width+10,font+7,4).fill({color:0xffffff,alpha:.96});
    scene.addChild(back);scene.removeChild(label);scene.addChild(label);
  }

  function draw(state){
    ({graph,presentation,focusContext,preferences,selected,scale,pan,
      boDetail,boTransfers,formatChange,formatValue,contextLost}=state);
    renderedEdges=presentation.edges;
    scene.removeChildren();
    edgePaths.clear();
    scene.position.set(pan.x,pan.y);
    scene.scale.set(scale);
    hits.length=0;
    metrics.nodes=metrics.edges=metrics.texts=0;
    const labelBoxes=[];
    drawRegions();
    drawEdges(false,labelBoxes);
    for(const box of graph.boxes){
      const start=scene.children.length;
      drawNode(box);
      if(focusContext.active&&!focusContext.nodes.has(box.id)){
        for(let i=start;i<scene.children.length;i++)scene.children[i].alpha*=.22;
      }
    }
    // Cross-group links remain above enclosing fills and nodes.
    drawEdges(true,labelBoxes);
    trimPool();
    drawCount++;
  }
  return {draw,clear,get frames(){return drawCount;}};
}
