// Verify visible branding in each real compiled runtime without editing a project.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const android=process.argv.includes('--android'),platform=android?'android':'windows',out=path.resolve('qa/app-name',platform);fs.mkdirSync(out,{recursive:true});
 const browser=android?await chromium.connectOverCDP('http://127.0.0.1:9225'):await chromium.launch({channel:'chrome',headless:true});
 const p=android?browser.contexts()[0].pages()[0]:await browser.newPage({viewport:{width:1440,height:1000}}),checks=[];
 const test=(name,passed,detail)=>{checks.push({name,passed:!!passed,detail});assert.ok(passed,name)};
 let menuWasOpen=false;
 try{
  if(!android){const h=JSON.parse(fs.readFileSync('qa/candidate-windows-process.json','utf8').replace(/^\uFEFF/,''));await p.goto('http://127.0.0.1:'+fs.readFileSync(path.join(h.dataDir,'ui-port.txt'),'utf8').trim());}
  await p.waitForFunction(()=>window.BunnyStudio);
  const before=await p.evaluate(()=>BunnyProject.bundle());
  test('Window title is Doodle Studio',await p.title()==='Doodle Studio',await p.title());
  test('Editor brand is Doodle Studio',await p.locator('.topbar h1').textContent()==='Doodle Studio');
  test('Native character remains Bunny',await p.locator('#stage').getAttribute('aria-label')==='Bunny character');
  const originalMenu=await p.evaluate(()=>({open:BunnyStudio.menu.open,page:BunnyStudio.menu.dataset.page}));menuWasOpen=originalMenu.open;
  await p.evaluate(()=>BunnyStudio.openMenu('home'));
  test('Main menu names the program Doodle Studio',await p.locator('#menu-context').textContent()==='Doodle Studio'&&await p.locator('#menu-heading').textContent()==='All tools');
  await p.screenshot({path:path.join(out,'menu.png')});
  await p.evaluate(()=>BunnyStudio.menu.close());
  await p.screenshot({path:path.join(out,'editor.png')});
  test('Original native-derived icon retained',await p.evaluate(async()=>await(await fetch(document.querySelector('link[rel=icon]').href)).text())===fs.readFileSync('art/icons/bunny-icon.svg','utf8'));
  test('Branding inspection leaves the project byte-identical',JSON.stringify(await p.evaluate(()=>BunnyProject.bundle()))===JSON.stringify(before));
  if(menuWasOpen)await p.evaluate(page=>BunnyStudio.openMenu(page||'home'),originalMenu.page);
 }finally{
  fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({checks,errors:[],testedBuild:JSON.parse(fs.readFileSync('qa/candidate-native-build.json','utf8')).artifacts[android?'apk':'exe']},null,2));
  if(!android)await browser.close();
 }
 console.log(JSON.stringify({platform,checks:checks.length,passed:true}));if(android)process.exit();
})().catch(e=>{console.error(e);process.exit(1)});
