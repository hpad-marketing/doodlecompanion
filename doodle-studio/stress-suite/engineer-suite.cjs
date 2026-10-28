// Doodle Studio pre-UX-pass engineering suite.
// Covers the categories studios run on editors before polish: command sweep, panel inventory/layout lint,
// input boundary fuzz, undo/redo model checks, save/load round trip, corrupt-file handling,
// render determinism, seeded monkey test, soak/leak metrics and playback frame-time budget.
// Usage: node engineer-suite.cjs <index.studio.html> [--only=a,b] [--seed=N] [--quick]
const fs=require('fs'),http=require('http'),path=require('path'),crypto=require('crypto');const {chromium}=require('playwright');
const HTML=path.resolve(process.argv[2]||'index.studio.html');
const arg=(k,d)=>{const a=process.argv.find(x=>x.startsWith('--'+k+'='));return a?a.split('=')[1]:d;};
const ONLY=arg('only','')?arg('only').split(','):null,SEED=+arg('seed',20261027),QUICK=process.argv.includes('--quick');
const OUT=path.resolve(arg('out',path.join(__dirname,'results')));fs.mkdirSync(OUT,{recursive:true});
const results=[];
const test=(group,name,ok,detail)=>{results.push({group,name,ok:!!ok,detail:ok?undefined:detail});console.log((ok?'PASS ':'FAIL ')+'['+group+'] '+name+(ok?'':' '+JSON.stringify(detail??'').slice(0,400)));};
const info=(group,name,data)=>{results.push({group,name,ok:true,info:data});console.log('INFO ['+group+'] '+name+' '+JSON.stringify(data).slice(0,400));};
const rng=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};
// Controls a monkey must never press: file pickers, exports, recording, destructive clears, phone pairing, quitting.
const DANGER=/export|record|capture|clear all|delete all|reset all|quit|exit|pair|phone|sync|open project|project files|save|import|choose file|browse|upload|microphone|camera access|remove shot|delete shot|restore|rollback|update/i;
const SKIP_SEL='input[type=file],#studio-export,#clear-all-keys,#rec,#capture-begin,#voice-take-begin,#project-save,#project-save-quick,#timeline-detach,[data-danger]';

let server;
async function boot(browser,{width=1600,height=900}={}){
 const p=await browser.newPage({viewport:{width,height}}),log={errors:[],consoleErrors:[],dialogs:0};
 p.on('pageerror',e=>log.errors.push(e.message.split('\n')[0]));
 p.on('console',m=>{if(m.type()==='error')log.consoleErrors.push(m.text().slice(0,200));});
 p.on('dialog',d=>{log.dialogs++;d.dismiss().catch(()=>{});});
 // Popups/downloads should never be triggered by the monkey; record them if they are.
 p.on('download',d=>{log.downloads=(log.downloads||0)+1;d.cancel().catch(()=>{});});
 await p.addInitScript(()=>{window.__longTasks=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__longTasks.push(Math.round(e.duration));}).observe({type:'longtask',buffered:true});}catch{}
  window.__loaf=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__loaf.push(Math.round(e.duration));}).observe({type:'long-animation-frame',buffered:true});}catch{}
  window.addEventListener('unhandledrejection',e=>{(window.__rejections=window.__rejections||[]).push(String(e.reason&&e.reason.message||e.reason).slice(0,200));});});
 const t0=Date.now();await p.goto('http://127.0.0.1:'+server.address().port);
 await p.waitForFunction(()=>window.BunnyStudio&&window.BunnyProject&&window.BunnyCommands&&window.DoodleDrawing,null,{timeout:120000});
 await p.waitForTimeout(1200);await p.evaluate(()=>document.querySelector('#studio-home')?.close());
 log.bootMs=Date.now()-t0;return {p,log};
}
const ev=(p,fn,a)=>p.evaluate(fn,a);
const responsive=p=>Promise.race([p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>r(true)))),new Promise(r=>setTimeout(()=>r(false),5000))]);
const closeAll=p=>p.evaluate(()=>{for(const d of document.querySelectorAll('dialog[open]'))d.close();try{BunnyStudio.menu?.open&&BunnyStudio.menu.close();}catch{}document.activeElement?.blur?.();});
const projectJSON=p=>p.evaluate(async()=>{const b=await BunnyProject.bundle();return JSON.stringify(b.project);});
// Fields that legitimately change with no user edit (timestamps, view state) are left out of model equality.
const norm=s=>{const o=JSON.parse(s);const drop=(x)=>{if(Array.isArray(x))return x.map(drop);if(x&&typeof x==='object'){const r={};for(const k of Object.keys(x).sort()){if(/^(modified|updated|updatedAt|savedAt|lastSaved|touched|time|opened)$/i.test(k))continue;if(Array.isArray(x[k])&&!x[k].length)continue;r[k]=drop(x[k]);}return r;}return x;};return JSON.stringify(drop(o));};
const hash=s=>crypto.createHash('sha1').update(s).digest('hex').slice(0,12);
const workspaces=p=>ev(p,()=>[...document.querySelectorAll('#studio-tabs button[data-workspace]')].map(b=>b.dataset.workspace));
const setWS=async(p,w)=>{await p.click('#studio-tabs button[data-workspace="'+w+'"]');await p.waitForTimeout(250);};
// Scan a project for values that should never reach disk.
const badNumbers=p=>ev(p,async()=>{const pr=(await BunnyProject.bundle()).project,bad=[];const walk=(x,path)=>{if(bad.length>20)return;if(typeof x==='number'&&!Number.isFinite(x))bad.push(path);else if(x&&typeof x==='object')for(const k in x)walk(x[k],path+'.'+k);};walk(pr,'p');
 for(const [t,a]of Object.entries(pr.keys||{}))for(const k of a||[])if(typeof k.t!=='number'||k.t<0||typeof k.v!=='number')bad.push('key '+t+'@'+k.t);return bad;});

