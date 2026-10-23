// Optional native observation bridge; business handlers never await this sink.
import {BOProbe} from '/bo_runtime.mjs';
try {
  const response=await fetch('/api/bo/config');
  if(response.ok) {
    const config=await response.json();
    const bo_probe=new BOProbe({project:config.project,buildId:config.build_id,endpoint:location.origin,token:config.token});
    window.bo_observe=(node,phase,values)=>bo_probe.record(node,phase,()=>values,{entity:'browser',attempt:'browser',scope:'application'});
  }
} catch { /* Observations cannot prevent page operations. */ }
