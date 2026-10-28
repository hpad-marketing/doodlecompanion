// Mouth sets: template export, import of a drawn sheet / single files / loose SVGs, rig swap on stage,
// undo, round trip, and real clicks through Tools › Mouth sets… Run next to a built index.studio.html.
const fs=require('fs'),http=require('http'),path=require('path'),os=require('os');let chromium;try{({chromium}=require('./qa-home-guard.cjs')(require('playwright')))}catch{({chromium}=require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))}
const W=+process.argv[2]||1440,H=+process.argv[3]||1000;
(async()=>{const server=http.createServer((q,r)=>{r.setHeader('Content-Type','text/html');r.end(fs.readFileSync('index.studio.html'))});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const b=await chromium.launch();const test=(n,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+n+(ok?'':' '+JSON.stringify(d)));if(!ok)process.exitCode=1};
const page=async()=>{const p=await b.newPage({viewport:{width:W,height:H}}),errors=[];p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());return{p,errors}};
try{
{const{p,errors}=await page();
await p.goto('http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.DoodleMouthSets,null,{timeout:90000});await p.evaluate(()=>document.querySelector('#studio-home')?.close());
const sheet=await p.evaluate(()=>DoodleMouthSets.sheet('guide'));
const meta=JSON.parse(sheet.match(/<metadata[^>]*>([^<]*)</)[1].replace(/&quot;/g,'"'));
const cell=k=>meta.cells.find(c=>c.key===k);
// A user layer on top of everything, in absolute sheet coordinates, Inkscape style.
const AI=cell('AI'),MBP=cell('MBP'),E=cell('E'),O=cell('O');
const user=`<g inkscape:label="Layer 1" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
<ellipse cx="${AI.x+240}" cy="${AI.y+200}" rx="140" ry="90" fill="#000000" stroke="#000" stroke-width="1"/>
<path d="M${MBP.x+120} ${MBP.y+180} Q${MBP.x+240} ${MBP.y+230} ${MBP.x+360} ${MBP.y+180}" fill="none" stroke="#1f1f1d" stroke-width="6"/>
<g transform="translate(${E.x} ${E.y}) scale(2)"><path fill-rule="evenodd" d="M60 70 L180 70 L170 120 L70 120 Z M90 80 L150 80 L150 95 L90 95 Z" fill="#111"/></g>
<rect x="${O.x+200}" y="${O.y+150}" width="80" height="100" rx="40" fill="#ffffff" stroke="#000" stroke-width="20"/>
</g>`;
const drawn=sheet.replace('</svg>',user+'</svg>');
const single=(await p.evaluate(()=>DoodleMouthSets.single(8))).replace('</svg>','<circle cx="300" cy="300" r="60" fill="#1f1f1d"/></svg>');
const loose='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path d="M100 500 Q500 800 900 500 Q500 650 100 500 Z" fill="black"/></svg>';
const res=await p.evaluate(async([a,b,c])=>DoodleMouthSets.importFiles([{name:'Mouth sheet.svg',text:a},{name:'08-FV.svg',text:b},{name:'smile 01.svg',text:c}]),[drawn,single,loose]);
test('imports sheet boxes and single files by name',JSON.stringify(res.imported.sort())===JSON.stringify(['AI','E','FV','MBP','O','Smile 01 - subtle']),res);
const st=await p.evaluate(()=>{const c=DoodleMouthSets.current(),m=c.mouths,bb=s=>{const xs=s.flatMap(q=>q.pts.map(p=>p[0])),ys=s.flatMap(q=>q.pts.map(p=>p[1]));return[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)].map(v=>Math.round(v))};return{name:c.name,AI:bb(m.AI.shapes),AIstyle:m.AI.shapes.map(s=>[s.fill,s.stroke,s.closed]),MBP:m.MBP.shapes.map(s=>[s.fill,s.stroke,s.closed,s.pts.length]),E:m.E.shapes.map(s=>[s.fill,s.stroke,s.closed]),O:m.O.shapes.map(s=>[s.fill,s.stroke,s.closed]),FV:bb(m.FV.shapes),smile:bb(m['Smile 01 - subtle'].shapes),saved:!!DoodleMouthSets._qa.project().mouthSet,lib:DoodleMouthSets.library().length}});

// AI ellipse: centre (AI.x+240, AI.y+200) -> source (196+60, 436+50) = (256,486); rx 140/4 = 35.
test('sheet drawing lands on the mouth centre at true size',Math.abs(st.AI[0]-221)<=1&&Math.abs(st.AI[1]-291)<=1&&Math.abs(st.AI[2]-464)<=1&&Math.abs(st.AI[3]-508)<=1,st.AI);
test('hairline outline on a filled shape is dropped',st.AIstyle.length===1&&st.AIstyle[0][0]==='ink'&&!st.AIstyle[0][1],st.AIstyle);
test('open line stays an open line at Bunny weight',st.MBP.length===1&&st.MBP[0][0]===null&&st.MBP[0][1]===true&&st.MBP[0][2]===false,st.MBP);
test('evenodd hole becomes face colour',st.E.length===2&&st.E[0][0]==='ink'&&st.E[1][0]==='face',st.E);
test('white fill maps to face colour and thick outline is kept',st.O.length===1&&st.O[0][0]==='face'&&st.O[0][1]===true,st.O);
test('single template file maps by its box',Math.abs((st.FV[0]+st.FV[1])/2-(196+(300-48)/4))<=1,st.FV);
test('loose drawing is centred on the mouth',Math.abs((st.smile[0]+st.smile[1])/2-256)<=1&&Math.abs(st.smile[1]-st.smile[0]-52)<=2,st.smile);
test('set saved in the story and library',st.saved&&st.lib>=1,st);
// Stage check: key AI (index 2) and compare the drawn mouth on stage with the built-in one.
const stage=await p.evaluate(()=>{const Q=DoodleMouthSets._qa,key=v=>{Q.keyMouth(v);const n=[...document.querySelectorAll('#projected-rig path[data-rig-part="mouth"]')];const bb=n.map(x=>x.getBBox());return{n:n.length,w:Math.max(...bb.map(b=>b.x+b.width))-Math.min(...bb.map(b=>b.x)),h:Math.max(...bb.map(b=>b.y+b.height))-Math.min(...bb.map(b=>b.y)),fills:n.map(x=>x.getAttribute('fill')+'/'+x.getAttribute('stroke')+'/'+x.getAttribute('stroke-width'))}};
 const mine={AI:key(2),MBP:key(7),E:key(3)};DoodleMouthSets.use(null);const built={AI:key(2)};return{mine,built};});

test('stage draws the imported AI mouth (70×44 source px)',Math.abs(stage.mine.AI.w-70)<4&&Math.abs(stage.mine.AI.h-44)<4,stage.mine.AI);
test('stage line uses Bunny weight',stage.mine.MBP.fills.some(f=>f.endsWith('/#1f1f1d/11.31936')),stage.mine.MBP);
test('switching back restores built-in mouth',Math.abs(stage.built.AI.w-40)<4,stage.built.AI);
const undo=await p.evaluate(()=>{const Q=DoodleMouthSets._qa;Q.undo();Q.keyMouth(2);const b=document.querySelector('#projected-rig path[data-rig-part="mouth"]').getBBox();return{set:Q.project().mouthSet?.name,w:b.width}});
test('undo brings the set back',undo.set&&Math.abs(undo.w-70)<4,undo);
// Round trip: the ink sheet, rescaled to millimetres the way Inkscape does, comes back unchanged.
const rt=await p.evaluate(async()=>{const M=DoodleMouthSets;M.use(null);let t=M.sheet('ink');const k=.2645833;t=t.replace(/<svg([^>]*)width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"([^>]*)>/,(m,a,w,h,vw,vh,b)=>`<svg${a}width="${w*k}mm" height="${h*k}mm" viewBox="0 0 ${vw*k} ${vh*k}"${b}><g transform="scale(${k})">`).replace(/<\/svg>\s*$/,'</g></svg>');
 const r=await M.importFiles([{name:'sheet-mm.svg',text:t}]);const c=M.current(),bb=s=>{const xs=s.flatMap(q=>q.pts.map(p=>p[0])),ys=s.flatMap(q=>q.pts.map(p=>p[1]));return[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)]};
 let worst=0,which='';for(const key of M.keys()){const a=bb(c.mouths[key.name].shapes),b=bb(M.builtInShapes(key.index));const d=Math.max(...a.map((v,i)=>Math.abs(v-b[i])));if(d>worst){worst=d;which=key.name}}return{n:r.imported.length,worst,which}});
test('ink sheet round trip (mm-scaled) keeps every mouth within 1 px',rt.n===18&&rt.worst<1,rt);
test('no page errors',!errors.length,errors);
await p.close();}
{const{p,errors}=await page();
await p.goto('http://127.0.0.1:'+server.address().port);await p.waitForFunction(()=>window.DoodleMouthSets&&document.querySelector('#doodle-menubar'),null,{timeout:90000});await p.evaluate(()=>document.querySelector('#studio-home')?.close());
// Native save mock: records what the desktop writer would receive.
await p.evaluate(()=>{window.__saved=[];let n=0;window.DoodleDesktop={exportInfo:async()=>({destination:'C:\\Users\\Sushant\\Documents\\Doodle Studio Exports'}),beginExport:async o=>({id:String(++n),o}),appendExport:async a=>{window.__chunk=a},finishExport:async a=>{const o=window.__lastBegin;return{path:'X'}},abortExport:async()=>{}};const begin=DoodleDesktop.beginExport;DoodleDesktop.beginExport=async o=>{__saved.push(o);return begin(o)};DoodleDesktop.finishExport=async a=>({path:__saved.at(-1).destination+'\\'+__saved.at(-1).name})});
await p.locator('#doodle-menubar [data-menu="tools"] .menu-title').dispatchEvent('pointerdown');
await p.locator('[data-action="tools:mouth-sets"]').click();
test('Tools › Mouth sets… opens the window',await p.locator('#mouth-sets-dialog[open]').count()===1);
await p.screenshot({path:`mouth-sets-${W}-1-open.png`});
test('18 mouth cards, none marked Yours',await p.locator('.ms-card').count()===18&&await p.locator('.ms-card .ms-tag.mine').count()===0);
await p.locator('#mouth-export-sheet').click();await p.waitForTimeout(300);
let saved=await p.evaluate(()=>__saved.map(s=>[s.destination,s.name,s.format,s.bytes]));
test('Whole sheet saves one SVG into Mouth templates',saved.length===1&&saved[0][0].endsWith('Doodle Studio Exports\\Mouth templates')&&saved[0][1]==='Mouth sheet - Bunny-built-in.svg'&&saved[0][2]==='svg',saved);
test('status names the folder',/Saved 1 SVG to .*Mouth templates/.test(await p.locator('#mouth-sets-status').textContent()),await p.locator('#mouth-sets-status').textContent());
await p.locator('#mouth-export-ref').selectOption('ink');await p.locator('#mouth-export-files').click();await p.waitForTimeout(500);
saved=await p.evaluate(()=>__saved.slice(1).map(s=>[s.destination,s.name]));
test('One file per mouth saves 18 named files',saved.length===18&&saved[6][1]==='07-MBP.svg'&&saved[0][0].endsWith('Mouth templates\\Mouths - Bunny-built-in'),saved.slice(0,3));
// Make "drawn" files and import with the real file picker.
const sheet=await p.evaluate(()=>DoodleMouthSets.sheet('guide'));const meta=JSON.parse(sheet.match(/<metadata[^>]*>([^<]*)</)[1].replace(/&quot;/g,'"'));const c=k=>meta.cells.find(x=>x.key===k);
const drawn=sheet.replace('</svg>',['AI','O','etc'].map((k,i)=>`<ellipse cx="${c(k).x+240}" cy="${c(k).y+190}" rx="${60+i*30}" ry="${40+i*10}" fill="#1f1f1d"/>`).join('')+'</svg>');
const drawnDir=fs.mkdtempSync(path.join(os.tmpdir(),'mouths-'));fs.writeFileSync(path.join(drawnDir,'My mouths.svg'),drawn);
fs.writeFileSync(path.join(drawnDir,'09-L.svg'),(await p.evaluate(()=>DoodleMouthSets.single(9))).replace('</svg>','<path d="M180 290 Q288 380 396 290" fill="none" stroke="#000" stroke-width="12"/></svg>'));
let fc=p.waitForEvent('filechooser');await p.locator('#mouth-import').click();await (await fc).setFiles([path.join(drawnDir,'My mouths.svg'),path.join(drawnDir,'09-L.svg')]);const t0=Date.now();await p.waitForFunction(()=>/Imported/.test(document.querySelector('#mouth-sets-status').textContent),null,{timeout:20000}).catch(()=>{});console.log('import ms',Date.now()-t0);
const st=await p.locator('#mouth-sets-status').textContent();
test('Import makes a set and reports what came in',/Imported 4 mouths into “My mouths”: AI, O, etc, L/.test(st),st);
test('cards show Yours on the 4 imported mouths',await p.locator('.ms-card .ms-tag.mine').count()===4);
test('picker shows the new set in use',(await p.locator('#mouth-set-pick option:checked').textContent()).startsWith('My mouths'));
await p.screenshot({path:`mouth-sets-${W}-2-imported.png`});
// Replace on one card.
fs.writeFileSync(path.join(drawnDir,'anything.svg'),'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="10" y="40" width="80" height="20" rx="10" fill="#222"/></svg>');
fc=p.waitForEvent('filechooser');await p.locator('[data-mouth-card="7"] [data-act=replace]').click();await (await fc).setFiles([path.join(drawnDir,'anything.svg')]);await p.waitForFunction(()=>/Imported 1 mouth/.test(document.querySelector('#mouth-sets-status').textContent),null,{timeout:20000}).catch(()=>{});
test('Replace… puts any file on that one mouth',await p.locator('[data-mouth-card="7"] .ms-tag').textContent()==='Yours',await p.locator('#mouth-sets-status').textContent());
// Preview on Bunny.
await p.locator('[data-mouth-card="2"] img').click();
const prev=await p.evaluate(()=>{const n=document.querySelector('#projected-rig path[data-rig-part="mouth"]').getBBox();return{w:n.width,h:n.height}});
test('clicking a mouth shows it on Bunny',Math.abs(prev.w-30)<4,prev);
test('face preview is framed on the face',await p.evaluate(()=>{const v=document.querySelector('#mouth-sets-face').getAttribute('viewBox');return!!v&&/AI/.test(document.querySelector('#mouth-sets-face-label').textContent)}));
await p.screenshot({path:`mouth-sets-${W}-3-preview.png`});
await p.locator('#mouth-sets-close').click();await p.evaluate(()=>DoodleMouthSets.open());
test('closing ends the preview, no key written',await p.evaluate(()=>!(DoodleMouthSets._qa.project().keys.mouth||[]).length));
// Reset.
await p.locator('[data-mouth-card="7"] [data-act=reset]').click();
test('Reset puts the built-in drawing back',await p.locator('[data-mouth-card="7"] .ms-tag').count()===0);
// Rename / duplicate / switch / delete.
await p.locator('#mouth-set-name').fill('Spooky mouths');await p.locator('#mouth-set-rename').click();
test('Rename',(await p.locator('#mouth-set-pick option:checked').textContent()).startsWith('Spooky mouths'));
await p.locator('#mouth-set-copy').click();
test('Duplicate switches to the copy',(await p.locator('#mouth-set-pick option:checked').textContent()).startsWith('Spooky mouths copy'));
await p.locator('#mouth-set-pick').selectOption({label:/^Spooky mouths \(/}).catch(async()=>{const v=await p.evaluate(()=>[...document.querySelectorAll('#mouth-set-pick option')].find(o=>/^Spooky mouths \(/.test(o.textContent)).value);await p.locator('#mouth-set-pick').selectOption(v);});
test('Switch set from the picker',(await p.locator('#mouth-set-pick option:checked').textContent()).startsWith('Spooky mouths ('));
await p.locator('#mouth-set-delete').click();await p.waitForTimeout(200);
test('Delete goes back to built-in and removes it from the list',(await p.locator('#mouth-set-pick option:checked').textContent()).startsWith('Bunny')&&await p.evaluate(()=>![...document.querySelectorAll('#mouth-set-pick option')].some(o=>/^Spooky mouths \(/.test(o.textContent))));
await p.locator('#mouth-sets-close').click();
test('Done closes',await p.locator('#mouth-sets-dialog[open]').count()===0);
// Lip-sync panel entry and its thumbnails follow the set.
await p.evaluate(()=>DoodleMouthSets.use(DoodleMouthSets.library().find(s=>/copy/.test(s.name)).id));
const lip=await p.evaluate(()=>{const b=document.querySelector('#lip-sync-mouth-sets');return!!b});
test('Mouth sets… button in the lip-sync panel',lip);
const th=await p.evaluate(()=>{const s=decodeURIComponent(DoodleMouthSets.thumb(2));return s.includes('<path')});
test('thumbnails render',th);
test('no page errors',!errors.length,errors);
await p.close();}
}finally{await b.close();server.close();}})();
