// Bunny Pet for Windows: a transparent desktop pet built from Bunny's rig frames. He stays above every app,
// lives a daily routine, and opens a radial menu (notes, his board, lunch, tea, meetings, focus, water) on double-click.
const {app,BrowserWindow,Tray,Menu,ipcMain,screen,powerMonitor,Notification,nativeImage,net,dialog}=require('electron');
const path=require('path'),fs=require('fs'),crypto=require('crypto'),{spawn}=require('child_process');
// Self-update: a manifest of file hashes at UPDATE_BASE; only changed files are fetched, then Bunny restarts.
const UPDATE_BASE=(()=>{try{return fs.readFileSync(path.join(__dirname,'update-url.txt'),'utf8').trim();}catch{return '';}})();

if(!app.requestSingleInstanceLock()){app.quit();}
// Windows can decide a transparent always-on-top window is "hidden" when other windows minimise and stop painting it.
// These switches keep Bunny painting and animating no matter what the windows around him do.
app.commandLine.appendSwitch('disable-features','CalculateNativeWinOcclusion');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.setAppUserModelId('com.deepindoodles.bunnypet');

const DEFAULTS={bw:150,onTop:true,water:true,waterMin:60,waterGoal:8,stretch:true,stretchMin:120,eyes:false,eyesMin:20,routine:true,chatty:true,
  sleepAway:true,nightSleep:true,startup:false,toasts:true,breakMin:5,custom:[],notes:[],stayPut:false,cursor:'off',windows:true,
  home:'auto',ideas:[],week:{},snackBest:0,renders:true,renderDirs:[],
  banner:{text:'Do not disturb. Unless snacks.',size:1,mode:'off',every:30,from:'13:30',to:'14:30'},waterLog:{day:'',count:0},
  schedule:{wake:'07:00',coffee:'08:30',office:'09:30',lunch:'13:30',tea:'15:30',pack:'18:30',evening:'19:15',bed:'23:00'}};
const file=()=>path.join(app.getPath('userData'),'settings.json');
let S={...DEFAULTS};
function load(){try{const f=JSON.parse(fs.readFileSync(file(),'utf8'));S={...DEFAULTS,...f,banner:{...DEFAULTS.banner,...(f.banner||{})},schedule:{...DEFAULTS.schedule,...(f.schedule||{})}};
  if(!f.bw&&f.size)S.bw={small:110,medium:150,large:200}[f.size]||150;}catch{S={...DEFAULTS};}}
function save(){try{fs.mkdirSync(path.dirname(file()),{recursive:true});fs.writeFileSync(file(),JSON.stringify(S,null,1));}catch{}}

let pet,tray,settingsWin,dragging=null,away=false,focus=null,meeting=null,timers={};
const icon=()=>nativeImage.createFromPath(path.join(__dirname,'icon.png'));
const MIN_BW=90,MAX_BW=360;
/** Bunny's canvas sits at the bottom centre; the space above holds his bubble, radial menu and panels. */
function dims(){const bw=Math.max(MIN_BW,Math.min(MAX_BW,Math.round(S.bw||150))),bh=Math.round(bw*497/360);
  return {bw,bh,w:Math.max(580,Math.round(bw*2.6)),h:bh+380};}

function createPet(){
  const d=dims(),wa=screen.getPrimaryDisplay().workArea;
  pet=new BrowserWindow({width:d.w,height:d.h,x:Math.round(wa.x+wa.width*0.7-d.w/2),y:wa.y+wa.height-d.h,transparent:true,frame:false,resizable:false,
    alwaysOnTop:true,skipTaskbar:true,hasShadow:false,focusable:false,fullscreenable:false,maximizable:false,minimizable:false,backgroundColor:'#00000000',
    webPreferences:{preload:path.join(__dirname,'preload.js'),backgroundThrottling:false}});
  applyOnTop();pet.setVisibleOnAllWorkspaces(true,{visibleOnFullScreen:true});
  pet.setIgnoreMouseEvents(true,{forward:true});
  pet.loadFile(path.join(__dirname,'pet.html'));
  pet.on('closed',()=>{pet=null;});
}
/** "screen-saver" is the highest level Windows allows, so he stays above full-screen apps, the taskbar and other always-on-top windows. */
function applyOnTop(){
  if(!pet)return;clearInterval(timers.top);
  if(S.onTop){pet.setAlwaysOnTop(true,'screen-saver');
    timers.top=setInterval(()=>{if(pet&&pet.isVisible()&&!dragging){pet.setAlwaysOnTop(true,'screen-saver');pet.moveTop();}},4000);}
  else pet.setAlwaysOnTop(false);
}
function toPet(ch,data){if(pet&&!pet.isDestroyed())pet.webContents.send(ch,data);}
function area(){if(!pet)return screen.getPrimaryDisplay().workArea;const b=pet.getBounds();return screen.getDisplayNearestPoint({x:b.x+b.width/2,y:b.y+b.height-10}).workArea;}

