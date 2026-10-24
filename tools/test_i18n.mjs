import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {t, setLocale, chooseLocale, localeURL, saveLocale, storedLocale} from '../skills/vibelens/assets/stategraph-viewer/i18n.js';
import {projectStorage} from '../skills/vibelens/assets/stategraph-viewer/preferences.js';
import {connectionStatus} from '../skills/vibelens/assets/stategraph-viewer/view-lifecycle.js';

assert.equal(chooseLocale(), 'en');
assert.equal(chooseLocale({languages:['fr-FR','zh-TW']}), 'zh-CN');
assert.equal(chooseLocale({explicit:'en',saved:'zh-CN',languages:['zh']}), 'en');
assert.equal(chooseLocale({saved:'zh-CN',languages:['en']}), 'zh-CN');
setLocale('en');
assert.equal(connectionStatus({health:{dropped:0,evicted_events:5}},t), 'Connected · 5 earlier events expired');
assert.equal(connectionStatus({health:{dropped:2,evicted_events:5}},t), 'Missing 2 records · 5 earlier events expired');
assert.equal(connectionStatus({historical:true,health:{dropped:0,evicted_events:5}},t), 'Saved run');
setLocale('zh-CN');
assert.equal(connectionStatus({health:{dropped:0,evicted_events:5}},t), '已连接 · 5 条历史事件已过期');
assert.equal(connectionStatus({health:{dropped:2,evicted_events:5}},t), '有 2 条记录缺失 · 5 条历史事件已过期');
setLocale('en');
assert.equal(t('Showing {0} nodes and {1} relations',3,2),'Showing 3 nodes and 2 relations');
setLocale('zh-CN');
assert.equal(t('Showing {0} nodes and {1} relations',3,2),'显示 3 个节点、2 条关系');
assert.equal(t('unregistered_key:{0}','source-id'),'unregistered_key:source-id');
assert.equal(t('unknown-node'),'unknown-node');
const href=localeURL('http://localhost/graph?node=review%3Aimage#details','zh');
assert.equal(new URL(href).searchParams.get('node'),'review:image');
assert.equal(new URL(href).hash,'#details');
setLocale('en');
let server={schema:1,revision:0,project_id:'trial',entries:{}};
const requests=[];
const request=async(_url,options)=>{
  if(options.method==='POST'){
    const next=JSON.parse(options.body);requests.push(next);
    assert.equal(next.revision,server.revision);
    await new Promise(resolve=>setTimeout(resolve,5));
    server={...next,revision:next.revision+1};
  }
  return {ok:true,json:async()=>structuredClone(server)};
};
const storage=await projectStorage(null,()=>{},request);
const notes=JSON.stringify({annotations:{upload:{name:'My upload',note:'Keep my words'}},positions:{upload:{x:12,y:34}}});
storage.setItem('business-observer.layout.v2:trial',notes);
const first=storage.flush();
await saveLocale(storage,'zh-CN');
await first;
assert.equal(JSON.parse(server.entries['business-observer.layout.v2:locale']).locale,'zh-CN');
assert.equal(server.entries['business-observer.layout.v2:trial'],notes);
assert.equal(storedLocale(await projectStorage(null,()=>{},request)),'zh-CN');
assert.equal(requests.length,2,'Locale change during a pending write must be persisted');
const conflict=await projectStorage(null,()=>{},async(_url,options)=>options.method==='POST'
  ? {ok:false,status:409,json:async()=>({error:'conflict'})}
  : {ok:true,json:async()=>structuredClone(server)});
await assert.rejects(saveLocale(conflict,'en'),/not saved/);
const html=await readFile(new URL('../skills/vibelens/assets/stategraph-viewer/index.html',import.meta.url),'utf8');
assert.match(html,/<html lang="en">/);
assert.match(html,/id="language"/);
assert.doesNotMatch(html,/[\u3400-\u9fff]/);
console.log('PASS: locale precedence, fallback, interpolation, stable identity, project persistence, concurrent writes, and conflict reporting.');
