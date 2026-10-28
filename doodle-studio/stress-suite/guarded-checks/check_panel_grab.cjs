// Regression for the actual six-dot grip, not an arbitrary title-bar centre.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const origin=process.argv[2]?.startsWith('http')?process.argv[2]:null,source=process.argv[3]||'index.studio.html',out=process.argv[4]||'qa/panel-grab-20261024/windows';fs.mkdirSync(out,{recursive:true});
 const server=origin?null:http.createServer((q,r)=>{r.setHeader('Content-Type','text/html');r.end(fs.readFileSync(source));});if(server)await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const b=await chromium.launch({channel:'msedge',headless:true}),c=await b.newContext({viewport:{width:1920,height:1032}}),p=await c.newPage(),checks=[],errors=[];
 const test=(name,passed,detail)=>{checks.push({name,passed:!!passed,detail});assert.ok(passed,name+' '+JSON.stringify(detail));};p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
 try{
  await p.goto(origin||'http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.BunnyDetachedPanels);
  await p.evaluate(async()=>{await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:'grip-regression',keys:{mouth:[{uid:'protected',t:0,v:7,manual:true,corrected:true}],moveX:[{uid:'body-key',t:1000,v:13}]},clips:[],cues:[]}});});
  const original=await p.evaluate(async()=>(await BunnyProject.bundle()).project);
  for(const size of [{width:1920,height:1032},{width:1280,height:720},{width:2560,height:1440},{width:1000,height:650}]){
   await p.setViewportSize(size);
   for(const layout of ['portrait-left','portrait-right','classic','canvas-top']){
    await p.evaluate(layout=>BunnyLayouts.apply(BunnyLayouts.preset(layout)),layout);await p.waitForTimeout(50);
    const result=await p.evaluate(()=>{
     const grips=[...document.querySelectorAll('[data-dock-drag]')].map(n=>{const r=n.getBoundingClientRect(),bad=[];for(const x of [5,14,28,r.width/2,r.width-8])for(const y of [4,14,24]){const h=document.elementFromPoint(r.x+x,r.y+y);if(h?.closest('[data-dock-drag]')!==n||getComputedStyle(h).cursor!=='grab')bad.push({x,y,hit:h?.className,cursor:h&&getComputedStyle(h).cursor});}return{id:n.dataset.dockDrag,bad};});
     const clipped=[];for(const e of document.querySelectorAll('.topbar button,.topbar select,#studio-transport button')){const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;const parent=e.closest('.topbar,#studio-transport'),pr=parent.getBoundingClientRect(),pane=e.closest('.dock-content').getBoundingClientRect();if(r.top<pr.top-.5||r.bottom>pr.bottom+.5||r.left<pr.left-.5||r.right>pr.right+.5||r.top<pane.top-.5||r.bottom>pane.bottom+.5)clipped.push({id:e.id,rect:r.toJSON(),parent:pr.toJSON()});}
     return{grips,clipped};
    });
    test('All three dotted grips receive the pointer with a grab cursor: '+size.width+'x'+size.height+' '+layout,result.grips.length===3&&result.grips.every(g=>!g.bad.length),result.grips);
    test('Header and transport controls fit completely: '+size.width+'x'+size.height+' '+layout,!result.clipped.length,result.clipped);
   }
  }
  await p.setViewportSize({width:1920,height:1032});
  for(const id of ['canvas','tools','timeline']){
   await p.evaluate(()=>BunnyLayouts.apply(BunnyLayouts.preset('portrait-left')));await p.waitForTimeout(50);const handle=await p.locator('[data-dock-drag='+id+']').boundingBox();
   await p.mouse.move(handle.x+14,handle.y+14);await p.mouse.down();
   test(id+' grip shows grabbing immediately on mouse down',await p.locator('[data-dock-drag='+id+']').evaluate(n=>getComputedStyle(n).cursor==='grabbing'));
   const targetID=id==='canvas'?'tools':'canvas',target=await p.locator('[data-dock-panel='+targetID+']').boundingBox(),before=await p.evaluate(()=>JSON.stringify(BunnyLayouts.current.tree));
   await p.mouse.move(target.x+target.width/2,target.y+target.height/2,{steps:10});test(id+' dotted-grip drag displays docking preview',await p.locator('#dock-drop-preview').isVisible());await p.mouse.up();
   test(id+' drag from the dots rearranges the actual panel',await p.evaluate(before=>JSON.stringify(BunnyLayouts.current.tree)!==before,before));
   test(id+' released cursor returns to grab',!await p.evaluate(()=>document.body.classList.contains('dock-grabbed'))&&await p.locator('[data-dock-drag='+id+']').evaluate(n=>getComputedStyle(n).cursor==='grab'));
  }
  await p.evaluate(()=>BunnyLayouts.apply(BunnyLayouts.preset('portrait-left')));await p.waitForTimeout(50);
  const old=await p.evaluate(()=>JSON.stringify(BunnyLayouts.current.tree)),h=await p.locator('[data-dock-drag=timeline]').boundingBox();await p.mouse.move(h.x+14,h.y+14);await p.mouse.down();await p.mouse.move(200,100,{steps:10});await p.keyboard.press('Escape');await p.mouse.up();test('Escape cancels grip drag and resets cursor',await p.evaluate(old=>JSON.stringify(BunnyLayouts.current.tree)===old&&!document.body.classList.contains('dock-grabbed'),old));
  const splitter=p.locator('.dock-split[data-axis=x]>.dock-splitter').first(),r=await splitter.boundingBox();await p.mouse.move(r.x+r.width/2,r.y+60);test('Actual divider retains the resize cursor',await splitter.evaluate(n=>getComputedStyle(n).cursor==='col-resize'));await p.mouse.down();await p.mouse.move(r.x+70,r.y+60,{steps:10});await p.mouse.up();test('Divider still resizes without stealing a title grip',await p.evaluate(old=>JSON.stringify(BunnyLayouts.current.tree)!==old,old));
  for(const id of ['canvas','tools','timeline']){
   const r=await p.locator('[data-dock-drag='+id+']').boundingBox(),popup=p.waitForEvent('popup');await p.mouse.move(r.x+14,r.y+14);await p.mouse.down();await p.mouse.move(1980,r.y+36,{steps:10});await p.mouse.up();const child=await popup;child.on('pageerror',e=>errors.push(e.message));await child.waitForLoadState('domcontentloaded');test(id+' detaches by dragging its six dots outside',await p.evaluate(id=>BunnyDetached.has(id),id));
   await p.evaluate(id=>BunnyDetached.dock({panel:id}),id);test(id+' docks back with its grip reachable',await p.locator('[data-dock-drag='+id+']').evaluate(n=>{const r=n.getBoundingClientRect();return document.elementFromPoint(r.x+14,r.y+14)?.closest('[data-dock-drag]')===n;}));
  }
  assert.deepEqual((await p.evaluate(()=>BunnyProject.bundle())).project,original);test('Layout drags preserve the complete project and corrected keys',true);test('No runtime errors',!errors.length,errors);
  await p.screenshot({path:path.join(out,'verified-grips-and-controls.png')});
 }catch(e){checks.push({name:'Suite completion',passed:false,error:e.message});await p.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw e;}
 finally{fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({source,sourceHTMLSHA256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),origin,checks,errors,passed:checks.every(c=>c.passed),testedBuild:origin?JSON.parse(fs.readFileSync('qa/candidate-native-build.json')).artifacts.exe:undefined},null,2));console.log(JSON.stringify({checks:checks.length,passed:checks.every(c=>c.passed),last:checks.at(-1)}));await b.close();server?.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

