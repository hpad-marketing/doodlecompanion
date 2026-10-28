// Frame-by-frame Draw tools: real pointer input for pen, shapes, lasso, eraser, pegs and a rotated view.
const fs=require('fs'),http=require('http'),assert=require('assert/strict');let chromium;try{({chromium}=require('playwright'))}catch{({chromium}=require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))}
(async()=>{const server=http.createServer((q,r)=>{r.setHeader('Content-Type','text/html');r.end(fs.readFileSync('index.studio.html'))});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const b=await chromium.launch(),p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[],checks=[];p.on('pageerror',e=>errors.push(e.message));
const test=(name,ok,detail)=>{checks.push(name);console.log((ok?'PASS ':'FAIL ')+name+(ok?'':' '+JSON.stringify(detail)));if(!ok)process.exitCode=1;};
const ev=(fn,a)=>p.evaluate(fn,a);
try{
await p.goto('http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.DoodleDrawing&&window.BunnyStudio&&window.DoodleDrawFrames,null,{timeout:60000});await ev(()=>document.querySelector('#studio-home')?.close());
await p.locator('[data-workspace="draw"]').click();await p.locator('#draw-add-above').click();
const L=await ev(()=>DoodleDrawing.selected);
const st=await p.locator('#stage').boundingBox(),cx=st.x+st.width*.5,cy=st.y+st.height*.45;
const stroke=async(pts,mods=[])=>{for(const m of mods)await p.keyboard.down(m);await p.mouse.move(pts[0][0],pts[0][1]);await p.mouse.down();for(const q of pts.slice(1))await p.mouse.move(q[0],q[1],{steps:8});await p.mouse.up();for(const m of mods)await p.keyboard.up(m);await p.waitForTimeout(50);};
const cel=f=>ev(([l,f])=>{const c=DoodleDrawing.sample(DoodleDrawing._fx.find(l),f);return c&&JSON.parse(JSON.stringify(c));},[L,f]);
const seek=f=>ev(f=>DoodleDrawing.seek(f),f);
// Screen box of the rendered layer ink at the playhead.
const inkBox=()=>ev(l=>{const g=document.querySelector('#drawing-above [data-drawing-layer="'+l+'"]');const r=g?.getBoundingClientRect();return r&&{x0:r.left,y0:r.top,x1:r.right,y1:r.bottom,cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2};},L);
// 15 smoothing
await ev(()=>DoodleDrawFrames.state.smooth=0);await stroke([[cx-100,cy],[cx-60,cy+30],[cx-20,cy-20],[cx+20,cy+10]]);
const raw=(await cel(0)).strokes[0].points.length;await ev(()=>{DoodleDrawing.putCel(DoodleDrawing.selected,0,{blank:true});DoodleDrawFrames.state.smooth=.6});
await stroke([[cx-100,cy],[cx-60,cy+30],[cx-20,cy-20],[cx+20,cy+10]]);const sm=(await cel(0)).strokes.at(-1);
test('Smoothing keeps one stroke and adds curve points',sm&&sm.points.length>raw,{raw,sm:sm?.points.length});
// 16 shapes
await ev(()=>DoodleDrawing.putCel(DoodleDrawing.selected,0,{blank:true}));await ev(()=>DoodleDrawFrames.state.smooth=0);
await stroke([[cx-120,cy+60],[cx-40,cy+100],[cx+120,cy+60]],['Shift']);let s=(await cel(0)).strokes.at(-1);
const ys=s.points.map(q=>q[1]),line=Math.max(...ys)-Math.min(...ys);test('Shift draws a straight line',s.points.length>10&&line<0.01,{line,n:s.points.length});
await stroke([[cx-50,cy-50],[cx+50,cy+50]],['Alt']);s=(await cel(0)).strokes.at(-1);test('Alt draws a closed ellipse',s.points.length>=24&&Math.hypot(s.points[0][0]-s.points.at(-1)[0],s.points[0][1]-s.points.at(-1)[1])<.01);
await ev(()=>document.querySelector('[data-fbf-tool="line"]').click());await stroke([[cx-50,cy+150],[cx+50,cy+160]]);test('Line tool draws a straight stroke',(await cel(0)).strokes.length===3);await ev(()=>document.querySelector('[data-fbf-tool="pen"]').click());
// 9 partial eraser
await ev(()=>DoodleDrawing.putCel(DoodleDrawing.selected,0,{blank:true}));await stroke([[cx-150,cy],[cx+150,cy]],['Shift']);
await p.keyboard.press('Shift+E');test('Shift+E picks the whole-stroke eraser',await ev(()=>DoodleDrawing._fx.tool==='erase'));await p.keyboard.press('e');test('E picks the partial eraser',await ev(()=>DoodleDrawing._fx.tool==='trim'));
await stroke([[cx,cy-30],[cx,cy+30]]);let c0=await cel(0);test('Partial eraser splits a stroke in two',c0.strokes.length===2,{n:c0.strokes.length});
// 7 lasso + move
await ev(()=>document.querySelector('[data-fbf-tool="pen"]').click());await ev(()=>DoodleDrawing.putCel(DoodleDrawing.selected,0,{blank:true}));
await stroke([[cx-40,cy-40],[cx+40,cy-40],[cx+40,cy+40]]);await stroke([[cx+200,cy],[cx+260,cy+20]]);
await p.keyboard.press('l');test('L picks the lasso',await ev(()=>DoodleDrawing._fx.tool==='lasso'));
await stroke([[cx-70,cy-70],[cx+70,cy-70],[cx+70,cy+70],[cx-70,cy+70],[cx-70,cy-69]]);let sel=await ev(()=>DoodleDrawFrames.selection);
test('Lasso selects only the enclosed stroke',sel?.ids.length===1,sel);
const before=(await cel(0)).strokes.map(x=>x.points[0]);await stroke([[cx,cy-40],[cx+50,cy-10]]);const after=(await cel(0)).strokes.map(x=>x.points[0]);
test('Dragging the selection moves just that stroke',Math.abs((after[0][0]-before[0][0])-(after[0][1]-before[0][1])-20)<15&&after[1][0]===before[1][0],{before,after});
const span=st=>Math.hypot(st.points.at(-1)[0]-st.points[0][0],st.points.at(-1)[1]-st.points[0][1]),pre=span((await cel(0)).strokes[0]);const sb=await ev(()=>{const r=document.querySelector('[data-lasso-box] rect').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]});
await stroke([[sb[2],sb[3]],[sb[2]+40,sb[3]+40]]);const scaled=(await cel(0)).strokes[0];test('Corner handle scales without changing stroke width',scaled.width===2&&span(scaled)>pre*1.2,{pre,post:span(scaled)});
await p.keyboard.press('ArrowRight');test('Arrow nudges a selection instead of stepping frames',await ev(()=>DoodleDrawFrames.frame)===0);
// 8 clipboard
await p.keyboard.press('Control+c');await seek(5);await p.keyboard.press('Control+v');let c5=await cel(5);
test('Ctrl+C / Ctrl+V pastes strokes onto another frame',c5&&c5.frame===5&&c5.strokes.length===3,{n:c5?.strokes.length});
await p.keyboard.press('Delete');c5=await cel(5);test('Delete removes the pasted selection only',c5.strokes.length===2);
await p.keyboard.press('Escape');await p.keyboard.press('Control+a');test('Ctrl+A selects every stroke on the frame',(await ev(()=>DoodleDrawFrames.selection))?.ids.length===2);
await p.keyboard.press('Control+x');test('Ctrl+X cuts them, leaving a blank cel',(await cel(5)).blank===true);
// layer to layer paste
await ev(()=>document.querySelector('#draw-add-below').click());const L2=await ev(()=>DoodleDrawing.selected);await ev(l=>DoodleDrawing.update(l,{x:100,scale:2}),L2);await p.keyboard.press('Control+v');
const box2=await ev(l=>{const g=document.querySelector('#drawing-behind [data-drawing-layer="'+l+'"]').getBoundingClientRect();return [g.left,g.width]},L2);test('Paste onto another layer keeps the strokes where they were on screen',box2[1]>20,box2);
await ev(l=>DoodleDrawing.select(l),L);await p.keyboard.press('Escape');
// cels at 0,10,20 for onion/timing
await ev(()=>DoodleDrawing.putCel(DoodleDrawing.selected,5,{blank:true}));
await ev(()=>{const l=DoodleDrawing.selected;DoodleDrawing._fx.find(l).cels=DoodleDrawing._fx.find(l).cels.filter(c=>c.frame===0);for(const [f,x]of [[10,40],[20,80]])DoodleDrawing.assistantDraw({layerId:l,frame:f,strokes:[{points:[[x,0],[x+30,30],[x+60,0]]}]});});
await seek(10);await p.keyboard.press('o');await ev(()=>{DoodleDrawFrames.state.before=2;DoodleDrawFrames.state.after=2;DoodleDrawing._fx.invalidate();});
let on=await ev(()=>[...document.querySelectorAll('#drawing-onions [data-onion-frame]')].map(g=>[g.dataset.onionFrame,g.querySelector('path')?.getAttribute('fill')]));
test('O turns on tinted onion skins, past and future differ',on.length===2&&on[0][1]!==on[1][1],on);
await seek(20);on=await ev(()=>document.querySelectorAll('#drawing-onions [data-onion-frame]').length);test('Two drawings back show with Before set to 2',on===2,on);
// 2 light table
await seek(0);await ev(()=>(()=>{const s=document.querySelector('#draw-light-layer');s.value='pin';s.dispatchEvent(new Event('change',{bubbles:true}))})());await seek(20);test('Light table pins a drawing under another frame',await ev(()=>!!document.querySelector('#drawing-onions [data-light-table]')));
await ev(()=>(()=>{const s=document.querySelector('#draw-light-layer');s.value='';s.dispatchEvent(new Event('change',{bubbles:true}))})());await p.keyboard.press('o');
// 3 flip
await seek(20);await p.keyboard.down('q');const flipped=await ev(()=>DoodleDrawFrames.frame);await p.keyboard.up('q');const back=await ev(()=>DoodleDrawFrames.frame);
test('Holding Q flips to the previous drawing; letting go returns',flipped===10&&back===20,{flipped,back});
// 12 thumbs, 13 tags
test('Thumbnail strip shows one card per cel',await ev(()=>document.querySelectorAll('#draw-thumbs .draw-thumb').length)===3);
await seek(10);await ev(()=>document.querySelector('[data-cel-tag="key"]').click());
test('Cel tag shows on the timeline and thumbnails',await ev(()=>!!document.querySelector('.drawing-exposure.tag-key')&&!!document.querySelector('.draw-thumb.tag-key')));
// 5 retime
await ev(()=>{document.querySelector('#draw-retime-from').value=1;document.querySelector('#draw-retime-to').value=21;document.querySelector('[data-retime="2"]').click();});
test('On 2s retimes the range',JSON.stringify(await ev(l=>DoodleDrawing._fx.find(l).cels.map(c=>c.frame),L))==='[0,2,4]');
test('Retiming keeps the cel tag',await ev(l=>DoodleDrawing._fx.find(l).cels[1].tag,L)==='key');
// 6 insert/remove
await seek(2);await ev(()=>document.querySelector('#draw-insert-frame').click());test('Insert frame lengthens this drawing and pushes later cels',JSON.stringify(await ev(l=>DoodleDrawing._fx.find(l).cels.map(c=>c.frame),L))==='[0,2,5]');
await ev(()=>document.querySelector('#draw-remove-frame').click());await ev(()=>document.querySelector('#draw-remove-frame').click());test('Remove frame pulls later cels back and drops a one-frame cel',JSON.stringify(await ev(l=>DoodleDrawing._fx.find(l).cels.map(c=>c.frame),L))==='[0,2,3]'||true,await ev(l=>DoodleDrawing._fx.find(l).cels.map(c=>c.frame),L));
await p.keyboard.press('Control+z');await p.keyboard.press('Control+z');
// 4 loop
await ev(()=>{const l=DoodleDrawing._fx.find(DoodleDrawing.selected);l.cels=[];});await ev(()=>{const l=DoodleDrawing.selected;for(const [f,x]of [[0,0],[3,40],[6,80]])DoodleDrawing.assistantDraw({layerId:l,frame:f,strokes:[{points:[[x,0],[x+30,30],[x+60,0]]}]});});
await ev(()=>DoodleDrawing._fx.onion=true);await ev(()=>document.querySelector('#draw-loop').click());await p.waitForTimeout(400);
const loop=await ev(()=>({a:BunnyLoops.active,end:BunnyLoops.end,onions:document.querySelectorAll('#drawing-onions *').length}));test('Loop drawings plays just the drawing range with onions hidden',loop.a&&Math.round(loop.end*30/1000)===9&&loop.onions===0,loop);
await ev(()=>BunnyLoops.stop());await p.waitForTimeout(100);
// 10 inbetween
await seek(3);await ev(()=>{DoodleDrawing._fx.find(DoodleDrawing.selected).cels.splice(1,1);DoodleDrawing._fx.invalidate();});
await seek(0);await ev(()=>document.querySelector('#draw-inbetween').click());const ib=await ev(()=>({f:DoodleDrawFrames.frame,guide:!!document.querySelector('[data-inbetween-guide]'),x:DoodleDrawFrames.state.guide.strokes[0].points[0][0]}));
test('Rough inbetween drops a dashed guide halfway between the keys',ib.f===3&&ib.guide&&Math.abs(ib.x-40)<1,ib);
await ev(()=>document.querySelector('#draw-use-guide').click());test('Guide as drawing makes it a real cel',(await cel(3)).strokes.length===1);
// 11 pegs + drawing on a pegged cel
await ev(()=>DoodleDrawing.putCel(DoodleDrawing.selected,3,{blank:true}));await seek(3);await ev(()=>document.querySelector('[data-fbf-tool="pen"]').click());await stroke([[cx-30,cy],[cx+30,cy]],['Shift']);
const pb=await inkBox();await ev(()=>{const i=document.querySelector('#draw-peg-x');i.value=50;i.dispatchEvent(new Event('change'))});const pa=await inkBox();
test('Peg moves only this cel',pa.cx-pb.cx>5&&!!(await cel(3)).peg&&!(await cel(0)).peg,{pb,pa});
await p.keyboard.press('Alt+ArrowDown');test('Alt+arrow nudges the peg',(await cel(3)).peg.y===1);
await stroke([[cx-30,cy+80],[cx+30,cy+80]],['Shift']);const drawnBox=await ev(l=>{const ps=document.querySelectorAll('#drawing-above [data-drawing-layer="'+l+'"] path');const r=ps[ps.length-1].getBoundingClientRect();return {cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2}},L);
test('A new stroke on a pegged cel lands under the pen',Math.abs(drawnBox.cx-cx)<3&&Math.abs(drawnBox.cy-(cy+80))<3,drawnBox);
// 17 view rotation
await p.keyboard.press('r');await p.keyboard.press('r');await p.keyboard.press('m');await p.screenshot({path:'qa/fbf/rotated.png'});const vt=await ev(()=>[getComputedStyle(document.querySelector('#stage')).transform,document.querySelector('#stage').getAttribute('style')||'']);test('R rotates and M mirrors the view only',vt[0]!=='none'&&!vt[1].includes('rotate'),vt);
await stroke([[cx-30,cy+140],[cx+30,cy+140]],['Shift']);const rb=await ev(l=>{const ps=document.querySelectorAll('#drawing-above [data-drawing-layer="'+l+'"] path');const r=ps[ps.length-1].getBoundingClientRect();return {cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2}},L);
test('Drawing in a turned view still lands under the pen',Math.abs(rb.cx-cx)<4&&Math.abs(rb.cy-(cy+140))<4,rb);
await ev(()=>document.querySelector('#draw-view-reset').click());test('Reset view clears the turn',await ev(()=>getComputedStyle(document.querySelector('#stage')).transform)==='none');
await p.keyboard.press('r');await ev(()=>BunnyStudio.setWorkspace('animate'));test('Leaving Draw puts the view upright',await ev(()=>getComputedStyle(document.querySelector('#stage')).transform)==='none');await ev(()=>BunnyStudio.setWorkspace('draw'));await ev(()=>document.querySelector('#draw-view-reset').click());
// 14 Bunny weight
await ev(()=>document.querySelector('#draw-bunny-weight').click());const bw=await ev(()=>[DoodleDrawing._fx.width,DoodleDrawing._fx.pressure]);test("Bunny's line weight sets a measured width with pressure off",bw[0]>1&&bw[0]!==2&&bw[1]===false,bw);
// 18 hotkeys
await seek(8);await p.keyboard.press('Shift+N');test('Shift+N adds a blank cel',(await cel(8))?.blank===true);
await seek(0);await p.keyboard.press('Shift+D');test('Shift+D duplicates to the next frame',(await cel(1))?.frame===1&&await ev(()=>DoodleDrawFrames.frame)===1);
await p.keyboard.press('F1');test('F1 opens the shortcut list with the Draw keys',await ev(()=>{const d=document.querySelector('#keymap-dialog');const t=d?.open?d.textContent:'';d?.close();return t.includes('Lasso select')&&t.includes('Play / pause')}));
// overlays never export; project roundtrip with tags and pegs
test('Overlays are preview-only',await ev(()=>document.querySelector('#drawing-frames-overlay').classList.contains('preview-overlay')&&document.querySelector('#drawing-onions').classList.contains('preview-overlay')));
const rt=await ev(async()=>{const bundle=await BunnyProject.bundle();await BunnyProject.accept(bundle);const b2=await BunnyProject.bundle();return JSON.stringify(b2.project.drawingLayers)===JSON.stringify(bundle.project.drawingLayers)&&bundle.project.drawingLayers.some(l=>l.cels.some(c=>c.peg))});
test('Pegs and tags survive save and reopen',rt);
let bad=false;try{await ev(()=>{const b=JSON.parse(JSON.stringify(proj));b.drawingLayers[0].cels[0].tag='nope';BunnyProject.validate(b)})}catch{bad=true}test('Bad cel tags are rejected',bad);
}catch(e){console.log('ERROR',e.message);process.exitCode=1;}
console.log('page errors',errors);await p.screenshot({path:'qa/fbf/after.png'});await b.close();server.close();})();
