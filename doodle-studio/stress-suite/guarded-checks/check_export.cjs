const { chromium } = require('./qa-home-guard.cjs')(require('C:/Users/Sushant/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const page=await browser.newPage({acceptDownloads:true});
 await page.goto(pathToFileURL(path.join(root,process.argv[2]||'index.source-rig.html')).href);
 if(await page.locator('#properties details').count())await page.locator('#properties summary').click();
 await page.locator('#text').fill('Native character export check.');
 await page.locator('#mkSubs').click();
 let download=page.waitForEvent('download');await page.locator('#exportSrt').click();
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
 if(meta.width!==1440||meta.height!==1080)throw Error('Wrong 4:3 export dimensions '+JSON.stringify(meta));
 await preview.locator('video').screenshot({path:path.join(root,'qa/exported-video-frame.png')});
 const result={subtitle:'passed',video:'passed',file:output,bytes:bytes.length,...meta,limits:['silent export tested; microphone and TTS audio not tested','1080p desktop Chrome; Android and 4K not tested']};
 fs.writeFileSync(path.join(root,'qa/source-art-export-check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
