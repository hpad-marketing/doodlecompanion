// Self-update (adapted from the 2D app's updater; separate channel doodle-studio-3d/). A manifest on GitHub lists every file this build ships (beside the
// bundled Electron runtime) with its SHA-256. Changed files are downloaded gzip'd,
// verified, then swapped in place. A running EXE can be renamed but not overwritten,
// so replaced files are set aside and, on the next launch, become the rollback copy
// in .update/previous (one version back). Everything the updater keeps lives in one
// hidden .update folder; the install folder itself only ever holds the app's own
// files, replaced in place. Creative data lives in AppData and is never touched.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib'),{spawn}=require('node:child_process');
module.exports=({app,dialog,net,window,logDir})=>{
 const root=path.resolve(__dirname,'..','..'),work=path.join(root,'.update'),old=path.join(work,'old'),previous=path.join(work,'previous'),stateFile=path.join(work,'state.json'),legacyState=path.join(root,'update.json');
 if(!fs.existsSync(path.join(root,'Doodle Studio 3D.exe')))return null;
 const base=(()=>{try{return fs.readFileSync(path.join(root,'update-url.txt'),'utf8').trim();}catch{return 'https://raw.githubusercontent.com/hpad-marketing/doodlecompanion/main/doodle-studio-3d/';}})();
 const log=text=>{try{fs.appendFileSync(path.join(logDir,'update.log'),new Date().toISOString()+' '+text+'\n');}catch{}};
 const state=()=>{try{return JSON.parse(fs.readFileSync(stateFile,'utf8'));}catch{return {};}};
 try{fs.mkdirSync(work,{recursive:true});spawn('attrib',['+h',work],{windowsHide:true,stdio:'ignore'}).on('error',()=>{});}catch{}
 // Earlier builds kept their version beside the EXE; move it out of sight.
 try{if(fs.existsSync(legacyState)){if(!fs.existsSync(stateFile))fs.copyFileSync(legacyState,stateFile);fs.unlinkSync(legacyState);}}catch{}
 // Files the last swap set aside are no longer running. Keep them as the rollback
 // copy, replacing the one before.
 try{if(fs.existsSync(old)){fs.rmSync(previous,{recursive:true,force:true});fs.renameSync(old,previous);}}catch{try{fs.rmSync(old,{recursive:true,force:true});}catch{}}
 for(const dir of [root,__dirname])try{for(const name of fs.readdirSync(dir))if(/\.old-\d+$/.test(name))try{fs.unlinkSync(path.join(dir,name));}catch{}}catch{}
 // Update safety check (hard rule: an update must never break the MCP). A new version is
 // on probation until its MCP answers; if it doesn't, or the app fails to start twice,
 // the previous version comes back by itself and this version is skipped.
 const writeState=s=>{try{fs.mkdirSync(work,{recursive:true});fs.writeFileSync(stateFile,JSON.stringify(s,null,2));}catch{}};
 const walk=(d,rel='')=>{let out=[];try{for(const e of fs.readdirSync(path.join(d,rel),{withFileTypes:true})){const r=path.join(rel,e.name);out=out.concat(e.isDirectory()?walk(d,r):[r]);}}catch{}return out;};
 function rollback(reason){
  const s=state(),from=path.join(previous,'files');
  if(!s.probation||!fs.existsSync(from)){log('rollback not possible ('+reason+'): no previous version kept');return false;}
  let back={};try{back=JSON.parse(fs.readFileSync(path.join(previous,'version.json'),'utf8'));}catch{}
  const aside=path.join(work,'failed-'+(s.version||'unknown'));
  for(const rel of walk(from)){const dst=path.join(root,rel),bad=path.join(aside,rel);try{fs.mkdirSync(path.dirname(bad),{recursive:true});if(fs.existsSync(dst))fs.renameSync(dst,bad);fs.mkdirSync(path.dirname(dst),{recursive:true});fs.copyFileSync(path.join(from,rel),dst);}catch(e){log('rollback '+rel+': '+e.message);}}
  writeState({version:back.version||'',skip:[...new Set([...(s.skip||[]),s.version])],rolledBack:{from:s.version,reason,at:new Date().toISOString()}});
  log('rolled back '+s.version+' -> '+(back.version||'?')+': '+reason);
  return true;
 }
 {const s=state();if(s.probation){s.launches=(s.launches||0)+1;writeState(s);if(s.launches>=3&&rollback('the new version did not start properly twice')){restartNow();}}}
 function restartNow(){try{app.relaunch();}catch{}app.exit(0);}
 // main.cjs calls this once the window is up, with a probe of the app's own MCP
 async function verify(probe){
  const s=state();if(!s.probation)return 'stable';
  let ok=false,why='';for(let i=0;i<3&&!ok;i++){try{ok=await probe();}catch(e){why=e.message;}if(!ok)await new Promise(r=>setTimeout(r,2000));}
  if(ok){delete s.probation;delete s.launches;s.verified=new Date().toISOString();writeState(s);log('safety check passed for '+s.version+': MCP answers');return 'verified';}
  if(rollback('the MCP did not answer'+(why?' ('+why+')':''))){const win=window();if(win&&!win.isDestroyed())await dialog.showMessageBox(win,{type:'warning',title:'Doodle Studio 3D update',message:'The update was undone',detail:'Version '+s.version+' started without its MCP connection, so the previous version is back. Doodle Studio 3D restarts now.'});restartNow();return 'rolled back';}
  return 'failed';
 }
 const sha=file=>new Promise(done=>{const hash=crypto.createHash('sha256');fs.createReadStream(file).on('error',()=>done('')).on('data',d=>hash.update(d)).on('end',()=>done(hash.digest('hex')));});
 async function get(url){let error;for(let i=0;i<3;i++){try{const r=await net.fetch(url,{cache:'no-store'});if(r.ok)return r;error=Error(url+' '+r.status);}catch(e){error=e;}await new Promise(r=>setTimeout(r,1000*(i+1)));}throw error;}
 // One updater at a time, even with several Doodle Studio windows open. The lock names its process:
 // an app closed mid-download leaves it behind, and the next launch must not wait for it to age out.
 const lock=()=>{const file=path.join(work,'lock');fs.mkdirSync(work,{recursive:true});try{const holder=Number(fs.readFileSync(file,'utf8'))||0;let alive=false;try{if(holder)process.kill(holder,0),alive=true;}catch{}if(!alive||Date.now()-fs.statSync(file).mtimeMs>30*60000)fs.unlinkSync(file);}catch{}try{const fd=fs.openSync(file,'wx');fs.writeSync(fd,String(process.pid));fs.closeSync(fd);return ()=>{try{fs.unlinkSync(file);}catch{}};}catch{return null;}};
 let busy=false,asking=false,restartAsked=0,runtimeWarned=false;
 // Tools › Check for updates passes manual, so a check that finds nothing still answers.
 const tell=(message,detail)=>{const win=window();if(win&&!win.isDestroyed())return dialog.showMessageBox(win,{type:'info',title:'Doodle Studio 3D update',message,detail:detail||''});};
 async function check(manual=false){
  if(busy){if(manual)tell('Already checking for updates','The result shows up here in a moment.');return 'busy';}
  busy=true;const held=lock();if(!held){busy=false;if(manual)tell('Already checking for updates','Another Doodle Studio window is installing it.');return 'busy';}
  // Release once: a check still waiting on its restart question must not free a newer check's lock.
  let freed=false;const release=()=>{if(freed)return;freed=true;busy=false;held();};
  try{
   const m=await (await get(base+'manifest.json')).json();
   if((state().skip||[]).includes(m.version)){if(manual)tell('An update was held back','Version '+m.version+' broke the MCP connection on this PC and was undone. The next fixed version installs as usual.');return 'skipped';}
   if(m.version===state().version){if(manual)tell('Doodle Studio 3D is up to date','You have version '+m.version+'.');return 'current';}
   if(m.runtime){let mine='';try{mine=fs.readFileSync(path.join(root,'version'),'utf8').trim();}catch{}
    if(mine!==m.runtime){log('update '+m.version+' needs runtime '+m.runtime+', have '+mine);if(!runtimeWarned||manual){runtimeWarned=true;dialog.showMessageBox(window(),{type:'info',title:'Doodle Studio 3D update',message:'Doodle Studio 3D '+m.version+' needs a full download',detail:'This update changes the app window itself, so it can\'t install in place. Ask Claude for the full build.'});}return;}}
   const todo=[];for(const [file,info] of Object.entries(m.files))if(await sha(path.join(root,file))!==info.sha256)todo.push([file,info]);
   log('update '+(state().version||'?')+' -> '+m.version+': '+todo.length+' files');
   // Already matches (installed by hand): just record the version, no restart.
   if(!todo.length){fs.writeFileSync(stateFile,JSON.stringify({version:m.version,notes:m.notes||'',installed:new Date().toISOString()},null,2));log('already up to date '+m.version);if(manual)tell('Doodle Studio 3D is up to date','You have version '+m.version+'.');return 'current';}
   const staged=path.join(work,'files');fs.rmSync(staged,{recursive:true,force:true});
   for(const [file,info] of todo){
    const data=zlib.gunzipSync(Buffer.from(await (await get(base+info.gz)).arrayBuffer()));
    if(crypto.createHash('sha256').update(data).digest('hex')!==info.sha256)throw Error('Damaged download: '+file);
    const out=path.join(staged,file);fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,data);
   }
   // Everything arrived intact. Swap it all in, or put everything back.
   const done=[];
   // A second update before a restart keeps the first one's set-aside files (the
   // running EXE among them can't be deleted yet).
   fs.mkdirSync(old,{recursive:true});if(!fs.existsSync(path.join(old,'version.json')))fs.writeFileSync(path.join(old,'version.json'),JSON.stringify({version:state().version||'',replacedBy:m.version,at:new Date().toISOString()},null,2));
   try{for(const [file] of todo){const dst=path.join(root,file),aside=path.join(old,'files',file)+(fs.existsSync(path.join(old,'files',file))?'.'+Date.now():'');fs.mkdirSync(path.dirname(dst),{recursive:true});fs.mkdirSync(path.dirname(aside),{recursive:true});
     if(fs.existsSync(dst))fs.renameSync(dst,aside);done.push([dst,aside]);fs.renameSync(path.join(staged,file),dst);}}
   catch(error){for(const [dst,aside] of done.reverse()){try{fs.rmSync(dst,{force:true});}catch{}try{if(fs.existsSync(aside))fs.renameSync(aside,dst);}catch{}}throw error;}
   fs.rmSync(staged,{recursive:true,force:true});
   writeState({version:m.version,notes:m.notes||'',installed:new Date().toISOString(),probation:true,launches:0,skip:state().skip||[]});log('installed '+m.version+' (on probation until its MCP answers)');
   const win=window();if(!win||win.isDestroyed())return 'installed';
   // Free the updater before asking: a restart question left open must never hold up later checks.
   release();if(asking)return 'installed';asking=true;
   let choice;try{choice=await dialog.showMessageBox(win,{type:'info',title:'Doodle Studio 3D updated',message:'Doodle Studio 3D '+m.version+' is installed',detail:(m.notes?m.notes+'\n\n':'')+'Restart to start using it. Your projects stay as they are. If you choose Later, the new version opens next time you start Doodle Studio.',buttons:['Restart now','Later'],defaultId:0,cancelId:1});}finally{asking=false;}
   if(choice.response===0&&!win.isDestroyed()){restartAsked=Date.now();win.close();}
   return 'installed';
  }catch(error){log('update failed: '+(error&&(error.stack||error.message)||error));if(manual)tell('Doodle Studio couldn\'t check for updates','Check the internet connection and try again.\n\n'+(error&&error.message||error));return 'failed';}
  finally{release();}
 }
 // The window's close runs the unsaved-project prompt. Relaunch only when the
 // quit really follows a Restart click, once the native host has exited.
 app.on('will-quit',()=>{
  if(!restartAsked||Date.now()-restartAsked>120000)return;
  const exe=path.join(root,'Doodle Studio 3D.exe').replace(/'/g,"''");
  spawn('powershell.exe',['-NoProfile','-WindowStyle','Hidden','-Command',`$i=0;while((Get-Process -Id ${process.pid} -ErrorAction SilentlyContinue) -and $i -lt 60){Start-Sleep -Milliseconds 500;$i++};Start-Sleep -Milliseconds 800;Start-Process -FilePath '${exe}'`],{detached:true,stdio:'ignore',windowsHide:true}).unref();
 });
 setTimeout(check,45000);setInterval(check,60*60000);
 return {check,verify,rollback};
};