ipcMain.handle('init',()=>({size:dims(),settings:S,area:area(),bounds:pet.getBounds()}));
let mouseOver=false,reassertAt=0;
ipcMain.on('hit',(_e,over)=>{mouseOver=!!over;if(pet&&!dragging)pet.setIgnoreMouseEvents(!over,{forward:true});});
// Typing in his notebook or on his board needs keyboard focus; the rest of the time he never steals it.
ipcMain.on('focusable',(_e,on)=>{if(!pet)return;pet.setFocusable(!!on);if(on){pet.setIgnoreMouseEvents(false);pet.focus();}else pet.blur();});
// never trust a position blindly: a bad number would crash the app, so it is logged and Bunny is put back on the ground
ipcMain.on('set-pos',(_e,p)=>{if(!pet||dragging)return;const x=Math.round(+(p&&p.x)),y=Math.round(+(p&&p.y));
  const v=screen.getAllDisplays().reduce((r,d)=>{const b=d.bounds;return {l:Math.min(r.l,b.x),t:Math.min(r.t,b.y),r:Math.max(r.r,b.x+b.width),b:Math.max(r.b,b.y+b.height)};},{l:1e9,t:1e9,r:-1e9,b:-1e9});
  const b=pet.getBounds();
  if(!Number.isFinite(x)||!Number.isFinite(y)||x<v.l-b.width||x>v.r||y<v.t-b.height*2||y>v.b){log('bad position '+JSON.stringify(p)+', rescuing');const a=area();toPet('rescue',{area:a});return;}
  try{pet.setPosition(x,y);}catch(e){log('setPosition failed '+x+','+y+': '+e.message);}
  if(playGame)sendPlay('bunny',bunnyRect());});
process.on('uncaughtException',e=>{try{log('main error: '+(e&&e.stack||e));}catch{}});
ipcMain.handle('bounds',()=>({bounds:pet.getBounds(),area:area()}));
ipcMain.on('drag-start',(_e,off)=>{if(!pet)return;dragging=off;pet.setIgnoreMouseEvents(false);
  const step=()=>{if(!dragging||!pet)return;const c=screen.getCursorScreenPoint();pet.setPosition(Math.round(c.x-dragging.x),Math.round(c.y-dragging.y));setTimeout(step,16);};step();});
