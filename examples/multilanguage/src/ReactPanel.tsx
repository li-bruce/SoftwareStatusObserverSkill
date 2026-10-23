import React, {useState} from 'react';
export function ReactPanel({run,bo_observe}: {run:(event:string)=>string,bo_observe?:Function}) {
  const [state,setState]=useState('pending');
  try {bo_observe?.('react.panel','read',{inputs:{has_handler:typeof run==='function'},outputs:{state}});} catch {}
  function start(){setState(run('start'));}
  function finish(){setState(run('finish'));}
  return <section><h2>React task</h2><p data-testid="react-state">{state}</p><button onClick={start}>Start React task</button><button onClick={finish}>Finish React task</button></section>;
}
