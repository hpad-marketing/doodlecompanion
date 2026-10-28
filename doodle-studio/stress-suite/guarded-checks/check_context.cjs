const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const fs=require('fs'),path=require('path');const root=path.resolve(__dirname,'..');
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});const p=await b.newPage({viewport:{width:1440,height:1000}});const errors=[],checks=[];p.on('pageerror',e=>errors.push(e.message));
 const check=(name,ok)=>{checks.push({name,passed:!!ok});if(!ok)throw Error(name)};
 try{
 await p.goto('file:///C:/Users/Sushant/Documents/Talking%20Character%20App/index.html');
 const part=id=>p.locator(`[data-part-select="${id}"]`);const control=id=>p.locator(`[data-context-track="${id}"]`);
 async function set(id,v){const n=control(id);await n.fill(String(v));await n.dispatchEvent(n.tagName==='SELECT'?'change':'input');}
 check('nine explicit parts',await p.locator('#parts-panel [data-part-select]').count()>=9)/*a tenth part was added later*/;
 check('legs behind torso',await p.evaluate(()=>{const c=[...document.querySelector('#native-torso').parentElement.children];return c.indexOf(document.querySelector('#native-legL'))<c.indexOf(document.querySelector('#native-torso'))}));
 await p.locator('[data-clip="walk"]').click();await part('armL').click();
 check('part selection clears clip inspector',await control('armL').count()===1);
 const headBefore=await p.locator('#head').getAttribute('transform');await set('armL',25);
 check('arm slider changes arm only',(await p.locator('#native-armL').getAttribute('transform')).includes('25.000')&&(await p.locator('#head').getAttribute('transform'))===headBefore);
 check('arm key visible in relevant timeline',await p.locator('[data-track="armL"] .kf').count()===1);
 await part('body').click();await set('bodyRot',15);await set('bodyY',10);
 check('body moves upper hierarchy',(await p.locator('#native-torso').getAttribute('transform')).includes('rotate(15')&&await p.locator('#native-torso #head').count()===1&&await p.locator('#native-torso #native-armL').count()===1);
 await part('figure').click();await set('figureRot',30);
 check('entire figure rotates',(await p.locator('#actor').getAttribute('transform')).includes('rotate(30 '));
 await part('mouth').click();const before=await p.locator('#actor').getAttribute('transform');const faceBefore=await p.locator('#native-face').innerHTML();
 await control('mouth').selectOption('2');
 check('mouth changes geometry without moving body',before===await p.locator('#actor').getAttribute('transform')&&faceBefore!==await p.locator('#native-face').innerHTML());
 await part('head').click();check('mouth change preserves expression',await control('expression').inputValue()==='0');
 const filter=await p.locator('#track-filter').isVisible()/*the UX pass shows every track and hides this filter*/;if(filter)await p.locator('#track-filter').click();check('all fifteen tracks available',await p.locator('#tl [data-track]').count()>=15)/*the timeline has grown past fifteen tracks*/;
 if(filter)await p.locator('#track-filter').click();
 // Reset transforms for a genuine canvas drag on a hand surface.
 await part('figure').click();await p.locator('#context-reset').click();await part('body').click();await p.locator('#context-reset').click();await part('armL').click();await p.locator('#context-reset').click();
 const target=p.locator('#native-armL > path').last();const box=await target.boundingBox();
 await p.mouse.move(box.x+box.width/2,box.y+box.height/2);await p.mouse.down();await p.mouse.move(box.x+box.width/2+60,box.y+box.height/2,{steps:6});await p.mouse.up();
 check('canvas hand drag moves arm',(await p.locator('#native-armL').getAttribute('transform'))!=='rotate(0.000 550.5723736211881 701.5589535404383)' && Math.abs(parseFloat((await p.locator('#native-armL').getAttribute('transform')).match(/rotate\(([-\d.]+)/)[1]))>1);
 await p.screenshot({path:path.join(root,'qa/stage04-editor.png'),fullPage:true});
 await p.setViewportSize({width:390,height:844});check('phone has no page overflow',await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:path.join(root,'qa/stage04-phone.png'),fullPage:true});
 check('no JavaScript errors',errors.length===0);
 }finally{fs.writeFileSync(path.join(root,'qa/stage04-context-checks.json'),JSON.stringify({checks,errors},null,2));await b.close()}
 console.log(JSON.stringify(checks));
})().catch(e=>{console.error(e);process.exit(1)});
