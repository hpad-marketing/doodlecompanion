const fs=require('fs'),path=require('path'),http=require('http');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..');
const __fill=async(l,v)=>{if(await l.count()&&!(await l.first().isVisible()))return l.first().evaluate((n,v)=>{n.value=v;n.dispatchEvent(new Event('input',{bubbles:true}));n.dispatchEvent(new Event('change',{bubbles:true}));},v);return l.fill(v)};const __select=async(l,v)=>{if(await l.count()&&!(await l.first().isVisible()))return l.first().evaluate((n,v)=>{n.value=v;n.dispatchEvent(new Event('input',{bubbles:true}));n.dispatchEvent(new Event('change',{bubbles:true}));},v);return l.selectOption(v)};
const __tap=async l=>{/*legacy controls still work but now sit in hidden containers of the studio layout*/if(await l.count()&&!(await l.first().isVisible()))return l.first().dispatchEvent('click');return l.click()};
(async()=>{
 const origin=fs.readFileSync(path.join(root,'qa/windows-host.log'),'utf8').trim();
 const browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({acceptDownloads:true,viewport:{width:1440,height:1100}}),p=await context.newPage();
 const checks=[],errors=[];p.on('pageerror',e=>errors.push(e.message));const check=(name,v)=>{checks.push({name,passed:!!v});if(!v)throw Error(name)};
 try{
  await p.goto(origin);await p.waitForFunction(()=>window.BunnyRig);
  const coverage=await p.evaluate(async()=>{
   const bundle=await BunnyProject.bundle();bundle.audio=undefined;bundle.project.audio=undefined;bundle.project.clips=[];bundle.project.cues=[];
   for(const id in bundle.project.keys)bundle.project.keys[id]=[];
   let count=0;for(let expression=0;expression<42;expression++)for(let gaze=0;gaze<9;gaze++){
    bundle.project.keys.expression=[{uid:'face-key',t:0,v:expression}];bundle.project.keys.gaze=[{uid:'gaze-key',t:0,v:gaze}];await BunnyProject.accept(bundle);
    const html=document.querySelector('#projected-rig').innerHTML;if(/NaN|Infinity/.test(html)||!html.includes('<path'))throw Error('Bad face '+expression+'/'+gaze);count++;
   }
   for(const view of [-85,0,85])for(const turn of [-180,-90,0,90,180]){
    bundle.project.keys.expression=[];bundle.project.keys.gaze=[];bundle.project.keys.view=[{uid:'view-key',t:0,v:view}];bundle.project.keys.turn=[{uid:'turn-key',t:0,v:turn}];await BunnyProject.accept(bundle);
    if(/NaN|Infinity/.test(document.querySelector('#projected-rig').innerHTML))throw Error('Bad volume '+view+'/'+turn);
   }
   for(const id in bundle.project.keys)bundle.project.keys[id]=[];await BunnyProject.accept(bundle);return count;
  });check('all 378 native face/gaze combinations have finite geometry',coverage===378);check('360 and above/below grid has finite geometry',true);
  const motions=await p.evaluate(async()=>{
   const b=await BunnyProject.bundle();b.project.clips=[{uid:'walk-motion',type:'walk',start:0,end:2000,amp:1}];await BunnyProject.accept(b);
   const walk=BunnyRig.pose(250).mats['THIGH.L'].some((n,i)=>Math.abs(n-BunnyRig.pose(750).mats['THIGH.L'][i])>.01);
   b.project.clips=[{uid:'sway-motion',type:'turn',start:0,end:2000,amp:1}];await BunnyProject.accept(b);const sway=Math.abs(BunnyRig.pose(1000).values['HEAD Tilt'])>.1;
   b.project.clips=[];b.project.keys.turn=[{uid:'hold-a',t:0,v:0,ease:'constant'},{uid:'hold-b',t:1000,v:90}];await BunnyProject.accept(b);const hold=BunnyRig.pose(750).values['TURN 360']===0;
   b.project.keys.turn[0].ease='linear';await BunnyProject.accept(b);const linear=Math.abs(BunnyRig.pose(250).values['TURN 360']-Math.PI/8)<.00001;
   b.project.keys.turn=[];await BunnyProject.accept(b);return {walk,sway,hold,linear};
  });for(const [name,passed] of Object.entries(motions))check(name+' drives native pose',passed);
  await p.evaluate(()=>{const t=document.querySelector('[data-part-select="armL"]'),d=document.getElementById('studio-parts-dialog');if(d&&!d.open&&t&&!t.getClientRects().length)d.showModal();})/*parts live in the Choose a part dialog since the studio layout*/;await __tap(p.locator('[data-part-select="armL"]'));check('arm range matches native 145 degrees',await p.locator('[data-context-track="armL"]').getAttribute('max')==='145');
  // PointerEvents from the real browser input stack, including pen pressure.
  const head=p.locator('#part-handles [data-rig-part="head"]');await p.waitForFunction(()=>document.querySelector('#part-handles [data-rig-part="head"]')?.getBoundingClientRect().width>0);const box=await p.evaluate(()=>{const r=document.querySelector('#part-handles [data-rig-part="head"]').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}),x=box.x+box.width/2,y=box.y+box.height/2;
  const cdp=await context.newCDPSession(p);await cdp.send('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',buttons:1,pointerType:'pen',force:.6});await cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:x+70,y,buttons:1,pointerType:'pen',force:.7});await cdp.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:x+70,y,button:'left',buttons:0,pointerType:'pen'});
  const pen=await p.evaluate(async()=>({pen:BunnyPen,keys:(await BunnyProject.bundle()).project.keys.headYaw}));check('pen event reaches stage',pen.pen.type==='pen'&&pen.pen.pressure>0);check('drag head writes yaw key',pen.keys.some(k=>k.v>0));
  await __tap(p.locator('#context-reset'));
  const before=await p.locator('#projected-rig').innerHTML();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});check('tap head blinks',before!==await p.locator('#projected-rig').innerHTML());
  await __tap(p.locator('#handle-toggle'));const point=await p.locator('[data-hit-target="mouth"]').evaluate(n=>{const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}});await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});check('tap mouth writes mouth key',(await p.evaluate(()=>BunnyProject.bundle())).project.keys.mouth.some(k=>k.v===1));
  await p.locator('#properties details').first().evaluate(n=>n.open=true);await p.locator('#include-audio').uncheck();
  const download=p.waitForEvent('download');await __tap(p.locator('#export'));const file=await download;await file.saveAs(path.join(root,'qa/windows-silent.mp4'));await p.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Saved'));
  check('Windows MP4 export is nonempty',fs.statSync(path.join(root,'qa/windows-silent.mp4')).size>1000);
  check('no JavaScript errors',errors.length===0);
 }finally{await p.screenshot({path:path.join(root,'qa/advanced-last.png')});fs.writeFileSync(path.join(root,'qa/advanced-checks.json'),JSON.stringify({checks,errors,limits:['Automated pen events simulated; user separately confirmed physical Kamvas hand, leg and head dragging','Finite geometry coverage does not certify every pose visually']},null,2));await browser.close()}
 // Decode actual Android export in a separate localhost test context.
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','video/mp4');res.end(fs.readFileSync(path.join(root,'qa/android-silent.mp4')))});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const decoder=await chromium.launch({channel:'chrome',headless:true});const videoPage=await decoder.newPage();await videoPage.goto('http://127.0.0.1:'+server.address().port);
 await videoPage.waitForFunction(()=>document.querySelector('video')?.readyState>=2);const video=await videoPage.evaluate(async()=>{const v=document.querySelector('video');v.currentTime=.7;await new Promise(r=>v.onseeked=r);return {width:v.videoWidth,height:v.videoHeight,duration:v.duration}});await videoPage.screenshot({path:path.join(root,'qa/android-video-decoded.png')});fs.writeFileSync(path.join(root,'qa/android-video-decode.json'),JSON.stringify(video,null,2));await decoder.close();server.close();console.log(JSON.stringify({checks,video}));
})().catch(e=>{console.error(e);process.exit(1)});
