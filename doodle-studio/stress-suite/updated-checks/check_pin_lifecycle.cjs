const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const {chromium}=require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(path.join(root,'index.studio.html')))});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
 const check=(name,value)=>{assert.ok(value,name);results.push({name,passed:true})},bundle=()=>page.evaluate(()=>BunnyProject.bundle()),part=async id=>{if(!await page.locator('#studio-parts').isVisible())await page.evaluate(()=>BunnyStudio.setWorkspace('pose'));await page.locator('#studio-parts').click();await page.locator('#studio-parts-dialog [data-part-select="'+id+'"]').click();};
 try{
  await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>window.BunnyStudio);
  await page.evaluate(async()=>{const b=await BunnyProject.bundle();for(const id in b.project.keys)b.project.keys[id]=[];b.project.clips=[];b.project.cues=[];await BunnyProject.accept(b)});
  await (async()=>{if(!await page.locator('#mode').isVisible())await page.evaluate(()=>BunnyStudio.setWorkspace('pose'));await page.locator('#mode').click()})();await part('legL');await page.locator('.pin-controls input[type=checkbox]').check();
  check('Manual pin previews without writing a key',(await bundle()).project.keys.pinLegL.length===0&&await page.evaluate(()=>!!BunnyConstraints.pinAt('legL',0)));
  await part('body');await page.locator('#keys').click();let b=await bundle(),pin=b.project.keys.pinLegL[0];
  check('Global Add Key commits pending foot pin after part switch',pin?.v===1&&pin.target?.length===3&&pin.orientation?.length===12&&pin.reference&&pin.ease==='constant');
  await page.locator('#undo').click();{const keyGone=!(await bundle()).project.keys.pinLegL.length,preview=await page.evaluate(()=>!!BunnyConstraints.pinAt('legL',0));await part('legL');const box=await page.locator('.pin-controls input[type=checkbox]').isChecked();check('Undo removes the committed pin key and returns to the pending preview that existed before Add Key, with the checkbox matching it',keyGone&&preview&&box);await page.locator('.pin-controls input[type=checkbox]').uncheck();check('Releasing the pending pin clears its preview',!await page.evaluate(()=>BunnyConstraints.pinAt('legL',0))&&!(await bundle()).project.keys.pinLegL.length);}
  await part('legR');await page.locator('.pin-controls input[type=checkbox]').check();await page.locator('#play').click();await page.locator('#play').click();check('Playback discards unkeyed pin previews',!await page.evaluate(()=>BunnyConstraints.pinAt('legR',0)));
  await page.evaluate(()=>BunnyStudio.setWorkspace('animate'));await page.locator('#toStart').click();await page.locator('[aria-label="Next frame"]').click();await part('legR');await page.locator('.pin-controls input[type=checkbox]').check();
  check('Manual pins work at fractional frame times',await page.evaluate(()=>!!BunnyConstraints.pinAt('legR',1000/30)));
  await page.locator('#context-key').click();pin=(await bundle()).project.keys.pinLegR[0];check('Context Key pose persists valid pin metadata',pin?.v===1&&pin.target?.every(Number.isFinite));
  await page.evaluate(async()=>{const first=BunnyWorkflow.active().uid,second=BunnyWorkflow.addShot('Other shot');await BunnyWorkflow.selectShot(second);await BunnyWorkflow.selectShot(first);});
  check('Shot switches preserve keyed pins and discard other previews',!await page.evaluate(()=>BunnyConstraints.pinAt('legL',0))&&(await bundle()).project.keys.pinLegR.length===1);
  b=await bundle();b.project.keys.headYaw=[{uid:'locked-head',t:500,v:15}];b.project.locks={headYaw:true};await page.evaluate(b=>BunnyProject.accept(b),b);await part('head');await page.locator('[data-workspace="animate"]').click();await page.locator('[data-uid="locked-head"]').click();
  check('Locked key inspector is disabled',await page.locator('#key-time').isDisabled()&&await page.locator('#key-value').isDisabled());
  await page.locator('#studio-tabs').click({position:{x:2,y:2}});await page.keyboard.press('ArrowRight');await page.keyboard.press('Delete');check('Locked key resists nudge and delete',(await bundle()).project.keys.headYaw[0]?.t===500);
  b=await bundle();b.project.editing={owner:'another-device',name:'Other phone'};await page.evaluate(b=>BunnyProject.accept(b),b);check('Remote control disables authoring transport',await page.locator('#keys').isDisabled()&&await page.locator('#undo').isDisabled());
  await page.evaluate(()=>BunnyStudio.openMenu('sync'));await page.locator('#take-editing-control').click();check('Explicit Take control enables editing',!await page.locator('#keys').isDisabled()&&await page.evaluate(()=>BunnyWorkflow.canEdit()));await page.locator('#menu-close').click();
  await page.screenshot({path:path.join(root,'qa/pin-lifecycle-candidate.png')});assert.deepEqual(errors,[]);fs.writeFileSync(path.join(root,'qa/pin-lifecycle-checks.json'),JSON.stringify({results,errors},null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1)});
