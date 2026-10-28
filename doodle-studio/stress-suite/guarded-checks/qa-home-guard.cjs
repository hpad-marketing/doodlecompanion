// Doodle Studio opens Home on startup. Checks written before Home existed expect the editor,
// so this closes only that first automatic Home once per page; Home opened later stays open.
// Set QA_KEEP_HOME=1 to turn it off.
const script=`(()=>{if(window.__qaHomeGuard)return;window.__qaHomeGuard=1;let done=false;const close=()=>{const h=document.getElementById('studio-home');if(done||!h||!h.open)return false;done=true;try{h.close()}catch{}return true};
const watch=()=>{if(close())return;const mo=new MutationObserver(()=>{if(close())mo.disconnect()});mo.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['open']});setTimeout(()=>mo.disconnect(),30000)};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',watch);else watch();})()`;
const closeNow=page=>page.evaluate(()=>{const h=document.getElementById('studio-home');if(h&&h.open)h.close()}).catch(()=>{});
async function wrapContext(ctx){await ctx.addInitScript(script).catch(()=>{});for(const p of ctx.pages())await closeNow(p);return ctx}
function wrapBrowser(b){const newContext=b.newContext.bind(b);b.newContext=async(...a)=>wrapContext(await newContext(...a));
 const newPage=b.newPage.bind(b);b.newPage=async(...a)=>{const p=await newPage(...a);await p.context().addInitScript(script).catch(()=>{});return p};return b}
const wrapType=bt=>new Proxy(bt,{get(o,k){const v=o[k];
 if(k==='launch')return async(...a)=>wrapBrowser(await o.launch(...a));
 if(k==='launchPersistentContext')return async(...a)=>wrapContext(await o.launchPersistentContext(...a));
 if(k==='connectOverCDP')return async(...a)=>{const b=wrapBrowser(await o.connectOverCDP(...a));for(const c of b.contexts())await wrapContext(c);return b};
 return typeof v==='function'?v.bind(o):v;}});
const wrapElectron=el=>new Proxy(el,{get(o,k){const v=o[k];if(k==='launch')return async(...a)=>{const app=await o.launch(...a);await wrapContext(app.context());app.on('window',p=>p.waitForLoadState('domcontentloaded').then(()=>closeNow(p)).catch(()=>{}));return app};return typeof v==='function'?v.bind(o):v;}});
module.exports=function guard(pw){if(process.env.QA_KEEP_HOME)return pw;const out={...pw};
 for(const t of ['chromium','firefox','webkit'])if(pw[t])out[t]=wrapType(pw[t]);
 if(pw._electron)out._electron=wrapElectron(pw._electron);
 return out};
