// Application logic is independent of the collector, viewer and transport.
export function available(context) {return context.slots>0;}
export function advance(state,event,slots,executor=null) {
  if(executor) return executor.step(state,event,{slots});
  if(event==='start'&&state==='pending')return {state:slots>0?'running':'waiting',guards:{available:slots>0},event,payload:{}};
  if(event==='resume'&&state==='waiting'&&slots>0)return {state:'running',guards:{available:true},event,payload:{}};
  if(event==='finish'&&state==='running')return {state:'done',guards:{},event,payload:{}};
  throw Error('No enabled transition');
}
