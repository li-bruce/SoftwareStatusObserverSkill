import assert from 'node:assert/strict';
import {nodeTypes} from '../skills/vibelens/assets/stategraph-viewer/graph-core.js';
import {glyphAppearance} from '../skills/vibelens/assets/stategraph-viewer/glyphs.js';
const luminance=c=>[16,8,0].map(s=>((c>>s)&255)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
for(const [type,{color}] of Object.entries(nodeTypes)){
  const normal=glyphAppearance(color),core=glyphAppearance(color,{core:true});
  assert.notEqual(normal.fill,0xffffff,type+' needs visible type fill');
  assert.notEqual(normal.fill,core.fill,type+' core must stand out');
  for(const options of [{},{core:true},{selected:true},{related:true}]){
    const {fill,ink}=glyphAppearance(color,options),a=luminance(fill),b=luminance(ink);
    assert((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,type+' glyph contrast');
  }
}
console.log(`PASS: all ${Object.keys(nodeTypes).length} node types have distinct fills, core emphasis and legible glyphs in 4 states.`);
