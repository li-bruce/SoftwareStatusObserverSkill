// Real React/Vue components and native application functions, not simulated UI
// results. jsdom supplies DOM APIs; transport is replaceable and tested separately.
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {BOProbe,BOExecutor} from '../bo_stategraph/bo_runtime.mjs';
import {bo_runner} from '../integrations/bo_runner.mjs';
import {advance,available} from '../src/job.mjs';
const root=new URL('../',import.meta.url);
const adapterRequire=createRequire(new URL('../../../skills/business-observer/scripts/bo_observer/adapters/javascript/package.json',import.meta.url));
const ts=adapterRequire('typescript'),sfc=adapterRequire('@vue/compiler-sfc');
const project=JSON.parse(readFileSync(new URL('bo_stategraph/project.json',root),'utf8'));
const input=process.env.BO_TEST_BUILD||'component-test';
const out=new URL('.stategraph/compiled/',root);mkdirSync(out,{recursive:true});
const reactSource=readFileSync(new URL('src/ReactPanel.tsx',root),'utf8');
const vueSource=readFileSync(new URL('src/VuePanel.vue',root),'utf8');
const vue=sfc.parse(vueSource,{filename:'VuePanel.vue'});
const compiled=sfc.compileScript(vue.descriptor,{id:'bo-vue-demo',inlineTemplate:true});
for(const [name,source] of [['react',reactSource],['vue',compiled.content]])writeFileSync(new URL(name+'.mjs',out),ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText);
const dom=new JSDOM('<main><div id="react"></div><div id="vue"></div></main>',{url:'http://localhost'});
for(const key of ['window','document','HTMLElement','Element','SVGElement','Node','Event','MouseEvent'])globalThis[key]=dom.window[key];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const {default:React,act}=await import('react'),{createRoot}=await import('react-dom/client');
const {createApp,nextTick}=await import('vue');
const {ReactPanel}=await import(new URL('react.mjs',out)),{default:VuePanel}=await import(new URL('vue.mjs',out));
const reports=[];
for(const development of ['drive','observe']) {
  const p=structuredClone(project);p.selection.mode=development;
  const runs=[];
  for(const mode of ['on','off','fault']) {
    const events=[],snapshots=[];
    const probe=new BOProbe({project:p,buildId:input,enabled:mode!=='off',sink:mode==='fault'?()=>{throw Error('collector failed')}: (e,kind)=>(kind==='events'?events:snapshots).push(e)});
    const run=bo_runner(p,probe);assert.equal(run('start'),'running');assert.equal(run('finish'),'done');await probe.flush();
    const executor=development==='drive'?new BOExecutor(p.model.machine,{available}):null;
    assert.equal(advance('pending','start',0,executor).state,'waiting');assert.equal(advance('waiting','resume',1,executor).state,'running');
    runs.push({case:'node',mode,events:events.splice(0),snapshots:snapshots.splice(0),observations:{state:'done'}});
    const bo_observe=(node,phase,values)=>probe.record(node,phase,()=>values);
    const reactRoot=createRoot(document.getElementById('react'));
    await act(async()=>reactRoot.render(React.createElement(ReactPanel,{run:bo_runner(p,probe,'react'),bo_observe})));
    const vueApp=createApp(VuePanel,{run:bo_runner(p,probe,'vue'),bo_observe});vueApp.mount('#vue');await nextTick();
    for(const [framework,settle] of [['react',async f=>act(f)],['vue',async f=>{f();await nextTick();}]]) {
      const host=document.getElementById(framework),buttons=host.querySelectorAll('button');
      await settle(()=>buttons[0].dispatchEvent(new MouseEvent('click',{bubbles:true})));
      assert.equal(host.querySelector('p').textContent,'running');
      await settle(()=>buttons[1].dispatchEvent(new MouseEvent('click',{bubbles:true})));
      assert.equal(host.querySelector('p').textContent,'done');
    }
    await probe.flush();
    if(mode==='on') {
      for(const node of ['react.start','react.finish','vue.start','vue.finish']) assert(events.some(e=>e.node===node));
      for(const framework of ['react','vue']) assert(events.some(e=>e.node===framework+'.finish'&&e.outputs.state==='done'&&e.outputs.before==='running'));
      assert(snapshots.filter(s=>s.state==='done').length===2);
    } else assert.equal(events.length,0);
    runs.push({case:'ui',mode,events:events.splice(0),observations:{react:'done',vue:'done'},snapshots:snapshots.splice(0)});
    await act(async()=>reactRoot.unmount());vueApp.unmount();
  }
  reports.push({development,runs});
}
dom.window.close();
process.stdout.write(JSON.stringify(reports));
