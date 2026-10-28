const { chromium } = require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const page=await browser.newPage({acceptDownloads:true});
 await page.goto(pathToFileURL(path.join(root,process.argv[2]||'index.source-rig.html')).href);
 /*the UX pass moved script text into the Voice workspace and export into the Export menu*/const reveal=async(ids,fn)=>{if(await page.evaluate(()=>!!window.BunnyStudio))await page.evaluate(fn);await page.evaluate(ids=>{for(const id of ids){let n=document.getElementById(id);while(n){if(n.tagName==='DETAILS')n.open=true;n=n.parentElement;}}},ids);};
 await page.evaluate(()=>{const h=document.getElementById('studio-home');if(h?.open)h.close();});
 await reveal(['text','mkSubs'],()=>{BunnyStudio.setWorkspace('voice');window.DoodleContextual?.show('voice','voice-extra-tools',{manual:true});});
 await page.locator('#text').fill('Native character export check.');
 await page.locator('#mkSubs').click();
 await reveal(['exportSrt','res','export'],()=>BunnyStudio.openMenu('export'));let download=page.waitForEvent('download');await page.locator('#exportSrt').click();
 const srt=await download;const srtPath=path.join(root,'qa/source-art-export.srt');await srt.saveAs(srtPath);
 if(!fs.readFileSync(srtPath,'utf8').includes('Native character'))throw Error('Subtitle content missing');
 await page.locator('#res').selectOption('1080');
 download=page.waitForEvent('download',{timeout:45000});await page.locator('#export').click();
 const video=await download;const output=path.join(root,'qa',video.suggestedFilename());await video.saveAs(output);
 if(fs.statSync(output).size<1000)throw Error('Empty video');
 const preview=await browser.newPage();await preview.setContent('<video controls id="preview"></video>');
 // Re-encode as a data URL to inspect the actual exported bytes locally.
 const bytes=fs.readFileSync(output);const mime=output.endsWith('.mp4')?'video/mp4':'video/webm';
 await preview.locator('video').evaluate((v,src)=>{v.src=src;},`data:${mime};base64,${bytes.toString('base64')}`);
 await preview.waitForFunction(()=>document.querySelector('video').readyState>=2);
 const meta=await preview.locator('video').evaluate(v=>({width:v.videoWidth,height:v.videoHeight,duration:v.duration}));
 if(Math.min(meta.width,meta.height)!==1080)throw Error('Wrong 1080p export dimensions '+JSON.stringify(meta));/*legacy source-rig exports 1440x1080, Doodle Studio exports the canvas format*/
 await preview.locator('video').screenshot({path:path.join(root,'qa/exported-video-frame.png')});
 const result={subtitle:'passed',video:'passed',file:output,bytes:bytes.length,...meta,limits:['silent export tested; microphone and TTS audio not tested','1080p desktop Chrome; Android and 4K not tested']};
 fs.writeFileSync(path.join(root,'qa/source-art-export-check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
