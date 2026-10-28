// Approved emulator only. Never calls browser.close(): CDP close destroys WebView.
const fs=require('fs'),path=require('path');
const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{
 const origin=fs.readFileSync(path.join(root,'qa/windows-host.log'),'utf8').trim();
 const info=await(await fetch(origin+'/api/info')).json();
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9223');const page=browser.contexts()[0].pages()[0];
 page.setDefaultTimeout(25000);await page.waitForFunction(()=>window.BunnyProject&&window.BunnyRig);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const result=await page.evaluate(async info=>{
  document.querySelector('#sync-address').value='http://10.0.2.2:'+info.port;document.querySelector('#sync-pin').value=info.pin;
  const original=await BunnyProject.bundle();const current=await BunnyProject.syncRequest({action:'pull',pin:info.pin});
  original.project.cues=[{uid:'android-sync-cue',start:0,end:1300,text:'Bunny emulator to PC'}];
  original.project.clips=[];for(const id in original.project.keys)if(id!=='mouth')original.project.keys[id]=[];
  const pushed=await BunnyProject.syncRequest({action:'push',pin:info.pin,revision:current.revision,bundle:original});
  const pulled=await BunnyProject.syncRequest({action:'pull',pin:info.pin});
  await BunnyProject.accept(pulled.bundle);
  return {secure:isSecureContext,origin:location.origin,native:!!window.BunnyAndroid,wifiPush:pushed.saved,wifiPull:pulled.bundle.project.cues[0].text==='Bunny emulator to PC',audio:!!pulled.bundle.audio,revision:pulled.revision,bluetooth:info.bluetooth};
 },info);
 result.errors=errors;fs.writeFileSync(path.join(root,'qa/android-sync.json'),JSON.stringify(result,null,2));console.log(result);
 // Export and wait for the human-equivalent native chooser action in a separate adb call.
 await page.locator('#properties details').first().evaluate(n=>n.open=true);
 await page.locator('#include-audio').uncheck();await page.locator('#export').click();
 console.log('Export running; choose SAVE in Android DocumentsUI.');
 await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Saved talking-bunny-1080.mp4')||document.querySelector('#status').textContent.startsWith('Export failed'),{},{timeout:180000});
 fs.writeFileSync(path.join(root,'qa/android-export-status.txt'),await page.locator('#status').textContent());console.log(await page.locator('#status').textContent());process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
