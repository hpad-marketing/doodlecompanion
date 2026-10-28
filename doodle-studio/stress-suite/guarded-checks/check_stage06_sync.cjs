// Controlled synthetic audio only. Native emulator HTTP -> isolated EXE localhost service.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const host=JSON.parse(fs.readFileSync('qa/sync-stage06-host.json','utf8').replace(/^\uFEFF/,''));
 const origin='http://127.0.0.1:'+fs.readFileSync(path.join(host.dataDir,'ui-port.txt'),'utf8').trim();
 const info=await(await fetch(origin+'/api/info')).json();
 const android=await chromium.connectOverCDP('http://127.0.0.1:9225'),phone=android.contexts()[0].pages()[0];
 const browser=await chromium.launch({channel:'chrome',headless:true}),pc=await browser.newPage();
 const checks=[],errors=[],test=(name,passed,data={})=>{checks.push({name,passed:!!passed,...data});assert.ok(passed,name+' '+JSON.stringify(data))};
 const equal=(a,b)=>assert.deepStrictEqual(a,b);let before,settings;
 phone.on('pageerror',e=>errors.push('Android '+e.message));pc.on('pageerror',e=>errors.push('Windows '+e.message));
 try{
  await pc.goto(origin);await pc.waitForFunction(()=>window.BunnyWorkflow);await phone.waitForFunction(()=>window.BunnyWorkflow);
  before=await phone.evaluate(()=>BunnyProject.bundle());
  settings=await phone.evaluate(()=>Object.fromEntries(['address','pin','bluetooth'].map(k=>[k,document.querySelector('#sync-'+k).value])));
  await phone.evaluate(({port,pin})=>{document.querySelector('#sync-address').value='http://10.0.2.2:'+port;document.querySelector('#sync-pin').value=pin;document.querySelector('#sync-bluetooth').value='';BunnyStudio.menu.close()},{port:+origin.split(':').at(-1),pin:info.pin});
  await pc.evaluate(origin=>document.querySelector('#sync-address').value=origin,origin);
  const initial=await phone.evaluate(pin=>BunnyProject.syncRequest({action:'pull',pin}),info.pin);
  test('Actual emulator Java HTTP reaches empty isolated compiled service',initial.revision===0&&initial.bundle===null);
  const sent=await phone.evaluate(async()=>{
   const n=3200,rate=16000,bytes=new ArrayBuffer(44+n*2),v=new DataView(bytes),text=(p,s)=>[...s].forEach((c,i)=>v.setUint8(p+i,c.charCodeAt(0)));
   text(0,'RIFF');v.setUint32(4,36+n*2,true);text(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,n*2,true);
   for(let i=0;i<n;i++)v.setInt16(44+i*2,Math.round(Math.sin(i/rate*880*Math.PI)*5000),true);
   const audio=await new Promise(r=>{const reader=new FileReader();reader.onload=()=>r(reader.result);reader.readAsDataURL(new Blob([bytes],{type:'audio/wav'}))});
   const id='audio-qa-sync-'+crypto.randomUUID();
   await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:'qa-sync-'+crypto.randomUUID(),title:'नमस्ते Bunny',language:'mixed',scriptText:'नमस्ते Bunny। hello!',keys:{bodyX:[{uid:'sync-body',t:0,v:9,ease:'constant',manual:true}],mouth:[{uid:'sync-closure',t:0,v:7,ease:'constant',corrected:true,manual:true,holdEnd:160},{uid:'sync-rest',t:160,v:1,ease:'constant',corrected:true,manual:true}]},clips:[],cues:[{uid:'sync-hi',start:0,end:1200,text:'नमस्ते Bunny। hello!'}],sub:{x:256,y:330},voiceSegments:[{uid:'sync-voice',assetID:id,type:'voice',start:0,sourceStart:0,duration:200}],audioGraphVersion:1,aspect:'portrait',cameraViews:{portrait:{x:2,y:-4,scale:1,rotation:0,fit:true},landscape:{x:-12,y:8,scale:1.1,rotation:3,fit:true}},markers:[{uid:'sync-pause',t:500,type:'pause',name:'Pause'}],locks:{gaze:true}},assets:{[id]:audio}});
   BunnyWorkflow.takeControl();
   BunnyProps.add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path fill="#E0A64B" stroke="#1F1F1D" d="M2 2H18V18H2Z"/></svg>',{name:'Sync prop',attachment:'scene',size:20});
   BunnyWorkflow.createShots([{name:'Reaction · दूसरा',duration:1500,scene:{keys:{headNod:[{uid:'sync-nod',t:0,v:4,ease:'constant'}]},clips:[],cues:[{uid:'sync-second',start:0,end:1200,text:'दूसरा shot'}],sub:{x:256,y:330},voiceSegments:[{uid:'sync-second-voice',assetID:id,type:'voice',start:0,sourceStart:0,duration:200}],audioGraphVersion:1,aspect:'landscape',cameraViews:{landscape:{x:12,y:5,scale:1,rotation:-2,fit:true}}}}]);
   BunnyStudio.setWorkspace('animate');return BunnyProject.bundle();
  });
  test('Expanded portable fixture includes two shots and hashed synthetic audio',sent.project.shots.length===2&&Object.keys(sent.assets).length===1&&Object.keys(sent.project.sourceHashes).length===1);
  const pushed=await phone.evaluate(({pin,bundle})=>BunnyProject.syncRequest({action:'push',pin,revision:0,bundle}),{pin:info.pin,bundle:sent});
  test('Android native bridge sends full portable bundle',pushed.saved&&pushed.revision===1);
  const received=await pc.evaluate(pin=>BunnyProject.syncRequest({action:'pull',pin}),info.pin);
  equal(received.bundle,sent);test('Windows receives exact shots, source bytes, props, camera and Unicode',true);
  const opened=await pc.evaluate(async b=>{await BunnyProject.accept(b);const plan=await BunnyAudio.prepare();return{bundle:await BunnyProject.bundle(),canEdit:BunnyWorkflow.canEdit(),decodedSources:plan.buffers.size}},received.bundle);
  test('Phone-owned project opens on Windows without implicit edit control',!opened.canEdit);
  equal(opened.bundle.assets,sent.assets);equal(opened.bundle.project.keys.mouth,sent.project.keys.mouth);equal(opened.bundle.project.props,sent.project.props);
  test('Portable open preserves exact source and protected holds/props',true);
  test('Received audio decodes through canonical graph',opened.decodedSources===1);
  test('Portable shot and workspace focus restore',opened.bundle.editor.workspace===sent.editor.workspace&&opened.bundle.project.activeShot===sent.project.activeShot);
  const changed=await pc.evaluate(async()=>{
   let blocked=false;try{BunnyWorkflow.transaction('Remote guard',()=>{})}catch{blocked=true}
   BunnyWorkflow.takeControl();const b=await BunnyProject.bundle();b.project.keys.bodyX[0].v=17;b.project.scriptText+=' PC correction';await BunnyProject.accept(b);
   return{blocked,canEdit:BunnyWorkflow.canEdit(),bundle:await BunnyProject.bundle()};
  });
  test('Windows explicitly takes editing control after remote edit rejection',changed.blocked&&changed.canEdit);
  equal(changed.bundle.project.keys.mouth,sent.project.keys.mouth);test('PC correction retains authored mouth interval metadata',true);
  const pcPush=await pc.evaluate(({pin,bundle})=>BunnyProject.syncRequest({action:'push',pin,revision:1,bundle}),{pin:info.pin,bundle:changed.bundle});
  test('Windows sends edited portable project at next revision',pcPush.saved&&pcPush.revision===2);
  const stale=await phone.evaluate(async({pin,bundle})=>{try{await BunnyProject.syncRequest({action:'push',pin,revision:1,bundle});return false}catch(e){return e.message.includes('other device')}},{pin:info.pin,bundle:sent});
  test('Stale Android send cannot overwrite newer correction',stale);
  const bad=await phone.evaluate(async pin=>{try{await BunnyProject.syncRequest({action:'pull',pin});return false}catch(e){return e.message.includes('Pairing code')}},info.pin==='000000'?'999999':'000000');
  test('Native HTTP rejects incorrect pairing code',bad);
  const returned=await phone.evaluate(async pin=>{const r=await BunnyProject.syncRequest({action:'pull',pin});await BunnyProject.accept(r.bundle);const before=await BunnyProject.bundle(),remote=!BunnyWorkflow.canEdit();BunnyWorkflow.takeControl();return{revision:r.revision,remote,before,after:await BunnyProject.bundle(),canEdit:BunnyWorkflow.canEdit()}},info.pin);
  test('Android receives PC correction with explicit remote ownership',returned.revision===2&&returned.remote&&returned.before.project.keys.bodyX[0].v===17&&returned.before.project.scriptText.endsWith('PC correction'));
  equal(returned.before.assets,sent.assets);equal(returned.before.project.keys.mouth,sent.project.keys.mouth);equal(returned.before.project.props,sent.project.props);equal(returned.before.project.sourceHashes,sent.project.sourceHashes);
  test('Complete roundtrip preserves source hash, SVG and corrected closure',true);
  test('Phone editing resumes only with explicit take-control action',returned.canEdit&&returned.after.project.editing.owner!==returned.before.project.editing.owner);
  const disk=JSON.parse(fs.readFileSync(path.join(host.dataDir,'sync-project.json'),'utf8').replace(/^\uFEFF/,''));
  equal(disk.bundle,changed.bundle);test('Compiled host persisted exact received bundle',disk.revision===2);
  const prior=await phone.evaluate(()=>BunnyProject.bundle());
  const rejected=await phone.evaluate(async pack=>{const id=Object.keys(pack.assets)[0];pack.assets[id]=pack.assets[id].slice(0,-8)+'AAAAAAAA';try{await BunnyProject.accept(pack);return false}catch(e){return /hash|checksum|integrity|match/i.test(e.message)}},JSON.parse(JSON.stringify(changed.bundle)));
  test('Corrupted source is rejected before received project replaces editor',rejected);
  const after=await phone.evaluate(()=>BunnyProject.bundle());equal(after.project.keys,prior.project.keys);equal(after.assets,prior.assets);
  test('Rejected transfer preserves authored keys and original source bytes',true);
  test('No runtime errors',!errors.length,{errors});console.log(JSON.stringify({checks:checks.length,passed:true}));
 }finally{
  if(before)await phone.evaluate(b=>{BunnyStudio.menu.close();return BunnyProject.accept(b)},before);
  if(settings)await phone.evaluate(s=>{for(const k of ['address','pin','bluetooth'])document.querySelector('#sync-'+k).value=s[k]},settings);
  fs.writeFileSync('qa/stage06-sync-checks.json',JSON.stringify({checks,errors,testedArtifacts:JSON.parse(fs.readFileSync('qa/candidate-native-build.json','utf8')).artifacts,limits:['Synthetic audio only. Emulator Java HTTP over10.0.2.2 bridge to isolated EXE localhost host; not physical Wi-Fi/Bluetooth/radio/pen/human acceptance.','Exact on-disk bundle checked; not process-death/restart stress.']},null,2));
  await browser.close();
 }
})().then(()=>process.exit(0),e=>{console.error(e);process.exit(1)});
