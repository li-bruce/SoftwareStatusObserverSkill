import React from 'react';
import {createRoot} from 'react-dom/client';
import {createApp} from 'vue';
import {ReactPanel} from '../src/ReactPanel';
import VuePanel from '../src/VuePanel.vue';
import {BOProbe} from '../bo_stategraph/bo_runtime.mjs';
import {bo_runner} from './bo_runner.mjs';
import project from '../bo_stategraph/project.json';
import settings from '../.stategraph/collector.json';

const bo_probe=new BOProbe({project,buildId:settings.build_id,endpoint:settings.endpoint,token:settings.token,enabled:settings.enabled!==false});
document.getElementById('mode')!.textContent='Mode: '+(project.selection.mode==='drive'?'Drive from the state declaration':'Observe application logic');
function bo_observe(node:string,phase:string,values:object){bo_probe.record(node,phase,()=>values);}
createRoot(document.getElementById('react')!).render(<ReactPanel run={bo_runner(project,bo_probe,'react')} bo_observe={bo_observe}/>);
createApp(VuePanel,{run:bo_runner(project,bo_probe,'vue'),bo_observe}).mount('#vue');