const SUITES={
 // A. Boot health and baseline console.
 async boot(browser){const {p,log}=await boot(browser);
  test('boot','Loads in under 20 s',log.bootMs<20000,log.bootMs);info('boot','Boot time ms',log.bootMs);
  test('boot','No page errors on load',log.errors.length===0,log.errors);
  test('boot','No console errors on load',log.consoleErrors.length===0,log.consoleErrors.slice(0,5));
  const rej=await ev(p,()=>window.__rejections||[]);test('boot','No unhandled promise rejections on load',rej.length===0,rej);
  const lt=await ev(p,()=>window.__longTasks);info('boot','Long tasks during boot (ms)',{count:lt.length,max:Math.max(0,...lt)});
  await p.close();},

 // B. Run every registered command (the command palette is the app's own list of features).
 async commands(browser){const {p,log}=await boot(browser);const ws=await workspaces(p);const fails=[];let ran=0;
  for(const w of ws){await setWS(p,w);
   const ids=await ev(p,()=>BunnyCommands.list().filter(c=>!c.disabled).map(c=>c.id+'|'+c.title));
   for(const row of ids){const [id,title]=row.split('|');if(/^project:save|^export:|^sources:check/.test(id)||DANGER.test(title)&&!/^tool:|^workspace:|^part:/.test(id))continue;
    const e0=log.errors.length;const r=await ev(p,async id=>{try{await Promise.race([BunnyCommands.run(id),new Promise((_,j)=>setTimeout(()=>j(Error('timeout')),8000))]);return '';}catch(e){return e.message;}},id);
    ran++;await p.waitForTimeout(120);await closeAll(p);
    if(id==='transport:play'){await ev(p,()=>{const b=document.querySelector('#play');if(/Pause/i.test(b?.title||''))b.click();});}
    if(log.errors.length>e0||r&&!/unavailable|Take project control|Finish or cancel|No changes/i.test(r))fails.push({w,id,r,err:log.errors.slice(e0)});}
   await setWS(p,w);}
  test('commands','Every enabled command runs in every workspace ('+ran+' runs) without errors',fails.length===0,fails.slice(0,8));
  test('commands','App responsive after the command sweep',await responsive(p));
  // Menu bar: every menu opens with labelled items, and every safe item runs without errors.
  const menus=await ev(p,()=>[...document.querySelectorAll('.menu[data-menu]')].map(m=>m.dataset.menu));
  const menuIssues=[],itemFails=[];let itemsRun=0;
  for(const id of menus){const items=await ev(p,id=>{DoodleMenu.open(id);const list=[...document.querySelectorAll('[data-menu-list="'+id+'"] button')].filter(b=>b.offsetParent);const out=list.map((b,i)=>({i,label:b.textContent.trim(),disabled:b.disabled,named:!!(b.textContent.trim()||b.title||b.getAttribute('aria-label'))}));DoodleMenu.close();return out;},id);
   if(!items.length||items.some(x=>!x.named))menuIssues.push({id,n:items.length});
   for(const it of items){if(it.disabled||DANGER.test(it.label)||/keyboard shortcuts|preferences|help and licenses|clear|home/i.test(it.label))continue;const e0=log.errors.length;
    await ev(p,([id,i])=>{DoodleMenu.open(id);const b=[...document.querySelectorAll('[data-menu-list="'+id+'"] button')].filter(b=>b.offsetParent)[i];b?.click();},[id,it.i]);itemsRun++;await p.waitForTimeout(150);await closeAll(p);await ev(p,()=>{DoodleMenu.close?.();const pl=document.querySelector('#play');if(/Pause/i.test(pl?.title||''))pl.click();});
    if(log.errors.length>e0)itemFails.push({menu:id,item:it.label,err:log.errors.slice(e0)});}}
  test('commands','Every menu-bar menu ('+menus.length+') opens with labelled items',menus.length>0&&menuIssues.length===0,menuIssues);
  test('commands','Every safe menu item ('+itemsRun+') runs without errors',itemFails.length===0,itemFails.slice(0,8));
  test('commands','App responsive after the menu sweep',await responsive(p));
  await p.close();},

 // C. Panel inventory + layout lint at the two common desktop sizes.
 async layout(browser){for(const [W,H,OPEN]of [[1366,768,false],[1920,1080,false],[1366,768,true]]){const {p,log}=await boot(browser,{width:W,height:H});const ws=await workspaces(p);const issues={overflow:[],unlabeled:[],tiny:[],overlap:[],clipped:[],truncated:[]};let controls=0;
  for(const w of ws){await setWS(p,w);
   const subs=await ev(p,w=>[...document.querySelectorAll('#workspace-'+w+' [data-context-tool]')].filter(b=>b.offsetParent).map(b=>b.dataset.contextTool),w);
   for(const s of [null,...subs]){if(s)await ev(p,([w,s])=>document.querySelector('#workspace-'+w+' [data-context-tool="'+s+'"]').click(),[w,s]);await p.waitForTimeout(150);
    if(OPEN)await ev(p,()=>{for(const d of document.querySelectorAll('#studio-panel details:not([open]), #desktop-timeline details:not([open])')){d.dataset.lintOpened='1';d.open=true;}});await p.waitForTimeout(OPEN?120:0);
    const r=await ev(p,async([w,s])=>{const vis=e=>{const r=e.getBoundingClientRect(),cs=getComputedStyle(e);return r.width>0&&r.height>0&&cs.visibility!=='hidden'&&cs.display!=='none'&&+cs.opacity>0.05&&!e.closest('dialog:not([open]),[hidden],[inert]')&&!(e.closest('details:not([open])')&&!e.closest('summary'));};
     const ctl=[...document.querySelectorAll('button,input:not([type=hidden]),select,textarea,[role=button],[role=tab]')].filter(e=>!(e instanceof SVGElement)).filter(vis).filter(e=>!e.checkVisibility||e.checkVisibility({checkVisibilityCSS:true}));// closed <details> keep layout boxes in Chromium; skip what checkVisibility() hides
     const name=e=>(e.getAttribute('aria-label')||e.title||e.textContent||e.labels?.[0]?.textContent||e.placeholder||e.closest('label')?.textContent||'').trim();
     const where=w+(s?'/'+s:'');const id=e=>where+' '+(e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+[...e.classList].slice(0,2).join('.'))+' "'+name(e).slice(0,24)+'"';
     const out={n:ctl.length,overflow:[],unlabeled:[],tiny:[],overlap:[],clipped:[],truncated:[]};
     if(document.documentElement.scrollWidth>innerWidth+1)out.overflow.push(where+' page scrollWidth '+document.documentElement.scrollWidth);
     // Geometry first, with nothing scrolled, so every rect comes from the same layout.
     const rects=ctl.map(e=>[e,e.getBoundingClientRect()]);
     for(const [e,r]of rects){
      if(!name(e)&&e.type!=='range'&&e.type!=='color')out.unlabeled.push(id(e));
      if(e.type!=='checkbox'&&e.type!=='radio'&&(r.width<16||r.height<16))out.tiny.push(id(e)+' '+Math.round(r.width)+'x'+Math.round(r.height));
      if(e.tagName==='BUTTON'&&e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflow!=='visible')out.truncated.push(id(e)+' '+e.scrollWidth+'>'+e.clientWidth);}
     for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){const [a,ra]=rects[i],[b,rb]=rects[j];if(a.contains(b)||b.contains(a))continue;const ix=Math.max(0,Math.min(ra.right,rb.right)-Math.max(ra.left,rb.left)),iy=Math.max(0,Math.min(ra.bottom,rb.bottom)-Math.max(ra.top,rb.top));const ar=Math.min(ra.width*ra.height,rb.width*rb.height);
      // Both controls must actually show in the shared area: sample a few points and require each to win at least one.
      if(ar>0&&ix*iy/ar>0.4){const x0=Math.max(ra.left,rb.left),x1=Math.min(ra.right,rb.right),y0=Math.max(ra.top,rb.top),y1=Math.min(ra.bottom,rb.bottom);let wa=0,wb=0;for(const fx of [.2,.5,.8])for(const fy of [.2,.5,.8]){const t=document.elementFromPoint(x0+(x1-x0)*fx,y0+(y1-y0)*fy);if(t&&a.contains(t))wa++;if(t&&b.contains(t))wb++;}if(wa&&wb)out.overlap.push(id(a)+' x '+id(b));}}
     // Reachability: scroll only containers a user can scroll, restore every one afterwards, then hit-test the centre.
     const pending=[];const userScrollers=e=>{const list=[];for(let a=e.parentElement;a&&a!==document.documentElement;a=a.parentElement){const cs=getComputedStyle(a);if((/(auto|scroll)/.test(cs.overflowY)&&a.scrollHeight>a.clientHeight+1)||(/(auto|scroll)/.test(cs.overflowX)&&a.scrollWidth>a.clientWidth+1))list.push(a);}return list;};
     for(const [e]of rects){const sc=userScrollers(e),saved=sc.map(a=>[a,a.scrollTop,a.scrollLeft]);
      for(const a of sc){const q=e.getBoundingClientRect(),c=a.getBoundingClientRect();if(q.top<c.top)a.scrollTop-=c.top-q.top+4;else if(q.bottom>c.bottom)a.scrollTop+=Math.min(q.top-c.top-4,q.bottom-c.bottom+4);if(q.left<c.left)a.scrollLeft-=c.left-q.left+4;else if(q.right>c.right)a.scrollLeft+=Math.min(q.left-c.left-4,q.right-c.right+4);}
      const q=e.getBoundingClientRect(),cx=q.left+q.width/2,cy=q.top+q.height/2;let ok=cx>=0&&cy>=0&&cx<=innerWidth&&cy<=innerHeight,under='';
      if(ok){const hit=document.elementFromPoint(cx,cy);ok=!!hit&&(hit===e||e.contains(hit)||(hit.tagName==='LABEL'&&hit.contains(e))||!!(e.labels&&[...e.labels].some(l=>l.contains(hit))));if(!ok&&hit)under=' under '+(hit.id?'#'+hit.id:hit.tagName.toLowerCase()+'.'+[...hit.classList].slice(0,2).join('.'));}
      for(const [a,t,l]of saved){a.scrollTop=t;a.scrollLeft=l;}
      if(!ok)pending.push([e,under+(sc.length?'':' (no scrollable parent)')]);}
     // Paged panels (tool shelves) bring a control into view on focus, wheel or the page buttons: try focus, the keyboard route.
     for(const [e,why]of pending){try{e.focus({preventScroll:false});}catch{}await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      const q=e.getBoundingClientRect(),cx=q.left+q.width/2,cy=q.top+q.height/2;let ok=document.activeElement===e&&cx>=0&&cy>=0&&cx<=innerWidth&&cy<=innerHeight;
      if(ok){const hit=document.elementFromPoint(cx,cy);ok=!!hit&&(hit===e||e.contains(hit)||(hit.tagName==='LABEL'&&hit.contains(e))||!!(e.labels&&[...e.labels].some(l=>l.contains(hit))));}
      if(!ok)out.clipped.push(id(e)+why+(document.activeElement===e?'':' (not focusable)'));e.blur?.();}
     for(let k=0;k<20&&document.querySelector('#tool-page-prev')&&!document.querySelector('#tool-page-prev').disabled;k++)document.querySelector('#tool-page-prev').click();
     return out;},[w,s]);
    controls+=r.n;for(const k of Object.keys(issues))issues[k].push(...(r[k]||[]));}}
  const u=a=>[...new Set(a)];const LBL=W+'x'+H+(OPEN?' (all sections open)':'');
  info('layout',LBL+' visible controls checked',controls);
  test('layout',LBL+': no page-level horizontal overflow',!issues.overflow.length,u(issues.overflow));
  test('layout',LBL+': every visible control has a name or tooltip',!issues.unlabeled.length,{n:u(issues.unlabeled).length,sample:u(issues.unlabeled).slice(0,12)});
  test('layout',LBL+': no control smaller than 16 px',!issues.tiny.length,{n:u(issues.tiny).length,sample:u(issues.tiny).slice(0,12)});
  test('layout',LBL+': no overlapping controls',!issues.overlap.length,{n:u(issues.overlap).length,sample:u(issues.overlap).slice(0,10)});
  test('layout',LBL+': no button text is truncated',!issues.truncated.length,{n:u(issues.truncated).length,sample:u(issues.truncated).slice(0,12)});
  test('layout',LBL+': every control can be scrolled into view and clicked (not covered)',!issues.clipped.length,{n:u(issues.clipped).length,sample:u(issues.clipped).slice(0,12)});
  fs.writeFileSync(path.join(OUT,'layout-'+W+'x'+H+(OPEN?'-open':'')+'.json'),JSON.stringify(Object.fromEntries(Object.entries(issues).map(([k,v])=>[k,u(v)])),null,1));
  test('layout',LBL+': no errors while visiting every panel',log.errors.length===0,log.errors.slice(0,5));
  await p.screenshot({path:path.join(OUT,'layout-'+W+'x'+H+(OPEN?'-open':'')+'.png')});await p.close();}},

 // D. Boundary values in every visible number/range/text field.
 async inputs(browser){const {p,log}=await boot(browser);const ws=await workspaces(p);const fails=[];let tried=0;
  const VALUES=['-999999','999999','0','-0','0.0001','1e309','abc','','  ','12abc','NaN','-1'];
  for(const w of ws){await setWS(p,w);
   const n=await ev(p,()=>{window.__fz=[...document.querySelectorAll('input[type=number],input[type=range],input[type=text]:not([type=search]),input:not([type])')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height&&!e.disabled&&!e.readOnly&&!e.closest('dialog');});return window.__fz.length;});
   for(let i=0;i<n;i++){for(const v of (QUICK?VALUES.slice(0,6):VALUES)){const e0=log.errors.length;
     await ev(p,([i,v])=>{const e=window.__fz[i];if(!e||!e.isConnected)return;const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));},[i,v]);tried++;
     if(log.errors.length>e0){const id=await ev(p,i=>{const e=window.__fz[i];return e?(e.id||e.name||e.getAttribute('aria-label')||e.title||e.className):'gone'},i);fails.push({w,field:id,value:v,err:log.errors.slice(e0)});}}}
   await ev(p,()=>document.activeElement?.blur());}
  await p.waitForTimeout(500);
  test('inputs','Boundary values in '+tried+' field edits raise no errors',fails.length===0,fails.slice(0,10));
  const bad=await badNumbers(p);test('inputs','Project holds no NaN/Infinity/negative times after fuzzing',bad.length===0,bad);
  const v=await ev(p,async()=>{try{BunnyProject.validate((await BunnyProject.bundle()).project);return '';}catch(e){return e.message}});test('inputs','Project still validates after fuzzing',!v,v);
  test('inputs','App responsive after fuzzing',await responsive(p));await p.close();},

 // E. Undo model check: every edit must be undoable back to the exact earlier state.
 async undo(browser){const {p,log}=await boot(browser);const r=rng(SEED);await setWS(p,'pose');
  const states=[norm(await projectJSON(p))];const steps=QUICK?12:30;const actions=[];
  const sliders=await ev(p,()=>[...document.querySelectorAll('#pose-inspector input[type=range]')].filter(e=>e.offsetParent&&!e.disabled).length);
  for(let i=0;i<steps;i++){const kind=r();const frame=Math.floor(r()*120);
   await ev(p,f=>DoodleDrawing.seek(f),frame);await p.waitForTimeout(40);
   if(kind<0.7&&sliders){const s=Math.floor(r()*sliders),val=r();
    await ev(p,([s,val])=>{const e=[...document.querySelectorAll('#pose-inspector input[type=range]')].filter(e=>e.offsetParent&&!e.disabled)[s];const v=+e.min+(+e.max-+e.min)*val;e.value=String(v);e.dispatchEvent(new Event('pointerdown',{bubbles:true}));e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.dispatchEvent(new Event('pointerup',{bubbles:true}));},[s,val]);actions.push('slider'+s+'@'+frame);}
   else{await ev(p,()=>document.querySelector('#keys')?.click());actions.push('addkey@'+frame);}
   await p.waitForTimeout(80);const st=norm(await projectJSON(p));if(st!==states.at(-1))states.push(st);}
  info('undo','Distinct model states produced by '+steps+' random edits',states.length-1);
  const mism=[];for(let i=states.length-2;i>=0;i--){await ev(p,()=>document.querySelector('#undo').click());await p.waitForTimeout(80);const now=norm(await projectJSON(p));if(now!==states[i]){mism.push({expectState:i,got:hash(now),want:hash(states[i])});break;}}
  test('undo','Undo walks back through every edit to the exact earlier state ('+(states.length-1)+' steps)',mism.length===0,{mism,actions});
  // Redo, if the build has it, must replay to the latest state.
  const hasRedo=await ev(p,()=>!!(document.querySelector('#ux-redo')||[...document.querySelectorAll('button')].find(b=>/^redo/i.test(b.title||b.textContent))));
  if(hasRedo){for(let i=1;i<states.length;i++){await p.keyboard.press('Control+Shift+z');await p.waitForTimeout(60);}const end=norm(await projectJSON(p));test('undo','Redo replays back to the final state',end===states.at(-1),{got:hash(end),want:hash(states.at(-1))});}
  else{await p.keyboard.press('Control+Shift+z');await p.waitForTimeout(150);const end=norm(await projectJSON(p));test('undo','Ctrl+Shift+Z (menu says Redo) restores the last undone edit',end===states[1]||end!==states[0],{note:'menu lists Redo Ctrl+Shift+Z'});}
  // Drawing edits share the same undo.
  await setWS(p,'draw');await ev(p,()=>document.querySelector('#draw-add-above')?.click());await p.waitForTimeout(200);const before=norm(await projectJSON(p));
  const st=await p.locator('#stage').boundingBox();await p.mouse.move(st.x+st.width*.4,st.y+st.height*.4);await p.mouse.down();await p.mouse.move(st.x+st.width*.6,st.y+st.height*.5,{steps:10});await p.mouse.up();await p.waitForTimeout(200);
  const strokes=()=>ev(p,()=>{const l=DoodleDrawing._fx?.find(DoodleDrawing.selected);return (l?.cels||[]).reduce((n,c)=>n+(c.strokes?.length||0),0);});const s1=await strokes();
  await p.keyboard.press('Control+z');await p.waitForTimeout(250);const s2=await strokes();
  test('undo','Ctrl+Z removes the last drawn stroke',s1>0&&s2===s1-1,{s1,s2});
  test('undo','No errors during undo checks',log.errors.length===0,log.errors.slice(0,5));await p.close();},

 // F. Save/load round trip and idempotence, plus a heavy synthetic project.
 async roundtrip(browser){const {p,log}=await boot(browser);
  const a=await ev(p,async()=>JSON.stringify(await BunnyProject.bundle()));
  await ev(p,async a=>{await BunnyProject.accept(JSON.parse(a));},a);await p.waitForTimeout(400);const b=await ev(p,async()=>JSON.stringify(await BunnyProject.bundle()));
  test('roundtrip','Load(save(project)) == project (model unchanged)',norm(JSON.parse(a).project?JSON.stringify(JSON.parse(a).project):a)===norm(JSON.stringify(JSON.parse(b).project)),{a:a.length,b:b.length});
  await ev(p,async b=>{await BunnyProject.accept(JSON.parse(b));},b);await p.waitForTimeout(300);const c=await ev(p,async()=>JSON.stringify((await BunnyProject.bundle()).project));
  test('roundtrip','Second round trip is identical (idempotent)',norm(c)===norm(JSON.stringify(JSON.parse(b).project)));
  // Heavy project: 60 s, every track keyed every 100 ms.
  const heavy=await ev(p,async()=>{const pr=JSON.parse(JSON.stringify((await BunnyProject.bundle()).project));let n=0;for(const t of Object.keys(pr.keys)){const a=[];for(let ms=0;ms<=60000;ms+=100){a.push({uid:'h'+(n++),t:ms,v:0,ease:'auto'});}pr.keys[t]=a;}
   pr.cues=Array.from({length:200},(_,i)=>({uid:'c'+i,text:'Line '+i+' of the stress caption test',start:i*300,end:i*300+280}));
   const t0=performance.now();await BunnyProject.accept({format:'BunnyStudio',version:1,project:pr});const load=performance.now()-t0;
   const t1=performance.now();for(const f of [0,450,900,1350,1799,10,1700])DoodleDrawing.seek(f);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));const seek=(performance.now()-t1)/7;
   const t2=performance.now();const s=JSON.stringify(await BunnyProject.bundle());const save=performance.now()-t2;return {keys:n,load:Math.round(load),seekAvg:Math.round(seek),save:Math.round(save),mb:+(s.length/1e6).toFixed(1)};});
  info('roundtrip','Heavy project timings (ms)',heavy);
  test('roundtrip','Heavy project ('+heavy.keys+' keys) loads in < 5 s',heavy.load<5000,heavy);
  test('roundtrip','Heavy project seeks in < 200 ms per frame',heavy.seekAvg<200,heavy);
  test('roundtrip','Heavy project saves in < 3 s',heavy.save<3000,heavy);
  test('roundtrip','App responsive with heavy project',await responsive(p));
  test('roundtrip','No errors in round-trip checks',log.errors.length===0,log.errors.slice(0,5));await p.close();},

 // G. Corrupt / hostile project files must be refused or cleaned, never crash or wipe the open project.
 async corrupt(browser){const {p,log}=await boot(browser);
  await ev(p,()=>document.querySelector('#keys')?.click());await p.waitForTimeout(200);const raw=await projectJSON(p),before=norm(raw);
  const cases={empty:'{}',nullProject:'{"format":"BunnyStudio","version":1,"project":null}',arrays:'{"project":{"keys":[],"clips":{},"cues":"x"}}',
   nanTimes:'{"project":{"keys":{"x":[{"uid":"a","t":"NaN","v":1},{"uid":"b","t":-5,"v":1},{"uid":"c","t":100,"v":1e400}]},"clips":[{"type":"zzz","start":0,"end":1}],"cues":[{"text":5,"start":0,"end":1},{"text":"ok","start":10,"end":5}]}}',
   badUid:'{"project":{"keys":{"x":[{"uid":"../../etc<script>","t":0,"v":0}]},"clips":[],"cues":[]}}',
   svgScript:'{"project":{"keys":{},"cues":[],"clips":[{"uid":"s","type":"doodle","start":0,"end":1000,"svg":"<svg xmlns=\\"http://www.w3.org/2000/svg\\" onload=\\"window.__pwned=1\\"><script>window.__pwned=1</script><image href=\\"javascript:window.__pwned=1\\"/><path d=\\"M0 0L10 10\\"/></svg>"}]}}',
   badAudio:'{"audio":"javascript:alert(1)","project":{"keys":{},"clips":[],"cues":[]}}',
   deep:JSON.stringify({project:{keys:{},clips:[],cues:[],extra:JSON.parse('['.repeat(2000)+']'.repeat(2000))}}),
   huge:JSON.stringify({project:{keys:{x:Array.from({length:200000},(_,i)=>({uid:'k'+i,t:i,v:0}))},clips:[],cues:[]}})};
  const res={};
  for(const [name,text]of Object.entries(cases)){const e0=log.errors.length;
   const r=await ev(p,async t=>{try{await Promise.race([BunnyProject.accept(JSON.parse(t),{recordUndo:false}),new Promise((_,j)=>setTimeout(()=>j(Error('timeout')),15000))]);return 'accepted';}catch(e){return 'refused: '+e.message.slice(0,80);}},text);
   await p.waitForTimeout(200);res[name]={r,errors:log.errors.slice(e0),bad:(await badNumbers(p)).length,resp:await responsive(p)};
   if(r==='accepted'){await ev(p,async b=>{await BunnyProject.accept({format:'BunnyStudio',version:1,project:JSON.parse(b)},{recordUndo:false});},raw);await p.waitForTimeout(200);}}
  const pwned=await ev(p,()=>!!window.__pwned);
  for(const [k,v]of Object.entries(res))test('corrupt','"'+k+'" file: '+v.r.slice(0,60)+' with no crash and no bad numbers',!v.errors.length&&!v.bad&&v.resp,v);
  test('corrupt','Hostile SVG/audio never runs script',!pwned);
  const after=norm(await projectJSON(p));test('corrupt','The open project survives refused files intact',after===before,{before:hash(before),after:hash(after)});
  await p.close();},

 // H. Determinism: the same frame renders the same, however you reach it.
 async determinism(browser){const {p,log}=await boot(browser);
  // Give the default shot some motion first.
  await ev(p,async()=>{const pr=JSON.parse(JSON.stringify((await BunnyProject.bundle()).project));const ids=Object.keys(pr.keys).slice(0,30);let n=0;for(const t of ids)pr.keys[t]=[0,700,1500,2600].map((ms,i)=>({uid:'d'+(n++),t:ms,v:(i%2?0.6:-0.4)*(i+1)/4,ease:'auto'}));await BunnyProject.accept({format:'BunnyStudio',version:1,project:pr});});
  const grab=f=>ev(p,async f=>{DoodleDrawing.seek(f);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return ['#projected-rig','#drawing-above','#drawing-behind','#props-layer','#caption-layer'].map(s=>document.querySelector(s)?.innerHTML||'').join('|');},f);
  const frames=[0,9,21,33,45,61,77];const direct={};for(const f of frames)direct[f]=await grab(f);
  const scrambled={};for(const f of [...frames].reverse()){await grab(Math.floor(Math.random()*90));scrambled[f]=await grab(f);}
  const diffs=frames.filter(f=>direct[f]!==scrambled[f]);
  test('determinism','Same frame renders identically regardless of seek order',diffs.length===0,{diffs});
  await ev(p,()=>document.querySelector('#play').click());await p.waitForTimeout(1200);await ev(p,()=>document.querySelector('#play').click());await p.waitForTimeout(200);
  const afterPlay=await grab(21);test('determinism','Frame 21 matches after playback (no leftover playback state)',afterPlay===direct[21]);
  test('determinism','Different frames actually differ (test is meaningful)',new Set(Object.values(direct)).size>=frames.length-1,{distinct:new Set(Object.values(direct)).size});
  test('determinism','No errors in determinism checks',log.errors.length===0,log.errors.slice(0,5));await p.close();},

 // I. Seeded monkey: random clicks, selects, sliders, keys and canvas drags across all workspaces.
 async monkey(browser){const {p,log}=await boot(browser);const r=rng(SEED+1);const ws=await workspaces(p);const N=QUICK?250:800;const trail=[];let firstErr=null;
  const KEYS=['k','b','v','t','c','e','l','o','q','w','r','m','Home','End',',','.',';',"'",'ArrowLeft','ArrowRight','Delete','Escape','Control+z','Control+Shift+z','Control+c','Control+v','Control+d','Control+a','F5','F6','F7','=','-','\\','Space','1','2','3','4','5','6','7'];
  for(let i=0;i<N;i++){const x=r();let act;
   if(x<0.08){const w=ws[Math.floor(r()*ws.length)];await closeAll(p);await ev(p,w=>document.querySelector('#studio-tabs button[data-workspace="'+w+'"]').click(),w);await p.waitForTimeout(150);act='ws '+w;}
   else if(x<0.55){const t=await ev(p,([skip,danger,pick])=>{const els=[...document.querySelectorAll('button,[role=button],[role=tab],input[type=checkbox],input[type=radio],summary')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height&&!e.disabled&&!e.matches(skip)&&!new RegExp(danger,'i').test((e.title||'')+' '+e.textContent+' '+(e.getAttribute('aria-label')||''))&&r.top>=0&&r.left>=0&&r.bottom<=innerHeight&&r.right<=innerWidth;});const e=els[Math.floor(pick*els.length)];if(!e)return null;const b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2,(e.id||'')+' '+(e.title||e.textContent).trim().slice(0,30)];},[SKIP_SEL,DANGER.source,r()]);
    if(t){await p.mouse.click(t[0],t[1]);act='click '+t[2];}}
   else if(x<0.65){const t=await ev(p,([pick,val])=>{const els=[...document.querySelectorAll('select,input[type=range]')].filter(e=>e.offsetParent&&!e.disabled&&!e.closest('dialog:not([open])'));const e=els[Math.floor(pick*els.length)];if(!e)return null;if(e.tagName==='SELECT'){if(!e.options.length)return null;e.selectedIndex=Math.floor(val*e.options.length);}else e.value=String(+e.min+(+e.max-+e.min)*val);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return (e.id||e.name||e.tagName)+'='+e.value;},[r(),r()]);act='set '+t;}
   else if(x<0.85){const k=KEYS[Math.floor(r()*KEYS.length)];await ev(p,()=>{if(document.activeElement&&/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))document.activeElement.blur();});await p.keyboard.press(k);act='key '+k;}
   else{const st=await p.locator('#stage').boundingBox().catch(()=>null);if(st){const a=[st.x+st.width*r(),st.y+st.height*r()],b=[st.x+st.width*r(),st.y+st.height*r()];await p.mouse.move(a[0],a[1]);await p.mouse.down();await p.mouse.move(b[0],b[1],{steps:6});await p.mouse.up();act='drag stage';}}
   trail.push(act);if(trail.length>25)trail.shift();
   {const modal=await ev(p,()=>{const d=document.querySelector('dialog[open]');return d?(d.id||d.className||'dialog'):null;});if(modal&&i%3===0)act+=' (modal '+modal+')';}
   if(i%4===0){await ev(p,()=>{for(const d of document.querySelectorAll('dialog[open]'))d.close();const pl=document.querySelector('#play');if(/Pause/i.test(pl?.title||''))pl.click();});}
   if(log.errors.length&&!firstErr)firstErr={step:i,err:log.errors[0],trail:[...trail]};
   if(i%100===99&&!(await responsive(p))){test('monkey','Responsive at step '+i,false,{trail});break;}}
  await closeAll(p);
  test('monkey','Seeded monkey ('+N+' actions, seed '+(SEED+1)+') raises no page errors',log.errors.length===0,{count:log.errors.length,unique:[...new Set(log.errors)].slice(0,6),firstErr});
  const rej=await ev(p,()=>window.__rejections||[]);test('monkey','...and no unhandled promise rejections',rej.length===0,[...new Set(rej)].slice(0,6));
  test('monkey','...and the app is still responsive',await responsive(p));
  const bad=await badNumbers(p);test('monkey','...and the project holds no NaN/negative times',bad.length===0,bad);
  info('monkey','Downloads/dialogs triggered',{downloads:log.downloads||0,dialogs:log.dialogs});
  await p.close();},

 // J. Soak: repeat a normal editing loop and watch heap, DOM nodes and listeners for leaks.
 async soak(browser){const {p,log}=await boot(browser);const cdp=await p.context().newCDPSession(p);await cdp.send('Performance.enable');await cdp.send('HeapProfiler.enable');
  const metrics=async()=>{await cdp.send('HeapProfiler.collectGarbage');await p.waitForTimeout(150);const m=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(x=>[x.name,x.value]));return {heapMB:+(m.JSHeapUsedSize/1e6).toFixed(1),nodes:m.Nodes,listeners:m.JSEventListeners,docs:m.Documents};};
  const ws=await workspaces(p);const cycles=QUICK?8:25;const series=[];
  for(let c=0;c<cycles;c++){for(const w of ws){await setWS(p,w);}
   await setWS(p,'animate');await ev(p,()=>document.querySelector('#play').click());await p.waitForTimeout(700);await ev(p,()=>document.querySelector('#play').click());
   await setWS(p,'pose');await ev(p,f=>DoodleDrawing.seek(f),c*3);await ev(p,()=>document.querySelector('#keys')?.click());await p.waitForTimeout(60);await ev(p,()=>document.querySelector('#undo')?.click());
   for(const id of ['tool:library','tool:projects','tool:help'])await ev(p,async id=>{try{await BunnyCommands.run(id);}catch{}},id),await closeAll(p);
   if(c===2||c===6||c===cycles-1||c%5===4)series.push({c,...await metrics()});}
  // Base after warm-up: first visits fill bounded caches (library thumbnails are SVG image documents); a leak keeps growing after that.
  const base=series.find(x=>x.c>=6)||series[0],end=series.at(-1);info('soak','Metrics after warm-up vs end',{base,end,series});
  fs.writeFileSync(path.join(OUT,'soak-series.json'),JSON.stringify(series,null,1));
  test('soak','JS heap grows < 25% over '+cycles+' editing cycles',end.heapMB<=base.heapMB*1.25+2,{base:base.heapMB,end:end.heapMB});
  test('soak','DOM node count grows < 15%',end.nodes<=base.nodes*1.15+200,{base:base.nodes,end:end.nodes});
  test('soak','Event listener count grows < 15%',end.listeners<=base.listeners*1.15+50,{base:base.listeners,end:end.listeners});
  test('soak','No errors during the soak',log.errors.length===0,log.errors.slice(0,5));await p.close();},

 // K. Playback frame-time budget on a busy shot.
 async perf(browser){const {p,log}=await boot(browser);
  await ev(p,async()=>{const pr=JSON.parse(JSON.stringify((await BunnyProject.bundle()).project));let n=0;for(const t of Object.keys(pr.keys)){pr.keys[t]=Array.from({length:40},(_,i)=>({uid:'p'+(n++),t:i*250,v:Math.sin(i+n)*0.5,ease:'auto'}));}await BunnyProject.accept({format:'BunnyStudio',version:1,project:pr});});
  await setWS(p,'draw');for(let i=0;i<6;i++){await ev(p,()=>document.querySelector('#draw-add-above')?.click());await ev(p,i=>{const l=DoodleDrawing.selected;for(let f=0;f<60;f+=2)DoodleDrawing.assistantDraw({layerId:l,frame:f,strokes:Array.from({length:8},(_,s)=>({points:Array.from({length:30},(_,k)=>[k*8+i*20,Math.sin(k/3+f/5+s)*40+s*15])}))});},i);}
  const out={};for(const w of ['animate','pose','draw']){await setWS(p,w);await ev(p,()=>{DoodleDrawing.seek(0);window.__longTasks.length=0;window.__loaf.length=0;});
   out[w]=await ev(p,async()=>{document.getElementById('play').click();const t=[];let last=performance.now();await new Promise(res=>{const f=n=>{t.push(n-last);last=n;if(t.length<180)requestAnimationFrame(f);else res();};requestAnimationFrame(f);});document.getElementById('play').click();t.shift();t.sort((a,b)=>a-b);const q=x=>+t[Math.floor(x*(t.length-1))].toFixed(1);return {median:q(.5),p95:q(.95),max:q(1),over50:t.filter(x=>x>50).length,longTasks:window.__longTasks.length,loaf:window.__loaf.length,loafMs:window.__loaf.reduce((a,b)=>a+b,0)};});}
  info('perf','Playback frame times ms (headless, software GPU)',out);fs.writeFileSync(path.join(OUT,'perf.json'),JSON.stringify(out,null,1));
  // Absolute gates need a real GPU (PERF_ABS=1 on the PC). Headless software raster is gated against a baseline run (PERF_BASE=perf.json) with a 20% margin, as Figma does.
  const ABS=process.env.PERF_ABS==='1',BASE=process.env.PERF_BASE&&fs.existsSync(process.env.PERF_BASE)?JSON.parse(fs.readFileSync(process.env.PERF_BASE,'utf8')):null,rel=(a,b)=>a<=Math.max(b*1.2,b+4);
  for(const [w,v]of Object.entries(out)){if(ABS||!BASE){test('perf',w+': median frame <= 34 ms (30 fps)',v.median<=34,v);test('perf',w+': p95 frame <= 50 ms',v.p95<=50,v);test('perf',w+': no frame over 250 ms',v.max<=250,v);}
   else{const b=BASE[w];if(!b)continue;test('perf',w+': median frame within one vsync of baseline',v.median<=b.median+17.5,{now:v.median,base:b.median});test('perf',w+': blocked time (long animation frames) within 20% of baseline',v.loafMs<=b.loafMs*1.2,{now:v.loafMs,base:b.loafMs});test('perf',w+': p95 frame within 20% of baseline',rel(v.p95,b.p95),{now:v.p95,base:b.p95});}}
  // Scrub cost: drag the playhead across the timeline.
  const scrub=await ev(p,async()=>{const t0=performance.now();for(let f=0;f<300;f+=3){DoodleDrawing.seek(f);await new Promise(r=>requestAnimationFrame(r));}return +((performance.now()-t0)/100).toFixed(1);});
  info('perf','Scrub ms per frame',scrub);if(ABS||!BASE)test('perf','Scrubbing costs < 50 ms per frame',scrub<50,scrub);else test('perf','Scrubbing within 20% of baseline',rel(scrub,BASE.__scrub??scrub),{now:scrub,base:BASE.__scrub});out.__scrub=scrub;fs.writeFileSync(path.join(OUT,'perf.json'),JSON.stringify(out,null,1));
  test('perf','No errors during performance runs',log.errors.length===0,log.errors.slice(0,5));await p.close();},

 // L. Golden frames: pixel-compare the stage at fixed frames of a canned scene (Blender/Krita style, with tolerance).
 // First run writes goldens; later runs (e.g. the UX-overhauled build) must match them, because UX work must not change rendering.
 async golden(browser){const {PNG}=require('pngjs'),pixelmatch=(m=>m.default||m)(require('pixelmatch'))/*pixelmatch 7 is ESM*/;const dir=path.resolve(arg('goldens',path.join(__dirname,'goldens')));fs.mkdirSync(dir,{recursive:true});
  const shoot=async()=>{const {p,log}=await boot(browser,{width:1600,height:900});
   await p.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
   await ev(p,async()=>{const pr=JSON.parse(JSON.stringify((await BunnyProject.bundle()).project));const ids=Object.keys(pr.keys);let n=0;ids.forEach((t,j)=>{pr.keys[t]=[0,500,1000,1500,2000].map((ms,i)=>({uid:'g'+(n++),t:ms,v:((i*7+j*3)%5-2)/4,ease:'auto'}));});pr.cues=[{uid:'c1',text:'Golden frame caption test',start:0,end:2000}];await BunnyProject.accept({format:'BunnyStudio',version:1,project:pr});});
   await setWS(p,'animate');const shots={};
   for(const f of [0,8,15,23,30,45,59]){await ev(p,async f=>{DoodleDrawing.seek(f);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));},f);await p.waitForTimeout(120);
    const box=await p.locator('#stage').boundingBox();shots[f]=await p.screenshot({clip:box});}
   const errs=log.errors;await p.close();return {shots,errs};};
  const cmp=(a,b)=>{const A=PNG.sync.read(a),B=PNG.sync.read(b);if(A.width!==B.width||A.height!==B.height)return {size:[A.width,A.height,B.width,B.height],ratio:1};const d=new PNG({width:A.width,height:A.height});const n=pixelmatch(A.data,B.data,d.data,A.width,A.height,{threshold:0.1});return {n,ratio:n/(A.width*A.height),diff:PNG.sync.write(d)};};
  const run1=await shoot(),run2=await shoot();
  const unstable=Object.keys(run1.shots).filter(f=>cmp(run1.shots[f],run2.shots[f]).ratio>0.001);
  test('golden','Stage renders are pixel-stable between two launches',unstable.length===0,{unstable});
  const have=fs.existsSync(path.join(dir,'frame-0.png'));
  if(!have||process.argv.includes('--update-goldens')){for(const [f,b]of Object.entries(run1.shots))fs.writeFileSync(path.join(dir,'frame-'+f+'.png'),b);info('golden','Wrote goldens',{dir,frames:Object.keys(run1.shots)});}
  else{const bad=[];for(const [f,b]of Object.entries(run1.shots)){const g=path.join(dir,'frame-'+f+'.png');if(!fs.existsSync(g)){bad.push({f,missing:true});continue;}const r=cmp(fs.readFileSync(g),b);if(r.ratio>0.01){bad.push({f,ratio:+r.ratio.toFixed(4)});if(r.diff)fs.writeFileSync(path.join(OUT,'golden-diff-'+f+'.png'),r.diff),fs.writeFileSync(path.join(OUT,'golden-actual-'+f+'.png'),b);}}
   test('golden','Every frame matches its golden within 1% of pixels',bad.length===0,bad);}
  test('golden','No errors while rendering goldens',!run1.errs.length&&!run2.errs.length,[...run1.errs,...run2.errs].slice(0,5));},

 // M. Crash injection: SIGKILL the browser during edits and check the reopened project is valid and recent.
 async crash(browser){const os=require('os');const fails=[];const rounds=QUICK?2:4;
  for(let round=0;round<rounds;round++){const dirp=fs.mkdtempSync(path.join(os.tmpdir(),'ds-crash-'));
   const open=async()=>{const ctx=await chromium.launchPersistentContext(dirp,{...(process.env.PW_CHANNEL?{channel:process.env.PW_CHANNEL}:{}),viewport:{width:1600,height:900}});const p=ctx.pages()[0]||await ctx.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.BunnyStudio&&window.BunnyProject,null,{timeout:120000});await p.waitForTimeout(1500);await ev(p,()=>document.querySelector('#studio-home')?.close());return {ctx,p,errors};};
   let {ctx,p}=await open();await setWS(p,'pose');
   const count=()=>ev(p,async()=>{const pr=(await BunnyProject.bundle()).project;return Object.values(pr.keys).reduce((n,a)=>n+(a?.length||0),0);});
   for(let i=0;i<5;i++){await ev(p,f=>DoodleDrawing.seek(f),i*10);await ev(p,()=>document.querySelector('#keys').click());await p.waitForTimeout(50);}
   await p.waitForTimeout(2500);const settled=await count();
   // Keep editing and kill mid-burst at a random moment.
   const burst=(async()=>{for(let i=0;i<40;i++){try{await ev(p,f=>DoodleDrawing.seek(f),60+i*3);await ev(p,()=>document.querySelector('#keys').click());}catch{return;}}})();
   await new Promise(r=>setTimeout(r,200+Math.floor(Math.random()*1500)));
   const pid=ctx.browser()?.process?.()?.pid;/*crash-cross-platform*/const cp=require('child_process');if(process.platform==='win32'){if(pid)try{cp.execSync('taskkill /F /T /PID '+pid,{stdio:'ignore'});}catch{}try{cp.execSync('powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like \'*'+dirp.replace(/'/g,"''")+'*\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"',{stdio:'ignore'});}catch{}}else{const procs=cp.execSync('pgrep -f "'+dirp+'" || true').toString().trim().split('\n').filter(Boolean);for(const id of procs)try{process.kill(+id,'SIGKILL');}catch{}}
   await burst.catch(()=>{});await ctx.close().catch(()=>{});
   ({ctx,p}=await open().catch(e=>({ctx:null,p:null,err:e})));if(!p){fails.push({round,reopen:'failed'});continue;}
   const errors=[];p.on('pageerror',e=>errors.push(e.message));
   const after=await count();const valid=await ev(p,async()=>{try{BunnyProject.validate((await BunnyProject.bundle()).project);return '';}catch(e){return e.message}});
   const bad=await badNumbers(p);
   if(valid||bad.length||after<settled)fails.push({round,settled,after,valid,bad:bad.slice(0,3),errors});
   info('crash','Round '+round+' keys settled/after-reopen',{settled,after});
   await ctx.close();fs.rmSync(dirp,{recursive:true,force:true});}
  test('crash','After SIGKILL mid-edit, the reopened project is valid and keeps every edit saved before the burst ('+rounds+' rounds)',fails.length===0,fails);},
};

(async()=>{server=http.createServer((q,r)=>{r.setHeader('Content-Type','text/html');r.end(fs.readFileSync(HTML))});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({...(process.env.PW_CHANNEL?{channel:process.env.PW_CHANNEL}:{}),args:['--autoplay-policy=no-user-gesture-required','--enable-precise-memory-info','--js-flags=--expose-gc']});
 for(const [name,fn]of Object.entries(SUITES)){if(ONLY&&!ONLY.includes(name))continue;const t0=Date.now();console.log('\n=== '+name);
  try{await Promise.race([fn(browser),new Promise((_,j)=>setTimeout(()=>j(Error('suite timeout 15 min')),900000))]);}catch(e){test(name,'Suite crashed: '+e.message.split('\n')[0],false,e.stack?.split('\n').slice(0,4));}
  info(name,'Suite seconds',Math.round((Date.now()-t0)/1000));}
 const pass=results.filter(r=>r.ok&&!r.info).length,fail=results.filter(r=>!r.ok).length;console.log('\nSUMMARY '+pass+' pass, '+fail+' fail');
 fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify({html:HTML,seed:SEED,when:new Date().toISOString(),results},null,1));
 process.exitCode=fail?1:0;await Promise.race([browser.close(),new Promise(r=>setTimeout(r,5000))]);server.close();setTimeout(()=>process.exit(process.exitCode),500);})();
