const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {_electron}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const root=process.cwd(),qa=path.join(root,'qa/stress-20261025/regressions'),host=JSON.parse(fs.readFileSync(path.join(qa,'host.json'))),origin='http://127.0.0.1:'+fs.readFileSync(path.join(host.profile,'ui-port.txt'),'utf8').trim(),build=JSON.parse(fs.readFileSync('qa/candidate-native-build.json'));
 const app=await _electron.launch({executablePath:path.join(build.folder,'windows/desktop/Doodle Studio Window.exe'),args:['--doodle-url='+origin,'--doodle-data-dir='+host.profile],env:Object.fromEntries(Object.entries(process.env).filter(([k])=>!['ELECTRON_RUN_AS_NODE','NODE_OPTIONS'].includes(k)))}),p=await app.firstWindow(),checks=[],errors=[];let complete=false;
 const check=(name,ok)=>{checks.push({name,passed:!!ok});assert(ok,name);console.log(name)};p.on('pageerror',e=>errors.push(e.message));
 try{
  await p.waitForFunction(()=>window.DoodleHome);await p.evaluate(()=>DoodleHome.resume());
  const result=await p.evaluate(async()=>{
   await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:'cutaway-fixture',keys:{},cues:[],clips:[]}});BunnyWorkflow.takeControl();
   const A=DoodleAssistantWorkspace,S=DoodleAssistantScript,W=BunnyWorkflow,id='cutaway-fixture';
   const before=JSON.stringify(await BunnyProject.bundle());
   const common='ds.shot(ds.project().shotId,{duration:5000});ds.setKeys("x",[{t:0,v:2000}]);';
   const fail=await S.run({projectId:id,code:common,dryRun:true});
   const code=common+'ds.framing({mode:"cutaway",reason:"Native doodle cutaway: Bunny intentionally off screen",from:0,to:5000});';
   const v=await S.run({projectId:id,code,dryRun:true}),unchanged=before===JSON.stringify(await BunnyProject.bundle());
   const preview=A.preview({projectId:id,validationId:v.validationId,time:500}),applied=A.apply({projectId:id,validationId:v.validationId}),stored=W.active().assistantFraming,read=A.read({projectId:id});
   A.undo({projectId:id});const undone=!W.active().assistantFraming&&(await BunnyProject.bundle()).project.keys.x.length===0;
   const partial=await S.run({projectId:id,code:common+'ds.framing({mode:"cutaway",reason:"Only the middle is a cutaway",from:1000,to:3000});',dryRun:true});
   const text=await S.run({projectId:id,code:code+'ds.insert(["cues"],{uid:"caption-outside",start:0,end:2000,text:"Unsafe caption"});ds.set(["sub","y"],380);',dryRun:true});
   let missing='',bad='',protectedMessage='';
   try{await S.run({projectId:id,code:common+'ds.framing({mode:"cutaway"});',dryRun:true})}catch(e){missing=e.message}
   try{await S.run({projectId:id,code:common+'ds.framing({mode:"cutaway",reason:"Bad range",from:1000,to:9000});',dryRun:true})}catch(e){bad=e.message}
   await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:id,keys:{headYaw:[{uid:'manual-example',t:0,v:7,manual:true}]},cues:[],clips:[]}});W.takeControl();
   try{await S.run({projectId:id,code:code+'ds.setKeys("headYaw",[{t:0,v:20}]);',dryRun:true})}catch(e){protectedMessage=e.message}
   return{normalRejected:!fail.framing[0].ok,v,unchanged,preview:preview.previewOnly,applied:applied.undoable,stored,read:read.assistantFraming,undone,partial,text,missing,bad,protectedMessage};
  });
  fs.writeFileSync(path.join(qa,'fixture-results.json'),JSON.stringify(result,null,2));
  check('Ordinary off-screen subject remains blocked',result.normalRejected);
  check('Explicit whole-shot cutaway passes with subject-only disclosure',result.v.framing[0].ok&&result.v.framing[0].cutaway.exemptSamples>0&&result.v.framing[0].cutaway.scope.includes('text checks'));
  check('Cutaway validation/preview do not author project changes',result.unchanged&&result.preview);
  check('Apply persists readable per-shot cutaway and supports one Undo',result.applied&&result.stored.mode==='cutaway'&&result.read.mode==='cutaway'&&result.undone);
  check('Off-screen Bunny outside the declared cutaway range stays blocked',!result.partial.framing[0].ok&&result.partial.framing[0].issues.some(x=>x.kind==='subject'&&(x.time<1000||x.time>=3000)));
  check('Caption safety still blocks an otherwise valid cutaway',!result.text.framing[0].ok&&result.text.framing[0].issues.some(x=>x.kind==='caption'));
  check('Cutaway requires an explanation and in-shot range',!!result.missing&&!!result.bad);
  check('Manual keys remain protected during cutaways',result.protectedMessage.includes('Protected'));
  await app.evaluate(async({BrowserWindow,dialog})=>{dialog.showMessageBox=async(_window,options)=>{globalThis.__guideRecoveryPrompt=options;return{response:0}};const w=BrowserWindow.getAllWindows()[0],loaded=new Promise((resolve,reject)=>{w.webContents.once('did-finish-load',resolve);setTimeout(()=>reject(Error('Recovery load timeout')),20000)});w.webContents.forcefullyCrashRenderer();await loaded});
  const recovered=await app.evaluate(async({BrowserWindow})=>({message:globalThis.__guideRecoveryPrompt?.message,buttons:globalThis.__guideRecoveryPrompt?.buttons,editor:await BrowserWindow.getAllWindows()[0].webContents.executeJavaScript('!!window.DoodleAssistantWorkspace')}));
  check('Renderer failure offers explicit saved-project recovery and reloads',recovered.message==='The editor stopped responding.'&&recovered.buttons[0]==='Reopen saved project'&&recovered.editor);
  check('No application JavaScript errors',!errors.length);complete=true;
 }finally{fs.writeFileSync(path.join(qa,'checks.json'),JSON.stringify({passed:complete,checks,errors,build:build.folder,scope:'Isolated native fixtures; no user animation changed.'},null,2));await app.evaluate(({app})=>app.exit(0));}
})().catch(e=>{console.error(e);process.exitCode=1});
