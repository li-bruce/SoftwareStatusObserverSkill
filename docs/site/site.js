(() => {
  'use strict';
  const English = Object.fromEntries([...document.querySelectorAll('[data-i18n]')].map(el => [el.dataset.i18n, el.innerHTML]));
  Object.assign(English, {
    'business.title': 'What happens to an image?',
    'business.body': 'Upload, validate, notify, review, and exhibit remain connected. Login and other implemented features also need a place in the full project graph.',
    'business.evidence': 'Business meaning is confirmed in conversation. This example is intentionally limited to one operation.',
    'state.title': 'What state is it in?',
    'state.body': 'A review can be pending, approved, or rejected. Transitions show the event and condition. Where an operation has parallel activities, their individual states remain available below the summary.',
    'state.evidence': 'The declaration describes allowed transitions. Runtime facts show which transition actually happened.',
    'decision.title': 'Why was the action allowed?',
    'decision.body': 'Separate the rule, its input relationships, and this particular evaluation. Show individual conditions and the actual result without turning every possible permission into a permanent instance edge.',
    'decision.evidence': 'Skipped or unobserved conditions stay unknown. They are not inferred from the final outcome.',
    'function.title': 'Which function and which values?',
    'function.body': 'Explicit source anchors connect this behavior to important functions. Selected input, output, and state fields expose actual values without collecting every local variable.',
    'function.evidence': 'A possible call from static analysis is distinct from a captured call. Node identity survives a display-name change.',
    'source.title': 'Where is the implementation?',
    'source.body': 'Drill into indexed functions, signatures, nearby calls, and bound source. Language adapters return common source facts for Python, JS/TS, React, and Vue.',
    'source.evidence': 'Current adapters do not resolve every dynamic call. A complete all-source browser is a proposed extension.',
    'mixed.title': 'Combine the parts you need',
    'mixed.body': 'Business regions provide context while states, decisions, and functions share the canvas. Shared membership uses references to the same node; it does not duplicate execution.',
    'mixed.evidence': 'The real viewer also combines edge types, scope, depth, and search, and preserves boundaries to filtered nodes.',
    'graph.validate':'Validate image', 'graph.notify':'Notify reviewer', 'graph.reject':'Reject',
    'graph.approved':'Approved', 'graph.rejected':'Rejected', 'graph.reviewEvent':'approve / allowed',
    'graph.rejectEvent':'reject / allowed', 'graph.actor':'Actor ≠ uploader', 'graph.permission':'May review?',
    'graph.result':'Decision: true', 'graph.condition':'AND', 'graph.rules':'Review rule',
    'graph.call':'possible call', 'graph.input':'captured input', 'graph.output':'captured result',
    'graph.boundary':'Other project code', 'graph.unknown':'unresolved dynamic call',
    'graph.context':'Review operation', 'graph.mixedEdge':'depends on', 'graph.stateChange':'state change',
    'frame.title.0':'Upload received', 'frame.title.1':'Image content validated',
    'frame.title.2':'Reviewer notified', 'frame.title.3':'Review approved',
    'frame.key.state':'state', 'frame.key.valid':'valid_image', 'frame.key.message':'notification', 'frame.key.visible':'visible',
    'frame.none':'none', 'frame.unknown':'unknown', 'frame.staged':'staged', 'frame.pending':'pending',
    'frame.approved':'approved', 'frame.sent':'sent',
    'copy.done':'Copied', 'copy.failed':'Select and copy the prompt above.',
    'page.title':'Business Observer — See what your code is doing',
    'prompt':document.getElementById('install-prompt').textContent
  });
  let saved;
  try { saved = localStorage.getItem('bo.product.language'); } catch {}
  const requested = new URL(location.href).searchParams.get('lang');
  let language = requested === 'zh-CN' || requested === 'en' ? requested : (saved === 'zh-CN' ? saved : 'en');
  let level = 'business', frame = 0;
  const levels = ['business','state','decision','function','source','mixed'];
  const t = key => (language === 'zh-CN' && window.BO_PRODUCT_ZH?.[key]) || English[key] || key;
  const esc = value => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const text = (x,y,label,extra='') => '<text x="'+x+'" y="'+y+'" text-anchor="middle" '+extra+'>'+esc(label)+'</text>';
  function node(type,x,y,label,sub='') {
    const attrs = {'business':['#d3e0ff','#2457db'],'state':['#efe5f7','#8056a8'],'decision':['#fff1d4','#a76b13'],'function':['#d8f0ed','#087f80'],'value':['#fff','#087f80'],'source':['#f3f6fa','#7890a3']}[type];
    const style = 'fill="'+attrs[0]+'" stroke="'+attrs[1]+'" stroke-width="1.5"';
    let shape = '<circle cx="'+x+'" cy="'+y+'" r="23" '+style+'/>';
    if (type==='state') shape += '<circle cx="'+x+'" cy="'+y+'" r="18" fill="none" stroke="'+attrs[1]+'"/>';
    if (type==='decision') shape = '<path d="M'+x+' '+(y-25)+'L'+(x+25)+' '+y+'L'+x+' '+(y+25)+'L'+(x-25)+' '+y+'Z" '+style+'/>'+text(x,y+5,'?');
    if (type==='function') shape = '<path d="M'+(x-23)+' '+(y-13)+'L'+x+' '+(y-26)+'L'+(x+23)+' '+(y-13)+'V'+(y+13)+'L'+x+' '+(y+26)+'L'+(x-23)+' '+(y+13)+'Z" '+style+'/>'+text(x,y+5,'ƒ');
    if (type==='value'||type==='source') shape = '<rect x="'+(x-69)+'" y="'+(y-18)+'" width="138" height="36" rx="'+(type==='value'?18:5)+'" '+style+'/>';
    return '<g data-kind="'+type+'">'+shape+text(x,type==='value'||type==='source'?y+5:y+46,label,type==='value'?'style="font:11px Consolas,monospace"':'')+(sub?text(x,y+65,sub,'class="svg-small"'):'')+'</g>';
  }
  function edge(x1,y1,x2,y2,label='',dashed=false) {
    return '<g><path d="M'+x1+' '+y1+'L'+x2+' '+y2+'" fill="none" stroke="'+(dashed?'#7890a3':'#7590bd')+'" stroke-width="1.5" '+(dashed?'stroke-dasharray="5 5"':'')+' marker-end="url(#arrow)"/>'+(label?text((x1+x2)/2,(y1+y2)/2-9,label,'class="svg-small"'):'')+'</g>';
  }
  function diagram() {
    let drawing='';
    if(level==='business') {
      drawing += edge(87,100,267,100)+edge(290,127,87,245,t('graph.reject'))+edge(315,100,493,100)+edge(516,125,516,245)+edge(490,270,315,270,t('graph.reviewEvent'));
      drawing += node('business',65,100,t('graph.upload'))+node('decision',290,100,t('graph.validate'))+node('business',516,100,t('graph.notify'))+node('state',65,270,t('graph.rejected'))+node('business',516,270,t('graph.review'))+node('business',290,270,t('graph.exhibit'));
    } else if(level==='state') {
      drawing += edge(145,180,425,90,t('graph.reviewEvent'))+edge(145,190,425,270,t('graph.rejectEvent'));
      drawing += node('state',120,185,t('graph.pending'))+node('state',450,85,t('graph.approved'))+node('state',450,275,t('graph.rejected'));
    } else if(level==='decision') {
      drawing += '<rect x="55" y="48" width="470" height="242" rx="90" fill="#fff9ed" stroke="#e0c899"/>'+text(290,78,t('graph.rules'),'class="svg-title"');
      drawing += edge(178,145,267,188)+edge(178,245,267,202)+edge(316,195,382,195,t('graph.condition'));
      drawing += node('decision',152,130,t('graph.actor'))+node('decision',152,233,t('graph.permission'))+node('decision',290,195,t('graph.allowed'))+node('value',458,195,t('graph.result'));
    } else if(level==='function') {
      drawing += edge(141,80,290,154,t('graph.input'))+edge(315,181,437,87,t('graph.call'),true)+edge(315,195,437,274,t('graph.call'),true)+edge(274,207,162,280,t('graph.output'));
      drawing += node('value',110,70,'actor_id: reviewer')+node('function',290,185,'approve()')+node('function',458,70,'may_review()')+node('function',458,285,'save_review()')+node('value',120,290,'status: approved');
    } else if(level==='source') {
      drawing += '<rect x="35" y="45" width="230" height="255" rx="12" fill="#f3f6fa" stroke="#d4dee8"/><rect x="340" y="45" width="200" height="255" rx="12" fill="#f3f6fa" stroke="#d4dee8"/>';
      drawing += text(150,73,'review.py','class="svg-title"')+text(440,73,'store.py','class="svg-title"')+edge(174,140,411,140,t('graph.call'),true)+edge(150,166,150,242,t('graph.call'),true);
      drawing += node('function',150,130,'approve(image_id, actor_id)')+node('function',440,130,'save_review()')+node('function',150,255,'may_review()')+text(440,240,t('graph.boundary'),'class="svg-small"')+text(440,262,t('graph.unknown'),'class="svg-small"');
    } else {
      const chosen = new Set([...document.querySelectorAll('#mix-controls input:checked')].map(el=>el.value));
      drawing += '<circle cx="290" cy="190" r="148" fill="#edf2fe" stroke="#99b2ef"/>'+text(290,72,t('graph.context'),'class="svg-title"');
      drawing += edge(89,190,140,190)+edge(440,190,491,190)+node('business',65,190,t('graph.upload'))+node('business',515,190,t('graph.exhibit'));
      if(chosen.has('state')) drawing+=node('state',225,140,t('graph.pending'));
      if(chosen.has('decision')) drawing+=node('decision',355,140,t('graph.allowed'));
      if(chosen.has('function')) drawing+=node('function',290,245,'approve()');
      if(chosen.has('state')&&chosen.has('function')) drawing+=edge(240,167,277,215);
      if(chosen.has('decision')&&chosen.has('function')) drawing+=edge(340,166,303,216);
      if(!chosen.size) drawing+=text(290,195,t('graph.review'),'class="svg-small"');
    }
    return '<svg viewBox="0 0 580 360" role="img" aria-label="'+esc(t(level+'.title'))+'"><defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#7890a3"/></marker></defs>'+drawing+'</svg>';
  }
  function renderGraph() {
    document.querySelectorAll('[data-level]').forEach(el => {
      const active=el.dataset.level===level;
      el.setAttribute('aria-selected',String(active));el.tabIndex=active?0:-1;
    });
    document.getElementById('graph-panel').setAttribute('aria-labelledby','tab-'+level);
    document.getElementById('level-number').textContent=level==='mixed'?'MIX':String(levels.indexOf(level)+1).padStart(2,'0')+' / 05';
    for(const [target,key] of [['level-title','title'],['level-description','body'],['level-evidence','evidence']]) document.getElementById(target).textContent=t(level+'.'+key);
    document.getElementById('mix-controls').hidden=level!=='mixed';
    document.getElementById('concept-graph').innerHTML=diagram();
  }
  function renderFrame() {
    const frames = [
      {fn:'upload(file)', fields:[['state','none','staged'],['visible','false','false']]},
      {fn:'validate_image(file)', fields:[['valid','unknown','true'],['state','staged','pending']]},
      {fn:'notify_reviewer(image_id)', fields:[['message','none','sent'],['state','pending','pending']]},
      {fn:'approve(image_id, actor_id)', fields:[['state','pending','approved'],['visible','false','true']]}
    ];
    const current=frames[frame], value=v=>English['frame.'+v]?t('frame.'+v):v;
    document.querySelectorAll('[data-frame]').forEach(el=>el.setAttribute('aria-pressed',String(Number(el.dataset.frame)===frame)));
    document.getElementById('frame-content').innerHTML='<h3 class="frame-title">'+esc(t('frame.title.'+frame))+'</h3><dl class="frame-fields">'+current.fields.map(([key,a,b])=>'<div><dt>'+esc(t('frame.key.'+key))+'</dt><dd>'+esc(value(a))+'<span class="frame-arrow">→</span>'+esc(value(b))+'</dd></div>').join('')+'</dl><p class="frame-function">'+esc(current.fn)+'</p>';
  }
  function localize() {
    document.documentElement.lang=language;
    document.title=t('page.title');
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      const parts=t(el.dataset.i18n).split(/<br\s*\/?>/);
      el.replaceChildren();
      parts.forEach((part,i)=>{if(i)el.append(document.createElement('br'));el.append(document.createTextNode(part));});
    });
    const button=document.getElementById('language');
    button.textContent=language==='en'?'中文':'EN';
    button.setAttribute('aria-label',language==='en'?'Switch to Chinese':'Switch to English');
    document.getElementById('usage-link').href='https://github.com/li-bruce/SoftwareStatusObserverSkill/blob/main/docs/usage.'+(language==='en'?'en':'zh-CN')+'.md';
    document.getElementById('install-prompt').textContent=t('prompt');
    document.getElementById('copy-status').textContent='';
    renderGraph();renderFrame();
  }
  document.getElementById('language').addEventListener('click',()=>{
    language=language==='en'?'zh-CN':'en';
    try{localStorage.setItem('bo.product.language',language);}catch{}
    const url=new URL(location.href);url.searchParams.set('lang',language);history.replaceState(null,'',url);localize();
  });
  document.querySelectorAll('[data-level]').forEach(button=>{
    button.addEventListener('click',()=>{level=button.dataset.level;renderGraph();});
    button.addEventListener('keydown',event=>{
      let index=levels.indexOf(level);
      if(event.key==='ArrowRight')index=(index+1)%levels.length;
      else if(event.key==='ArrowLeft')index=(index+levels.length-1)%levels.length;
      else if(event.key==='Home')index=0;
      else if(event.key==='End')index=levels.length-1;else return;
      event.preventDefault();level=levels[index];renderGraph();document.getElementById('tab-'+level).focus();
    });
  });
  document.querySelectorAll('#mix-controls input').forEach(input=>input.addEventListener('change',renderGraph));
  document.querySelectorAll('[data-frame]').forEach(button=>button.addEventListener('click',()=>{frame=Number(button.dataset.frame);renderFrame();}));
  document.getElementById('copy-prompt').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(t('prompt'));document.getElementById('copy-status').textContent=t('copy.done');}
    catch{document.getElementById('copy-status').textContent=t('copy.failed');}
  });
  localize();
})();

