// Isolated native Windows publisher + separate phone UI context. Radio tested separately.
const fs=require('fs'),assert=require('assert/strict');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
if(!process.env.QA_ANDROID){/*the phone side of live sync runs through the Android bridge (window.BunnyAndroid); the Android app is retired*/console.log(JSON.stringify({skipped:true,reason:'Android client retired'}));process.exit(0);}
(async()=>{
 const origin=process.argv[2];assert(origin&&!origin.endsWith(':54183'));
 const browser=await chromium.launch({channel:'msedge',headless:true});const pc=await browser.newPage({viewport:{width:1600,height:1000}}),phone=await browser.newPage({viewport:{width:393,height:850},isMobile:true,hasTouch:true}),checks=[],errors=[];let network=0,assets=0,forceWifiFailure=false;
 const test=(name,ok,detail)=>{checks.push({name,passed:!!ok,detail});assert(ok,name+' '+JSON.stringify(detail));};
 pc.on('pageerror',e=>errors.push('pc: '+e.message));phone.on('pageerror',e=>errors.push('phone: '+e.message));
 await phone.exposeBinding('testNative',async(source,{kind,id,address,text})=>{
  network++;let type,value;try{if(kind==='wifi'&&forceWifiFailure)throw Error('Isolated Wi-Fi loss');const message=JSON.parse(text);if(message.action==='live-asset')assets++;const reply=await fetch(address,{method:'POST',headers:{'Content-Type':'application/json'},body:text});value=await reply.text();type=kind==='wifi'?'wifi-sync':'bluetooth-sync';}catch(e){type=kind==='wifi'?'wifi-error':'bluetooth-error';value=e.message;}
  await phone.evaluate(({id,type,value})=>window.dispatchEvent(new CustomEvent('bunny-native',{detail:{id,type,value}})),{id,type,value});
 });
 await phone.addInitScript(()=>{window.BunnyAndroid={automation:()=>JSON.stringify({enabled:false}),wifiSync:(id,address,text)=>window.testNative({kind:'wifi',id,address,text}),bluetoothSync:(id,peer,text)=>window.testNative({kind:'bluetooth',id,address:window.__testAddress+'/sync',text})};});
 try{
  await pc.goto(origin);await phone.goto(origin);await Promise.all([pc,phone].map(p=>p.waitForFunction(()=>window.DoodleLiveSync)));
  await pc.evaluate(async()=>{const project={projectID:'live-pc-fixture',keys:{mouth:[{uid:'manual-original',t:0,v:7,manual:true,corrected:true}]},clips:[],cues:[]};await BunnyProject.accept({format:'BunnyStudio',version:2,project});BunnyWorkflow.takeControl();});
  await phone.evaluate(async()=>{await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:'phone-original',keys:{headYaw:[{uid:'keep-phone',t:0,v:12}]},clips:[],cues:[]}});BunnyWorkflow.takeControl();});
  const prior=await phone.evaluate(async()=>BunnyProject.bundle());
  await pc.evaluate(()=>DoodleLiveSync.startShare());
  const info=await(await fetch(origin+'/api/info')).json(),address='http://127.0.0.1:'+info.port;
  await phone.evaluate(({address,pin})=>{window.__testAddress=address;document.getElementById('sync-address').value=address;document.getElementById('sync-pin').value=pin;document.getElementById('sync-bluetooth').append(new Option('Mock paired PC','fixture'));document.getElementById('sync-bluetooth').value='fixture';},{address,pin:info.pin});
  await phone.evaluate(()=>DoodleLiveSync.startFollow());await phone.waitForFunction(async()=>(await BunnyProject.bundle()).project.projectID==='live-pc-fixture');
  test('Phone receives the actual PC project',await phone.evaluate(()=>DoodleLiveSync.following&&DoodleLiveSync.revision>0));
  test('Follower cannot take editing control',await phone.evaluate(()=>{try{BunnyWorkflow.takeControl();return false;}catch{return !BunnyWorkflow.canEdit();}}));
  const before=await pc.evaluate(async()=>BunnyProject.bundle());
  await pc.evaluate(()=>BunnyWorkflow.transaction('fixture-key',()=>{const keys=BunnyProject;DoodleScreenplay.save({text:'INT. OFFICE - DAY\n\nBUNNY\n/happy\nHi!'},'live-pc-fixture');}));
  // Apply via real bounded editor automation path, never mutate a rig file.
  const added=await pc.evaluate(async()=>{const d=DoodleScreenplay.submit({shots:[{name:'Wave test',duration:1500,keys:{headYaw:[{t:0,v:0},{t:500,v:20}],expression:[{t:0,v:1}],gaze:[{t:0,v:2}],mouth:[{t:0,v:7},{t:600,v:3}]}}]},'live-pc-fixture');return DoodleScreenplay.apply(d.draftId,'live-pc-fixture');});
  await phone.waitForFunction(async()=>(await BunnyProject.bundle()).project.shots.length===2);
  test('New script animation shots arrive live across contexts',true);
  const synced=await phone.evaluate(async()=>BunnyProject.bundle());test('Corrected original mouth key survives live animation',synced.project.shots[0].scene.keys.mouth.some(k=>k.uid==='manual-original'&&k.corrected&&k.v===7));
  await pc.evaluate(async id=>BunnyWorkflow.selectShot(id),added.shotIds[0]);await phone.waitForFunction(async id=>(await BunnyProject.bundle()).project.activeShot===id,added.shotIds[0]);
  await pc.evaluate(()=>DoodleScreenplay.request('seek_preview',{projectId:'live-pc-fixture',time:500}));await phone.waitForFunction(()=>DoodleLiveSync.lastEditor?.playhead===500);
  test('Active shot and playhead follow the PC',true);
  await pc.evaluate(()=>DoodleLiveSync.stopShare());await phone.waitForFunction(()=>document.getElementById('live-sync-state').textContent.includes('offline'));
  test('Disconnected publisher keeps the received project',await phone.evaluate(async()=>DoodleLiveSync.following&&(await BunnyProject.bundle()).project.projectID==='live-pc-fixture'));
  await pc.evaluate(()=>DoodleLiveSync.startShare());await phone.waitForFunction(()=>document.getElementById('live-sync-state').textContent.includes('Following PC live'));
  test('Saved grant reconnects after sharing restarts',true);
  forceWifiFailure=true;await phone.waitForFunction(()=>document.getElementById('live-sync-state').textContent.includes('Bluetooth'),{timeout:10000});test('Wi-Fi failure enters the existing Bluetooth transport',true);
  const count=network;await phone.waitForTimeout(2200);test('Fallback polls without retrying failed Wi-Fi each cycle',network-count<=4,network-count);forceWifiFailure=false;
  const stop=await pc.evaluate(async()=>fetch('/api/live/revoke',{method:'POST',headers:{'Content-Type':'application/json','X-Doodle-Editor':'1'},body:'{}'}).then(r=>r.json()));await phone.waitForFunction(()=>!DoodleLiveSync.following);test('PC revocation stops follower',!!stop.revoked);
  await phone.evaluate(()=>DoodleLiveSync.restore());const restored=await phone.evaluate(async()=>BunnyProject.bundle());const normalize=v=>JSON.stringify(v,(k,x)=>k==='updatedAt'?undefined:x);
  test('Previous phone project restores exactly',normalize(prior.project)===normalize(restored.project));
  test('No audio requests for projects without audio',assets===0);
  test('No JavaScript exceptions',errors.length===0,errors);
 }finally{
  fs.writeFileSync('qa/live-workflow-20261025/live-browser-checks.json',JSON.stringify({checks,errors,transport:'Real native Windows HTTP; phone native transport mocked. Not a physical Wi-Fi/Bluetooth acceptance.'},null,2));
  await pc.screenshot({path:'qa/live-workflow-20261025/pc-live-test.png'});await phone.screenshot({path:'qa/live-workflow-20261025/phone-live-test.png'});await browser.close();console.log(JSON.stringify({passed:checks.filter(c=>c.passed).length,checks:checks.length,errors}));
 }
})().catch(e=>{console.error(e);process.exitCode=1});