ipcMain.on('drag-end',()=>{dragging=null;});
ipcMain.on('menu',()=>Menu.buildFromTemplate(menuTemplate()).popup());
ipcMain.handle('get-settings',()=>S);
ipcMain.on('set-settings',(_e,patch)=>{const resized=patch.bw!==undefined&&Math.round(patch.bw)!==Math.round(S.bw);S={...S,...patch};save();applySettings(resized);});
ipcMain.on('add-reminder',(_e,r)=>{const at=Date.now()+Math.max(1,+r.minutes||10)*60000;S.custom=[...(S.custom||[]),{text:String(r.text||'Reminder').slice(0,120),at}];save();scheduleCustom();toPet('say',{text:'Got it! I\'ll remind you.',ms:2500,action:'write'});});
ipcMain.on('focus-start',(_e,f)=>startFocus(f));
ipcMain.on('focus-stop',()=>stopFocus());
ipcMain.on('meeting',(_e,m)=>setMeeting(m));
ipcMain.on('open-settings',(_e,s)=>openSettings(s));
ipcMain.on('notify',(_e,n)=>notify(n.title,n.body));
const logFile=()=>path.join(app.getPath('userData'),'bunny-log.txt');
function log(m){try{const f=logFile();if(fs.existsSync(f)&&fs.statSync(f).size>512*1024)fs.renameSync(f,f+'.old');fs.appendFileSync(f,new Date().toISOString()+' '+m+'\n');}catch{}}
ipcMain.on('log',(_e,m)=>log(String(m).slice(0,2000)));
// watchdog: whatever happens around him, he stays shown, unminimised and on a screen
let hiddenByUser=false;
setInterval(()=>{if(!pet||pet.isDestroyed()||hiddenByUser||dragging)return;
  if(pet.isMinimized()){log('watchdog: pet was minimised, restoring');pet.restore();pet.showInactive();}
  if(!pet.isVisible()){log('watchdog: pet was hidden, showing');pet.showInactive();}
  const b=pet.getBounds(),cx=b.x+b.width/2,cy=b.y+b.height-20;
  const onAny=screen.getAllDisplays().some(d=>{const a=d.workArea;return cx>=a.x&&cx<=a.x+a.width&&cy>=a.y-40&&cy<=a.y+a.height+40;});
  if(!onAny){log('watchdog: pet off screen at '+JSON.stringify(b)+', bringing back');const a=screen.getPrimaryDisplay().workArea;pet.setPosition(Math.round(a.x+a.width*0.7-b.width/2),a.y+a.height-b.height);toPet('rescue',{area:a});}
},1500);
// When a window closes or minimises, Windows hands focus to the next window and can drop Bunny's top-most spot
// or stop painting him. Put him back on top straight away, then again once the minimise animation has finished.
function reassert(why){if(!pet||pet.isDestroyed()||hiddenByUser)return;const now=Date.now();if(now-reassertAt<3000)return;reassertAt=now;
  log(why+': visible '+pet.isVisible()+', minimised '+pet.isMinimized()+', on top '+pet.isAlwaysOnTop());
  // only touch what's actually wrong, then put click-through back exactly as it was, so he keeps answering the mouse
  const go=()=>{if(!pet||pet.isDestroyed()||hiddenByUser||dragging)return;if(pet.isMinimized())pet.restore();if(!pet.isVisible())pet.showInactive();
    if(S.onTop){pet.setAlwaysOnTop(true,'screen-saver');pet.moveTop();}pet.setIgnoreMouseEvents(!mouseOver,{forward:true});};
  go();setTimeout(go,700);}
ipcMain.on('perch-lost',()=>reassert('perch window gone'));
ipcMain.on('hide',()=>{hiddenByUser=true;if(pet)pet.hide();rebuildMenu();});
ipcMain.on('cursor-mode',()=>applyCursor());
ipcMain.on('windows-mode',()=>applyWindows());

