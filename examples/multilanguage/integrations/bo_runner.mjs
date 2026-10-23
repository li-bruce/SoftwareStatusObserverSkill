// Observation and native driver wiring. Actual decisions live in src/job.mjs.
import {advance,available} from '../src/job.mjs';
import {BOExecutor} from '../bo_stategraph/bo_runtime.mjs';
export function bo_runner(project,probe,framework=null,slots=1) {
  const executor=project.selection.mode==='drive'?new BOExecutor(project.model.machine,{available}):null;
  let state='pending',revision=0;
  const attempt=(framework||'node')+':'+crypto.randomUUID();
  function bo_report(event,guards=null,before=state) {
    const id=probe.record('js.advance','change',()=>({inputs:{state:before,event:event||'initial',slots,mode:project.selection.mode},outputs:{state}}),{entity:framework||'node',attempt,scope:'entity',revision});
    probe.snapshot(attempt,state,{slots},revision,id,{event,guards,payload:event?{}:null});
  }
  bo_report(null);
  return function bo_run(event) {
    const before=state,result=advance(state,event,slots,executor);state=result.state;revision++;
    if(framework)probe.record(framework+'.'+event,'return',()=>({inputs:{event},outputs:{state,before}}),{entity:framework,attempt,scope:'entity'});
    bo_report(event,result.guards,before);return state;
  };
}
