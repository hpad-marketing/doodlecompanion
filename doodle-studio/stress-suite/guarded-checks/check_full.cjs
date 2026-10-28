// Isolated code test server/browser. Never attaches to the user's preview/session.
const fs=require('fs'),http=require('http'),path=require('path');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{
 const html=fs.readFileSync(path.join(root,'index.html'));const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(html)});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+path.join(root,'qa/speech-fixture.wav')]});
 const context=await browser.newContext({permissions:['microphone'],viewport:{width:1440,height:1100},acceptDownloads:true});const page=await context.newPage();const errors=[],checks=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR:',e.message)});
 const check=(name,value)=>{checks.push({name,passed:!!value});if(!value)throw Error(name)};
 try{
  await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>window.BunnyRig&&document.querySelector('#projected-rig path'));
  check('native projected rig renders',await page.locator('#projected-rig path').count()>10);
  await page.screenshot({path:path.join(root,'qa/full-front.png'),fullPage:true});
  await page.locator('[data-part-select="figure"]').click();await page.locator('[data-context-track="turn"]').fill('90');await page.locator('[data-context-track="turn"]').dispatchEvent('input');
  const side=await page.locator('#projected-rig').innerHTML();await page.screenshot({path:path.join(root,'qa/full-side.png'),fullPage:true});
  await page.locator('[data-context-track="turn"]').fill('180');await page.locator('[data-context-track="turn"]').dispatchEvent('input');check('back differs from side',side!==await page.locator('#projected-rig').innerHTML());
  await page.locator('[data-context-track="turn"]').fill('0');await page.locator('[data-context-track="turn"]').dispatchEvent('input');await page.locator('[data-context-track="view"]').fill('-70');await page.locator('[data-context-track="view"]').dispatchEvent('input');await page.screenshot({path:path.join(root,'qa/full-below.png'),fullPage:true});
  check('below view has finite geometry',!(/NaN|Infinity/.test(await page.locator('#projected-rig').innerHTML())));
  await page.locator('#context-reset').click();await page.locator('[data-part-select="armL"]').click();await page.locator('[data-context-track="elbowL"]').fill('100');await page.locator('[data-context-track="elbowL"]').dispatchEvent('input');
  check('elbow articulation changes native forearm matrix',await page.evaluate(()=>Math.abs(BunnyRig.pose(0).mats['FOREARM.L'][0]-1)>.1));
  await page.locator('#context-reset').click();
  await page.locator('#rec').click();await page.waitForFunction(()=>document.querySelector('#rec').textContent==='Stop');
  await page.waitForFunction(()=>document.querySelector('#clock').textContent.includes('2.'));await page.locator('#rec').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Voice and lip-sync keys saved'));
  const bundle=await page.evaluate(()=>BunnyProject.bundle());check('recording embeds audio',!!bundle.audio&&bundle.project.audio.ms>1000);check('recording creates editable mouth keys',bundle.project.keys.mouth.length>1);
  await page.reload();await page.waitForFunction(()=>window.BunnyProject);await page.waitForFunction(async()=>!!(await BunnyProject.bundle()).audio);check('voice survives reload',true);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(root,'qa/full-phone.png'),fullPage:true});
  check('48px phone transport',await page.locator('#rec').evaluate(n=>n.getBoundingClientRect().height>=48));check('no horizontal phone overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  check('no script errors',errors.length===0);
 }finally{fs.writeFileSync(path.join(root,'qa/full-software-checks.json'),JSON.stringify({checks,errors,limits:['Synthetic microphone fixture, not hardware audio','No Android installation or Kamvas/Bluetooth peer acceptance']},null,2));await browser.close();server.close()}
 console.log(JSON.stringify(checks));
})().catch(e=>{console.error(e);process.exit(1)});