// ---- what's on screen: your open windows (for grabbing and perching) and the cursor (for watching and following) ----
let winIds=new Set(),winProc=null,winLast='',winFails=0,winLogged=0,ctxLast='';
const cmdFile=()=>path.join(app.getPath('temp'),'bunny-cmd-'+process.pid+'.txt');
const toDip=([id,l,t,r,b])=>{const d=screen.screenToDipRect(null,{x:l,y:t,width:r-l,height:b-t});return [id,d.x,d.y,d.x+d.width,d.y+d.height];};
// The watcher always runs on Windows: window climbing can be switched off, but he still notices what you're working in.
function applyWindows(){
  if(process.platform!=='win32'){toPet('windows',[]);return;}
  if(winProc){winLast='';if(S.windows===false)toPet('windows',[]);return;}
  try{winProc=spawn('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'windows.ps1'),String(process.pid),cmdFile()],{windowsHide:true});}catch{winProc=null;return;}
  let buf='';winProc.stdout.setEncoding('utf8');
  winProc.stdout.on('data',d=>{buf+=d;let i;while((i=buf.indexOf('\n'))>=0){const line=buf.slice(0,i).trim();buf=buf.slice(i+1);if(!line||line===winLast)continue;winLast=line;
    try{const o=JSON.parse(line),list=Array.isArray(o)?o.map(toDip):(o.w||[]).map(toDip);
      const ids=new Set(list.map(w=>w[0])),gone=[...winIds].some(id=>!ids.has(id));winIds=ids;toPet('windows',S.windows===false?[]:list);winFails=0;if(gone&&pet&&!pet.isDestroyed()&&(!pet.isVisible()||pet.isMinimized()))reassert('a window closed or minimised');
      if(!Array.isArray(o)){const c={title:String(o.fg&&o.fg.t||'').slice(0,200),proc:String(o.fg&&o.fg.p||'').slice(0,60),pip:o.pip?toDip(o.pip):null},k=JSON.stringify(c);if(k!==ctxLast){ctxLast=k;toPet('context',c);}}
      if(++winLogged<60)log('windows '+JSON.stringify(list).slice(0,400));}catch(e){log('windows parse: '+e.message);}}});
  winProc.stderr.on('data',d=>log('windows.ps1: '+String(d).slice(0,300)));
  winProc.on('exit',()=>{winProc=null;if(++winFails<5)setTimeout(applyWindows,3000);});
}
// carrying a picture-in-picture video: Bunny asks for it to be moved next to his hand (positions in DIP, Windows wants pixels)
ipcMain.on('move-win',(_e,m)=>{if(process.platform!=='win32'||!m||!Number.isFinite(+m.x)||!Number.isFinite(+m.y))return;
  const p=screen.dipToScreenPoint({x:Math.round(+m.x),y:Math.round(+m.y)});
  try{fs.appendFileSync(cmdFile(),`move ${String(m.id).replace(/\D/g,'')} ${Math.round(p.x)} ${Math.round(p.y)}\n`);}catch(e){log('move-win: '+e.message);}
  if(pet&&S.onTop){pet.setAlwaysOnTop(true,'screen-saver');pet.moveTop();}});
function applyCursor(){
  clearInterval(timers.cursor);const snack=playGame==='snack';if(!snack&&(!S.cursor||S.cursor==='off'))return;let last='';
  timers.cursor=setInterval(()=>{if(!pet||!pet.isVisible())return;const c=screen.getCursorScreenPoint(),k=c.x+','+c.y;if(k===last)return;last=k;toPet('cursor',c);},snack?30:S.cursor==='follow'?40:80);
}

// ---- play: a see-through layer over the screen for his ball and the falling snacks, open only while you play ----
let playWin=null,playGame=null;
function bunnyRect(){if(!pet)return null;const b=pet.getBounds(),d=dims();return {x:b.x,y:b.y,w:b.width,h:b.height,bw:d.bw,bh:d.bh};}
function sendPlay(ch,d){if(playWin&&!playWin.isDestroyed())playWin.webContents.send(ch,d);}
function startPlay(game){
  if(!pet||!['fetch','snack'].includes(game))return;playGame=game;const wa=area(),start=()=>sendPlay('start',{game,area:wa,bunny:bunnyRect()});
  if(playWin&&!playWin.isDestroyed()){playWin.setBounds(wa);start();}
  else{playWin=new BrowserWindow({x:wa.x,y:wa.y,width:wa.width,height:wa.height,show:false,transparent:true,frame:false,resizable:false,movable:false,
      alwaysOnTop:true,skipTaskbar:true,hasShadow:false,focusable:false,fullscreenable:false,maximizable:false,minimizable:false,backgroundColor:'#00000000',
      webPreferences:{preload:path.join(__dirname,'preload.js'),backgroundThrottling:false}});
    playWin.setIgnoreMouseEvents(true,{forward:true});playWin.loadFile(path.join(__dirname,'play.html'));
    playWin.once('ready-to-show',()=>{if(!playWin)return;playWin.setAlwaysOnTop(true,'screen-saver');playWin.showInactive();if(pet){pet.setAlwaysOnTop(true,'screen-saver');pet.moveTop();}start();});
    playWin.on('closed',()=>{playWin=null;if(playGame){playGame=null;toPet('play-ev',{type:'closed'});}applyCursor();});}
  applyCursor();log('play '+game);}
function stopPlay(){playGame=null;if(playWin&&!playWin.isDestroyed())playWin.close();applyCursor();}
ipcMain.on('play-start',(_e,g)=>startPlay(g&&g.game));
ipcMain.on('play-stop',()=>stopPlay());
ipcMain.on('play-cmd',(_e,c)=>sendPlay('cmd',c));
ipcMain.on('play-ev',(_e,e)=>toPet('play-ev',e));
ipcMain.on('play-hit',(_e,over)=>{if(playWin&&!playWin.isDestroyed())playWin.setIgnoreMouseEvents(!over,{forward:true});});

// ---- render celebrations: a new video or image saved in your render folders gets a dance and confetti ----
const MEDIA=/\.(mp4|mov|webm|mkv|gif|png|jpe?g)$/i;let renderWatchers=[];const renderSeen=new Map();
function renderDirs(){const d=S.renderDirs&&S.renderDirs.length?S.renderDirs:[path.join(app.getPath('documents'),'DeepInDoodles')];
  return d.filter(x=>{try{return fs.statSync(x).isDirectory();}catch{return false;}});}
function applyRenders(){for(const w of renderWatchers)try{w.close();}catch{}renderWatchers=[];if(S.renders===false)return;
  for(const dir of renderDirs()){try{const w=fs.watch(dir,(_ev,name)=>{if(name&&MEDIA.test(String(name)))checkRender(path.join(dir,String(name)));});w.on('error',e=>log('render watch: '+e.message));renderWatchers.push(w);}
    catch(e){log('render watch '+dir+': '+e.message);}}}
// a render counts once its size has stopped changing; an old file copied or touched (not freshly written) doesn't count
function checkRender(f,lastSize){const seen=renderSeen.get(f);if(seen&&seen.done)return;if(seen)clearTimeout(seen.t);
  const t=setTimeout(()=>{let st;try{st=fs.statSync(f);}catch{renderSeen.delete(f);return;}
    if(lastSize===undefined&&Date.now()-st.mtimeMs>120000){renderSeen.delete(f);return;}
    if(st.size>0&&st.size===lastSize){renderSeen.set(f,{done:true});const name=path.basename(f);log('render done '+name);
      toPet('render',{name});notify('Render done!',`${name} is saved. Bunny is throwing confetti.`);return;}
    checkRender(f,st.size);},3000);
  renderSeen.set(f,{t});}
ipcMain.handle('pick-render-dir',async()=>{const r=await dialog.showOpenDialog({title:'Folder Bunny watches for your renders',properties:['openDirectory'],defaultPath:renderDirs()[0]||app.getPath('documents')});
  if(r.canceled||!r.filePaths[0])return null;S.renderDirs=[r.filePaths[0]];save();applyRenders();toPet('settings',{settings:S,size:dims()});return r.filePaths[0];});
ipcMain.handle('render-dirs',()=>renderDirs());

function notify(title,body){if(S.toasts&&Notification.isSupported())new Notification({title,body,icon:path.join(__dirname,'icon.png'),silent:false}).show();}
function remind(action,text,title){if(away)return;toPet('remind',{action,text});notify(title||'Bunny',text);}

// ---- reminders and his routine ----
function every(name,on,minutes,fn){clearInterval(timers[name]);if(on)timers[name]=setInterval(fn,Math.max(1,minutes)*60000);}
function daily(name,on,hhmm,fn,weekends){clearTimeout(timers[name]);if(!on)return;const [h,m]=String(hhmm).split(':').map(Number);const t=new Date();t.setHours(h||0,m||0,0,0);if(t<=new Date())t.setDate(t.getDate()+1);
  timers[name]=setTimeout(()=>{const day=new Date().getDay();if(weekends||(day!==0&&day!==6))fn();daily(name,on,hhmm,fn,weekends);},t-new Date());}
const pick=a=>a[Math.floor(Math.random()*a.length)];
// Home mode: on, off, or auto (weekends, and outside office hours on weekdays)
function isHome(){const h=S.home||'auto';if(h!=='auto')return h==='on';const d=new Date(),day=d.getDay(),m=d.getHours()*60+d.getMinutes();
  const tm=k=>{const [a,b]=String(S.schedule[k]).split(':').map(Number);return (a||0)*60+(b||0);};return day===0||day===6||m<tm('office')||m>=tm('pack');}
function today(){const d=new Date();return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate();}
function glasses(){if(S.waterLog.day!==today())S.waterLog={day:today(),count:0};return S.waterLog.count;}
ipcMain.handle('water-log',(_e,add)=>{glasses();if(add){S.waterLog.count=Math.min(30,S.waterLog.count+add);save();}return {count:S.waterLog.count,goal:S.waterGoal};});
function scheduleCustom(){clearTimeout(timers.custom);const now=Date.now();const due=(S.custom||[]).filter(r=>r.at<=now);if(due.length){for(const r of due)remind('wave',r.text,'Reminder');S.custom=S.custom.filter(r=>r.at>now);save();}
  const next=(S.custom||[]).reduce((m,r)=>Math.min(m,r.at),Infinity);if(next<Infinity)timers.custom=setTimeout(scheduleCustom,Math.min(next-now+50,2**31-1));}
function applySettings(resized){
  every('water',S.water,S.waterMin,()=>{const n=glasses();remind('drink',pick(['Water break! I\'m having some too.','Sip time. Grab your glass!','Have you had water lately?'])+` (${n} of ${S.waterGoal} today)`,'Drink some water');});
  every('stretch',S.stretch,S.stretchMin,()=>remind('yawn',pick(['Two hours in. Stand up and stretch with me!','Shoulders down, stretch it out.','Quick stretch? Your back will thank you.']),'Stretch break'));
  every('eyes',S.eyes,S.eyesMin,()=>remind('look',"Look at something far away for 20 seconds.",'Rest your eyes'));
  daily('lunch',S.routine,S.schedule.lunch,()=>{if(!away){toPet('routine','lunch');notify('Lunch','Lunch time! Bunny is already dancing.');}});
  daily('tea',S.routine,S.schedule.tea,()=>{if(away)return;if(isHome()){toPet('routine','snack');notify('Snack time','Bunny is having a snack. Join him?');}
    else{toPet('routine','tea');notify('Tea time','Chai break? Bunny is having one.');}},true);
  daily('pack',S.routine,S.schedule.pack,()=>{if(away||isHome())return;toPet('routine','pack');const open=(S.notes||[]).filter(n=>!n.done);
    notify('Wrapping up',open.length?`Still open in Bunny's notebook:\n• ${open.map(n=>n.text).join('\n• ')}`:'Notebook is clear. Good work today!');});
  const bed=(()=>{const [h,m]=String(S.schedule.bed).split(':').map(Number);const t=((h||0)*60+(m||0)-30+1440)%1440;return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');})();
  daily('winddown',S.routine&&S.home!=='off',bed,()=>{if(away||!isHome())return;toPet('routine','winddown');notify('Wind down','Half an hour to bed. Bunny is making tea.');},true);
  scheduleCustom();applyOnTop();applyWindows();applyCursor();applyRenders();
  app.setLoginItemSettings({openAtLogin:!!S.startup});
  if(resized&&pet){const d=dims(),b=pet.getBounds(),wa=area();const cx=b.x+b.width/2,bottom=b.y+b.height;
    pet.setBounds({x:Math.round(cx-d.w/2),y:Math.min(bottom,wa.y+wa.height)-d.h,width:d.w,height:d.h});}
  toPet('settings',{settings:S,size:dims()});
  rebuildMenu();
}

// ---- focus timer and Pomodoro (4 x 25 min, 5 min breaks, a long 15 min break after the fourth) ----
function startFocus(f){
  stopFocus(true);const pomo=!!(f&&f.pomo);const min=pomo?25:Math.max(1,+(f&&f.min)||25);
  focus={pomo,round:1,min};phase('focus');
}
function phase(kind){
  clearTimeout(timers.focus);if(!focus)return;
  const len=kind==='focus'?focus.min:kind==='long'?15:S.breakMin;const end=Date.now()+len*60000;
  focus.mode=kind;focus.end=end;
  const label=focus.pomo?(kind==='focus'?`Pomodoro ${focus.round}/4`:kind==='long'?'Long break':'Break'):(kind==='focus'?'Focus':'Break');
  toPet('focus',{mode:kind==='focus'?'focus':'break',end,label});
  if(kind==='focus')notify(label,`${len} minutes. I'll read quietly.`);
  timers.focus=setTimeout(()=>{
    if(kind==='focus'){const long=focus.pomo&&focus.round>=4;remind('yawn',long?'Four rounds done! Take a proper 15 minute break.':'Time\'s up! Stand up, stretch, look away.','Break time');phase(long?'long':'break');}
    else if(focus.pomo&&kind==='break'){focus.round++;remind('wave',`Break over. Round ${focus.round} of 4?`,'Back to it');phase('focus');}
    else{focus=null;toPet('focus',{mode:'off'});remind('wave','Break over. Ready for another round?','Back to it');rebuildMenu();}
  },len*60000);
  rebuildMenu();
}
function stopFocus(quiet){clearTimeout(timers.focus);if(focus&&!quiet)toPet('focus',{mode:'off'});focus=null;rebuildMenu();}

// ---- meeting countdown: a wave and a nudge five minutes before, then his "In a meeting" sign ----
function setMeeting(m){
  clearTimeout(timers.meet5);clearTimeout(timers.meet0);meeting=null;
  if(!m||!m.minutes){toPet('meeting',null);rebuildMenu();return;}
  const at=Date.now()+m.minutes*60000;meeting={at};toPet('meeting',{at});
  const five=at-5*60000-Date.now();
  if(five>0)timers.meet5=setTimeout(()=>{toPet('remind',{action:'wave',text:'Meeting in 5 minutes! Grab your water.'});notify('Meeting in 5 minutes','Bunny says: grab your water and your notes.');},five);
  timers.meet0=setTimeout(()=>{meeting=null;toPet('meeting',null);toPet('sign','meeting');notify('Meeting time','Bunny is holding up your "In a meeting" sign.');rebuildMenu();},at-Date.now());
  rebuildMenu();
}

function menuTemplate(){return [
  {label:pet&&pet.isVisible()?'Hide Bunny':'Show Bunny',click:()=>{if(!pet)createPet();else if(pet.isVisible()){hiddenByUser=true;pet.hide();}else{hiddenByUser=false;pet.showInactive();}rebuildMenu();}},
  {label:'Open his menu',click:()=>{if(pet){pet.showInactive();toPet('radial',true);}}},
  {type:'separator'},
  {label:'Home mode',submenu:[['Auto (evenings and weekends)','auto'],['On','on'],['Off','off']].map(([l,v])=>({label:l,type:'radio',checked:(S.home||'auto')===v,click:()=>{S.home=v;save();applySettings();}}))},
  {label:'Play fetch',click:()=>toPet('play','fetch')},
  {label:'Snack catch',click:()=>toPet('play','snack')},
  {type:'separator'},
  {label:'Gone for lunch',click:()=>toPet('sign','lunch')},
  {label:'Gone for tea',click:()=>toPet('sign','tea')},
  {label:'In a meeting',click:()=>toPet('sign','meeting')},
  {label:'Hold up my board',click:()=>toPet('sign','banner')},
  {type:'separator'},
  focus?{label:`Stop ${focus.pomo?'Pomodoro':'focus timer'}`,click:()=>stopFocus()}:
   {label:'Focus',submenu:[...[25,50,90].map(m=>({label:`${m} minutes`,click:()=>startFocus({min:m})})),{label:'Pomodoro (4 × 25)',click:()=>startFocus({pomo:true})}]},
  meeting?{label:'Cancel meeting countdown',click:()=>setMeeting(null)}:{label:'Meeting in…',submenu:[5,10,15,30,60].map(m=>({label:`${m} minutes`,click:()=>setMeeting({minutes:m})}))},
  {label:'Remind me…',click:()=>openSettings('remind')},
  {type:'separator'},
  {label:'Stay put',type:'checkbox',checked:!!S.stayPut,click:i=>{S.stayPut=i.checked;if(i.checked&&S.cursor==='follow')S.cursor='off';save();applySettings();}},
  {label:'Watch my cursor',type:'checkbox',checked:S.cursor==='watch',click:i=>{S.cursor=i.checked?'watch':'off';save();applySettings();}},
  {label:'Follow my cursor',type:'checkbox',checked:S.cursor==='follow',click:i=>{S.cursor=i.checked?'follow':'off';if(i.checked)S.stayPut=false;save();applySettings();}},
  {label:'Climb on windows',type:'checkbox',checked:S.windows!==false,click:i=>{S.windows=i.checked;save();applySettings();}},
  {type:'separator'},
  {label:'Stay on top of everything',type:'checkbox',checked:!!S.onTop,click:i=>{S.onTop=i.checked;save();applyOnTop();}},
  {label:'Size',submenu:[['Small',110],['Medium',150],['Large',220],['Huge',320]].map(([l,v])=>({label:l,type:'radio',checked:Math.abs(S.bw-v)<20,click:()=>{S.bw=v;save();applySettings(true);}}))},
  {label:'Settings…',click:()=>openSettings()},
  {label:'Check for updates',click:()=>checkUpdate(true)},
  {label:'Open log folder',click:()=>require('electron').shell.showItemInFolder(logFile())},
  {label:'Start with Windows',type:'checkbox',checked:!!S.startup,click:i=>{S.startup=i.checked;save();applySettings();}},
  {type:'separator'},
  {label:'Quit Bunny Pet',click:()=>app.quit()}];}
function rebuildMenu(){if(tray)tray.setContextMenu(Menu.buildFromTemplate(menuTemplate()));}
function openSettings(section){
  if(settingsWin&&!settingsWin.isDestroyed()){settingsWin.show();settingsWin.focus();settingsWin.webContents.send('section',section);return;}
  settingsWin=new BrowserWindow({width:500,height:760,title:'Bunny Pet settings',icon:icon(),backgroundColor:'#E0A64B',autoHideMenuBar:true,webPreferences:{preload:path.join(__dirname,'preload.js')}});
  settingsWin.loadFile(path.join(__dirname,'settings.html'),{hash:section||''});settingsWin.on('closed',()=>settingsWin=null);
}

app.whenReady().then(()=>{
  load();createPet();
  tray=new Tray(icon().resize({width:32,height:32}));tray.setToolTip('Bunny Pet');
  tray.on('click',()=>{if(pet){if(pet.isVisible()){hiddenByUser=true;pet.hide();}else{hiddenByUser=false;pet.showInactive();}rebuildMenu();}});
  applySettings();
  powerMonitor.on('lock-screen',()=>{away=true;toPet('away',true);});
  powerMonitor.on('unlock-screen',()=>{away=false;toPet('away',false);});
  powerMonitor.on('resume',()=>{away=false;toPet('away',false);});
  setInterval(()=>{if(!S.sleepAway)return;const idle=powerMonitor.getSystemIdleTime();
    if(!away&&idle>300){away=true;toPet('away',true);}else if(away&&idle<5){away=false;toPet('away',false);}},5000);
  screen.on('display-metrics-changed',()=>toPet('area',area()));
  setTimeout(()=>checkUpdate(false),20000);setInterval(()=>checkUpdate(false),60*60000);
});
app.on('second-instance',()=>{if(pet){hiddenByUser=false;pet.showInactive();toPet('do','wave');}});
function sha(f){try{return crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');}catch{return '';}}
// Downloads go through Chromium's network stack (net.fetch), so office proxies and firewalls that let your browser
// through let Bunny through too. Each file gets three tries before the update is put off.
async function get(url){let err;for(let i=0;i<3;i++){try{const r=await net.fetch(url,{cache:'no-store'});if(r.ok)return r;err=new Error(url+' '+r.status);}catch(e){err=e;}
  await new Promise(r=>setTimeout(r,800*(i+1)));}throw err;}
let updating=false;
async function checkUpdate(manual){
  if(updating){if(manual)toPet('say',{text:'Already updating, hang on…',ms:2500});return;}
  if(!UPDATE_BASE){if(manual)toPet('say',{text:'Updates aren\'t set up yet.',ms:2500});return;}
  try{
    updating=true;const m=await (await get(UPDATE_BASE+'manifest.json')).json();
    const mine=require('./package.json').version;if(m.version===mine){if(manual)toPet('say',{text:`I'm up to date (v${mine}).`,ms:2500});return;}
    const todo=Object.entries(m.files).filter(([f,h])=>sha(path.join(__dirname,f))!==h);
    const tmp=path.join(app.getPath('userData'),'update');fs.rmSync(tmp,{recursive:true,force:true});
    if(todo.length>20)toPet('say',{text:`Downloading v${m.version}… (${todo.length} files)`,ms:4000});log('update '+mine+' → '+m.version+': '+todo.length+' files');
    for(const [f,h] of todo){const r=await get(UPDATE_BASE+f.split('/').map(encodeURIComponent).join('/'));
      const buf=Buffer.from(await r.arrayBuffer());if(crypto.createHash('sha256').update(buf).digest('hex')!==h)throw new Error('bad hash '+f);
      const out=path.join(tmp,f);fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,buf);}
    // everything arrived intact: swap the files in, drop ones the new version no longer has, restart
    for(const [f] of todo){const dst=path.join(__dirname,f);fs.mkdirSync(path.dirname(dst),{recursive:true});fs.copyFileSync(path.join(tmp,f),dst);}
    for(const f of m.remove||[]){fs.rmSync(path.join(__dirname,f),{force:true,recursive:true});}
    fs.rmSync(tmp,{recursive:true,force:true});
    toPet('say',{text:`New tricks! Updating to v${m.version}…`,ms:2500,action:'spin'});notify('Bunny updated',`Version ${m.version}: ${m.notes||'new moves and fixes'}`);
    setTimeout(()=>{app.relaunch();app.exit(0);},2600);
  }catch(e){updating=false;log('update failed: '+(e&&(e.stack||e.message)||e));if(manual)toPet('say',{text:'Couldn\'t reach the update server ('+String(e&&e.message||e).slice(0,60)+'). I\'ll try later.',ms:5000});}
}
app.on('before-quit',()=>{if(winProc)winProc.kill();});
app.on('window-all-closed',e=>e.preventDefault&&e.preventDefault());
