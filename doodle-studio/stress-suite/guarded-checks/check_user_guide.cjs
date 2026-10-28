const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {_electron,chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const root=process.cwd(),qa=path.join(root,'qa/user-guide-20261025'),profile=process.env.DOODLE_GUIDE_PROFILE||path.join(qa,'profile'),assets=path.join(root,'docs/user-guide/assets'),guide=path.join(root,'docs/user-guide/Doodle-Studio-User-Guide.html');
 const origin='http://127.0.0.1:'+fs.readFileSync(path.join(profile,'ui-port.txt'),'utf8').trim();
 const app=await _electron.launch({executablePath:path.join(root,'deliveries/20261025-141533/desktop/Doodle Studio Window.exe'),args:['--doodle-url='+origin,'--doodle-data-dir='+profile],env:Object.fromEntries(Object.entries(process.env).filter(([k])=>!['ELECTRON_RUN_AS_NODE','NODE_OPTIONS'].includes(k)))}),p=await app.firstWindow(),checks=[],errors=[];
 const check=(name,ok)=>{checks.push({name,passed:!!ok});assert(ok,name);console.log(name)};
 let g,browser,nativeClosed=false,completed=false;
 try{
  await p.waitForFunction(()=>window.DoodleHome);await p.evaluate(()=>DoodleHome.resume());console.log('Guide runtime ready');
  const recipes=JSON.parse(fs.readFileSync(path.join(qa,'example-recipes.json'))),recipeResults=[];
  for(let i=0;i<recipes.length&&!process.env.DOODLE_GUIDE_SKIP_RECIPES;i++){
   const result=await p.evaluate(async({recipe,i})=>{
    await BunnyProject.accept({format:'BunnyStudio',version:2,project:{projectID:'guide-recipe-'+i,title:'Guide test only',aspect:'portrait',keys:{},clips:[],cues:[]}});BunnyWorkflow.takeControl();
    const before=JSON.stringify(await BunnyProject.bundle()),v=await DoodleAssistantScript.run({projectId:'guide-recipe-'+i,code:recipe.code,dryRun:true});
    if(!v.framing.every(f=>f.ok))return{ok:false,framing:v.framing};
    const unchanged=before===JSON.stringify(await BunnyProject.bundle()),preview=DoodleAssistantWorkspace.preview({projectId:'guide-recipe-'+i,validationId:v.validationId,time:500});
    const apply=DoodleAssistantWorkspace.apply({projectId:'guide-recipe-'+i,validationId:v.validationId});DoodleAssistantWorkspace.undo({projectId:'guide-recipe-'+i});
    return{ok:true,unchanged,preview:preview.previewOnly,undoable:apply.undoable};
   },{recipe:recipes[i],i});
   recipeResults.push({label:recipes[i].label,...result});fs.writeFileSync(path.join(qa,'recipe-checks.json'),JSON.stringify({passed:false,recipes:recipeResults},null,2));if(!result.ok||!result.unchanged||!result.preview||!result.undoable)console.log(JSON.stringify(result));check('Native recipe '+(i+1)+': validate, preview, Apply and Undo',result.ok&&result.unchanged&&result.preview&&result.undoable);
  }
  if(!process.env.DOODLE_GUIDE_SKIP_RECIPES)fs.writeFileSync(path.join(qa,'recipe-checks.json'),JSON.stringify({passed:true,recipes:recipeResults,scope:'Actual native app, fresh isolated blank test projects. No user project or source artwork touched.'},null,2));
  await app.evaluate(({app})=>app.exit(0));nativeClosed=true;
  browser=await chromium.launch({channel:'chrome',headless:true});g=await browser.newPage({viewport:{width:1440,height:1000}});g.setDefaultTimeout(15000);await g.emulateMedia({reducedMotion:'reduce'});g.on('pageerror',e=>errors.push(e.message));await g.goto(require('url').pathToFileURL(guide).href);console.log('Offline guide loaded in isolated browser');
  await g.waitForFunction(()=>document.getElementById('lesson-code')?.textContent.includes('ds.setKeys'));
  await g.evaluate(()=>{for(const im of document.images)im.loading='eager';return Promise.all([...document.images].map(im=>im.decode()))});
  check('All31 chapters are present',await g.locator('.chapter').count()===31);
  check('All67 native tracks have dictionary entries',await g.locator('.parameter').count()===67);
  check('Every atlas image decoded',await g.evaluate(()=>[...document.images].every(n=>n.complete&&n.naturalWidth>0)));
  const links=await g.evaluate(()=>[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.hash.slice(1))).map(a=>a.hash));check('All internal chapter links resolve',!links.length);
  await g.fill('#guide-search','mouth');check('Symptom search finds the mouth override repair',await g.locator('#search-results').innerText().then(t=>t.includes('Changing the expression also changes the mouth')));
  await g.fill('#parameter-query','headYaw');check('Dictionary search isolates the exact control',await g.locator('.parameter:not([hidden])').count()===1);
  await g.fill('#parameter-query','');await g.selectOption('#parameter-group','Arms');check('Dictionary groups filter all8 arm controls',await g.locator('.parameter:not([hidden])').count()===8);await g.selectOption('#parameter-group','');
  await g.fill('#guide-search','');await g.locator('#head-workshop').scrollIntoViewIfNeeded();await g.evaluate(()=>{document.getElementById('lesson-angle').value=30;document.getElementById('lesson-angle').dispatchEvent(new Event('input'));document.getElementById('lesson-duration').value=2000;document.getElementById('lesson-duration').dispatchEvent(new Event('input'));document.getElementById('lesson-time').value=500;document.getElementById('lesson-time').dispatchEvent(new Event('input'))});
  check('Lesson changes its code, value and native picture',await g.evaluate(()=>document.getElementById('lesson-code').textContent.includes('t: 2000, v: 30')&&document.getElementById('workshop-state').textContent.includes('15.0 degrees')&&document.getElementById('workshop-bunny').naturalWidth>0));
  await g.click('#lesson-play');await g.waitForFunction(()=>+document.getElementById('lesson-time').value>550);await g.click('#lesson-play');check('Lesson playback runs and pauses',await g.locator('#lesson-play').innerText()==='Play example');
  await g.click('#lesson-reset');check('Lesson reset returns to the original example',await g.inputValue('#lesson-angle')==='20');
  await g.screenshot({path:path.join(qa,'interactive-workshop.png')});
  // Raster diagrams for the printable companion, using the existing Chromium renderer.
  for(const name of ['hierarchy','pipeline','timeline','caption-demo','safe-zone']){
   const svg=fs.readFileSync(path.join(assets,name+'.svg'),'utf8'),png=await g.evaluate(async text=>{const dims=text.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/),im=new Image();im.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(text);await im.decode();const c=document.createElement('canvas');c.width=1800;c.height=Math.round(1800*(+dims[2])/(+dims[1]));const ctx=c.getContext('2d');ctx.fillStyle='#E0A64B';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(im,0,0,c.width,c.height);return c.toDataURL('image/png').split(',')[1]},svg);fs.writeFileSync(path.join(assets,name+'.png'),Buffer.from(png,'base64'));
  }
  await g.evaluate(()=>window.scrollTo(0,0));await g.screenshot({path:path.join(qa,'guide-desktop.png')});
  await g.setViewportSize({width:430,height:900});
  await g.waitForFunction(()=>innerWidth<=430);check('Mobile guide has no horizontal document overflow',await g.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await g.click('#guide-menu');check('Mobile chapter menu opens',await g.locator('#guide-sidebar').isVisible());await g.click('#guide-sidebar a[href="#dictionary"]');check('Mobile chapter choice closes the menu',!await g.locator('#guide-sidebar').isVisible());
  await g.locator('#dictionary').scrollIntoViewIfNeeded();await g.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await g.screenshot({path:path.join(qa,'guide-mobile-dictionary.png')});
  await g.evaluate(()=>window.scrollTo(0,0));await g.screenshot({path:path.join(qa,'guide-mobile.png')});
  check('Guide has no network or live-project API calls',!fs.readFileSync(guide,'utf8').match(/\b(?:fetch\s*\(|XMLHttpRequest|new WebSocket|127\.0\.0\.1)/));
  check('No guide JavaScript errors',!errors.length);completed=true;
 }finally{fs.writeFileSync(path.join(qa,'guide-checks.json'),JSON.stringify({passed:completed&&checks.every(c=>c.passed),checks,errors,scope:'Native recipe checks plus offline guide in installed Chrome with an isolated headless profile: image loading, search/filter, lesson scrub/play/reset, desktop/mobile layout and no live-app networking.'},null,2));if(browser)await browser.close();if(!nativeClosed)await app.evaluate(({app})=>app.exit(0));}
})().catch(e=>{console.error(e);process.exitCode=1});
