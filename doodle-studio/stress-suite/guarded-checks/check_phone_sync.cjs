// Approved physical Bunny testing. Connect only to that app's debug WebView.
const fs=require('fs');const {chromium}=require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const origin=fs.readFileSync('qa/windows-host.log','utf8').trim();await fetch(origin+'/api/sync/enable',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const info=await(await fetch(origin+'/api/info')).json();
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9224'),p=browser.contexts()[0].pages()[0];await p.waitForFunction(()=>window.BunnyProject);
 p.on('console',msg=>{if(msg.text().startsWith('BT QA'))console.log(msg.text())});
 const result=await p.evaluate(async info=>{
  document.querySelector('#sync-pin').value=info.pin;document.querySelector('#sync-address').value='http://127.0.0.1:1';
  // Populate names from actual bonded devices, then target only this computer.
  const id=crypto.randomUUID();const peers=await new Promise((resolve,reject)=>{const handler=e=>{if(e.detail.id!==id)return;if(e.detail.type==='bluetooth-peers'){window.removeEventListener('bunny-native',handler);resolve(JSON.parse(e.detail.value))}else if(e.detail.type==='bluetooth-error'){window.removeEventListener('bunny-native',handler);reject(Error(e.detail.value))}};window.addEventListener('bunny-native',handler);BunnyAndroid.bluetoothPeers(id)});
  const pc=peers.find(peer=>peer.name?.toUpperCase()==='SUSHI');if(!pc)throw Error('Pair this phone with SUSHI first');const select=document.querySelector('#sync-bluetooth');select.innerHTML='';select.add(new Option(pc.name,pc.address));select.value=pc.address;
  const events=[],progress=[],listener=e=>{events.push(e.detail.type);if(e.detail.type==='bluetooth-progress'){progress.push(e.detail.value);console.log('BT QA '+e.detail.value)}};window.addEventListener('bunny-native',listener);
  const started=performance.now(),current=await BunnyProject.syncRequest({action:'pull',pin:info.pin});console.log('BT QA initial pull complete');
  const bundle=await BunnyProject.bundle();if(!bundle.audio)throw Error('Physical microphone take missing');bundle.project.cues=[{uid:'physical-bt-cue',start:0,end:1500,text:'Bunny real phone Bluetooth test'}];
  const sent=await BunnyProject.syncRequest({action:'push',pin:info.pin,revision:current.revision,bundle});if(!sent.saved)throw Error('Bluetooth project not saved');console.log('BT QA project/audio push complete');
  const received=await BunnyProject.syncRequest({action:'pull',pin:info.pin});window.removeEventListener('bunny-native',listener);
  return {sent:sent.saved,received:received.bundle.project.cues[0].text==='Bunny real phone Bluetooth test',audioMatched:received.bundle.audio===bundle.audio,audioBytes:bundle.audio.length,events:events.filter(e=>e!=='bluetooth-progress'),progressEvents:progress.length,ms:performance.now()-started,revision:received.revision};
 },info);
 console.log(result);fs.writeFileSync('qa/phone-bluetooth.json',JSON.stringify(result,null,2));if(!result.sent||!result.received||!result.audioMatched)throw Error('Bluetooth round-trip mismatch');process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
