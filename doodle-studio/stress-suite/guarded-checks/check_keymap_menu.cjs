// Menu bar, remappable shortcuts, Space play/pause, play-from-end with audio, and Draw holds: real key and pointer input.
const fs=require('fs'),http=require('http');let chromium;try{({chromium}=require('./qa-home-guard.cjs')(require('playwright')))}catch{({chromium}=require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))}
(async()=>{const server=http.createServer((q,r)=>{r.setHeader('Content-Type','text/html');r.end(fs.readFileSync('index.studio.html'))});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']}),p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
const test=(name,ok,detail)=>{console.log((ok?'PASS ':'FAIL ')+name+(ok?'':' '+JSON.stringify(detail)));if(!ok)process.exitCode=1;};
const ev=(fn,a)=>p.evaluate(fn,a);
await p.addInitScript(()=>{window.__src=[];const s=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(at,off,len){window.__src.push(off);return s.call(this,at,off,len)};});
try{
await p.goto('http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.DoodleKeymap&&window.DoodleDrawFrames,null,{timeout:60000});await ev(()=>{document.querySelector('#studio-home')?.close();DoodleKeymap.reset();});
const playing=()=>ev(()=>document.getElementById('play').textContent==='Pause');
const stop=()=>ev(()=>{if(document.getElementById('play').textContent==='Pause')document.getElementById('play').click()});
// Space everywhere, including right after clicking a button in a panel
for(const ws of ['script','voice','pose','draw','animate','captions','assistant']){await p.locator(`button[data-workspace="${ws}"]`).first().click();await p.keyboard.press('Home');
 await p.keyboard.press('Space');const a=await playing();await p.keyboard.press('Space');const z=await playing();test(`Space plays and pauses in ${ws}`,a&&!z,{a,z});await stop();}
await p.locator('button[data-workspace="draw"]').click();await p.locator('#draw-add-above').click();const layers=await ev(()=>DoodleDrawing._fx.layers().length);
await p.keyboard.press('Space');test('Space plays after clicking a Draw button, without pressing it again',await playing()&&await ev(()=>DoodleDrawing._fx.layers().length)===layers);await stop();
await p.locator('#play').click();await p.keyboard.press('Space');test('Space pauses when the Play button has focus',!(await playing()));await stop();
// Menu bar
test('Menu bar sits above the panels',await ev(()=>{const m=document.querySelector('#doodle-menubar').getBoundingClientRect(),c=document.querySelector('.topbar').getBoundingClientRect();return m.top===0&&m.height===30&&c.top>=30}));
await p.locator('[data-menu=view] .menu-title').click();await p.locator('[data-action="view:ws-animate"]').click();test('View › Animate workspace switches workspace',await ev(()=>BunnyStudio.workspace)==='animate');
await p.locator('[data-menu=draw] .menu-title').click();await p.locator('[data-action="draw:lasso"]').click();await p.waitForTimeout(400);test('Draw › Lasso from another workspace opens Draw with the lasso',await ev(()=>BunnyStudio.workspace==='draw'&&DoodleDrawing._fx.tool==='lasso'));
await p.locator('[data-menu=playback] .menu-title').click();await p.locator('[data-action="play:toggle"]').click();test('Playback › Play / pause plays',await playing());await stop();
await p.locator('[data-menu=edit] .menu-title').click();test('Menu shows each command with its key',await ev(()=>document.querySelector('[data-action="edit:undo"] kbd').textContent)==='Ctrl+Z');
await p.keyboard.press('Escape');test('Esc closes the menu',await ev(()=>!document.querySelector('#doodle-menubar .menu.open')));
await p.locator('[data-menu=file] .menu-title').click();await p.mouse.click(300,600);test('Clicking outside closes the menu',await ev(()=>!document.querySelector('#doodle-menubar .menu.open')));
let saved=0;await p.exposeFunction('__saved',()=>saved++);await ev(()=>window.addEventListener("keydown",e=>{if(e.ctrlKey&&e.key==="s")window.__saved()},true));
await p.locator('[data-menu=file] .menu-title').click();await p.locator('[data-action="file:save"]').click();await p.waitForTimeout(100);test('File › Save sends the save command',saved===1,{saved});
// Each default key reaches a handler
await p.locator('button[data-workspace="animate"]').click();await p.keyboard.press('Home');await p.keyboard.press('.');test('. steps one frame',await ev(()=>DoodleDrawFrames.frame)===1);
await p.keyboard.press('Shift+ArrowRight');test('Shift+→ steps ten frames',await ev(()=>DoodleDrawFrames.frame)===11);
await p.keyboard.press('Home');test('Home goes to frame 1',await ev(()=>DoodleDrawFrames.frame)===0);
const loopOn=()=>ev(()=>document.getElementById('loop').classList.contains('on'));const l0=await loopOn();await p.keyboard.press('l');test('L toggles loop outside Draw',await loopOn()!==l0);await p.keyboard.press('l');
await p.keyboard.press('4');test('4 opens Draw',await ev(()=>BunnyStudio.workspace)==='draw');await p.keyboard.press('l');test('L is the lasso inside Draw',await ev(()=>DoodleDrawing._fx.tool)==='lasso'&&await loopOn()===l0);
await p.keyboard.press('b');test('B is the pen inside Draw',await ev(()=>DoodleDrawing._fx.tool)==='pen');
// Remapping
await ev(()=>DoodleKeymap.setKeys('play:toggle',['P']));await p.keyboard.press('p');const pp=await playing();await stop();await p.keyboard.press('Space');const ps=await playing();await stop();
test('Play remapped to P: P plays and Space no longer does',pp&&!ps,{pp,ps});
await ev(()=>DoodleKeymap.setKeys('draw:onion',['U']));const o0=await ev(()=>DoodleDrawing._fx.onion);await p.keyboard.press('u');const o1=await ev(()=>DoodleDrawing._fx.onion);await p.keyboard.press('o');const o2=await ev(()=>DoodleDrawing._fx.onion);
test('Onion remapped to U: U toggles it, O does nothing',o1!==o0&&o2===o1,{o0,o1,o2});
const moved=await ev(()=>DoodleKeymap.setKeys('draw:mirror',['U']));test('Taking a key from another command says so and frees it',moved.includes('Onion skins on / off')&&!(await ev(()=>DoodleKeymap.keysOf('draw:onion'))).includes('U'),moved);
// hold-to-flip remapped
await ev(()=>{const l=DoodleDrawing.selected;DoodleDrawing._fx.find(l).cels=[];for(const [f,x]of [[0,0],[4,40]])DoodleDrawing.assistantDraw({layerId:l,frame:f,strokes:[{points:[[x,0],[x+30,30],[x+60,0]]}]});DoodleDrawing.seek(4)});
await ev(()=>DoodleKeymap.setKeys('draw:flip-back',['A']));await p.keyboard.down('a');const fA=await ev(()=>DoodleDrawFrames.frame);await p.keyboard.up('a');const fB=await ev(()=>DoodleDrawFrames.frame);test('Hold-to-flip works on a remapped key',fA===0&&fB===4,{fA,fB});
// Recording a key in the dialog
await p.keyboard.press('F1');await p.locator('#keymap-dialog [data-action="anim:key"] .keymap-chip button').first().click();await p.keyboard.press('Shift+K');
test('Shortcut dialog records a new key',(await ev(()=>DoodleKeymap.keysOf('anim:key')))[0]==='Shift+K');
await p.screenshot({path:'qa/fbf/keymap-dialog.png'});
await p.locator('#keymap-dialog [data-action="anim:key"] .keymap-reset').click();test('Default puts one command back',(await ev(()=>DoodleKeymap.keysOf('anim:key'))).join()==='K,I');
await p.locator('#keymap-close').click();
await ev(()=>DoodleKeymap.reset());test('Reset all brings Space back',(await ev(()=>DoodleKeymap.keysOf('play:toggle'))).join()==='Space');
await p.reload();await p.waitForFunction(()=>window.DoodleKeymap,null,{timeout:60000});await ev(()=>{document.querySelector('#studio-home')?.close();DoodleKeymap.setKeys('play:toggle',['P'])});await p.reload();await p.waitForFunction(()=>window.DoodleKeymap,null,{timeout:60000});
test('Remapped keys are remembered after a restart',(await ev(()=>DoodleKeymap.keysOf('play:toggle'))).join()==='P');await ev(()=>{document.querySelector('#studio-home')?.close();DoodleKeymap.reset()});
// Play from the end restarts at frame 1 with the audio, loop on or off
await ev(async()=>{const sr=48000,n=sr*2,buf=new ArrayBuffer(44+n*2),v=new DataView(buf);const w=(o,s)=>[...s].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));w(0,'RIFF');v.setUint32(4,36+n*2,true);w(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sr,true);v.setUint32(28,sr*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,'data');v.setUint32(40,n*2,true);for(let i=0;i<n;i++)v.setInt16(44+i*2,Math.sin(i/20)*8000,true);await BunnyAudio.importAudio(new Blob([buf],{type:'audio/wav'}),{type:'voice',name:'tone',at:0});});
for(const loop of [true,false]){await ev(want=>{const b=document.getElementById('loop');if(b.classList.contains('on')!==want)b.click()},loop);await p.keyboard.press('End');await ev(()=>window.__src.length=0);
 await p.keyboard.press('Space');await p.waitForTimeout(400);const r=await ev(()=>({f:DoodleDrawFrames.frame,src:[...window.__src]}));await stop();
 test(`Play from the last frame starts at frame 1 with its audio (loop ${loop?'on':'off'})`,r.f>3&&r.f<20&&r.src[0]===0,r);}
await ev(()=>{const b=document.getElementById('loop');if(!b.classList.contains('on'))b.click()});await p.keyboard.press('Home');await ev(()=>window.__src.length=0);await p.keyboard.press('Space');await p.waitForTimeout(2400);
const w=await ev(()=>({f:DoodleDrawFrames.frame,src:[...window.__src]}));await stop();test('On loop the audio starts again from 0 when the playhead wraps',w.f<20&&w.src.filter(x=>x===0).length>=2,w);
// Draw holds
await p.locator('button[data-workspace="draw"]').click();await ev(()=>{localStorage.setItem('doodle.draw.hold','2');});await p.keyboard.press('Home');await p.locator('#draw-add-above').click();
const c0=await ev(()=>{const l=DoodleDrawing._fx.find(DoodleDrawing.selected);return l.cels.map(c=>[c.frame,c.endFrame])});test('A new drawing layer holds for 2 frames, not the whole shot',JSON.stringify(c0)==='[[0,2]]',c0);
await ev(()=>DoodleDrawing.seek(0));await p.locator('#draw-hold-more').click();test('Hold + lengthens this drawing',await ev(()=>DoodleDrawing._fx.find(DoodleDrawing.selected).cels[0].endFrame)===3);
await p.locator('#draw-hold-len').fill('6');await p.locator('#draw-hold-len').press('Enter');test('Typing a hold sets it exactly',await ev(()=>DoodleDrawing._fx.find(DoodleDrawing.selected).cels[0].endFrame)===6);
await p.keyboard.press('F6');const d=await ev(()=>({f:DoodleDrawFrames.frame,c:DoodleDrawing._fx.find(DoodleDrawing.selected).cels.map(c=>[c.frame,c.endFrame])}));test('F6 duplicates to the frame after the hold',d.f===6&&d.c[1][0]===6&&d.c[1][1]===8,d);
await p.locator('#draw-hold-new').selectOption('0');await ev(()=>DoodleDrawing.seek(10));await p.keyboard.press('F7');const t=await ev(()=>DoodleDrawing._fx.find(DoodleDrawing.selected).cels.at(-1));test('"to next" makes new drawings hold until the next one',t.endFrame===undefined,t);
test('Strip labels show the frame and its hold',await ev(()=>document.querySelector('#draw-thumbs .draw-thumb span').textContent)==='F1 · 6f');
await p.screenshot({path:'qa/fbf/draw-panel.png'});
}catch(e){console.log('ERROR',e.message);process.exitCode=1;}
console.log('page errors',errors);await b.close();server.close();})();
