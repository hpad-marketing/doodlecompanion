// Bunny's brain. Your chats with him fill a memory bank on this PC; the memories shape his personality traits and the
// thoughts he holds up on his board. Optionally a small open-source chat model (Qwen2.5 1.5B Instruct, Apache-2.0) runs
// here through node-llama-cpp, so he can really talk. The model is a one-time 1.1 GB download; nothing else leaves the PC.
const fs=require('fs'),path=require('path'),os=require('os');
const MODEL_FILE='qwen2.5-1.5b-instruct-q4_k_m.gguf',MODEL_SIZE=1117320736,
  MODEL_URL='https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/'+MODEL_FILE;
// traits grow from what the memories talk about; each memory counts less as it ages (half-life two weeks)
const TRAITS={
  foodie:/\b(food|eat|ate|snack|burger|pizza|donut|lunch|dinner|breakfast|coffee|chai|tea|cook|biryani|sweet|hungry|salad|apple)\w*/i,
  playful:/\b(game|play|fetch|fun|joke|laugh|silly|prank|lol|haha)\w*/i,
  artsy:/\b(draw|doodle|design|art|paint|animat|illustrat|sketch|colou?r|canva|figma|affinity|cavalry)\w*/i,
  cinephile:/\b(movie|film|watch|series|show|anime|cartoon|netflix|youtube|episode|trailer)\w*/i,
  musical:/\b(music|song|guitar|sing|band|playlist|album|concert|beat)\w*/i,
  curious:/\b(why|how come|learn|science|book|read|history|space|idea|wonder|fact)\w*/i,
  cozy:/\b(sleep|nap|tired|bed|blanket|rest|cosy|cozy|weekend|relax)\w*/i,
  sporty:/\b(run|gym|walk|cricket|football|sport|yoga|swim|cycle|workout|steps)\w*/i,
  hardworking:/\b(work|deadline|client|meeting|project|office|email|launch|campaign|boss)\w*/i,
  affectionate:/\b(love|hug|miss|friend|cute|sweet|thank|best buddy|proud)\w*/i};
const now=()=>Date.now(),norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').split(/\s+/).filter(w=>w.length>2);
function similar(a,b){const A=new Set(norm(a)),B=new Set(norm(b));if(!A.size||!B.size)return 0;let n=0;for(const w of A)if(B.has(w))n++;return n/Math.min(A.size,B.size);}
// the same rules work without the model, so the bank grows from day one
const RULES=[
  [/\b(?:i (?:really )?(?:like|love|enjoy|adore))\s+(.{2,60})/i,m=>`You love ${m[1]}`],
  [/\b(?:i (?:hate|dislike|can't stand|don't like))\s+(.{2,60})/i,m=>`You don't like ${m[1]}`],
  [/\bmy (favou?rite \w+) is\s+(.{2,50})/i,m=>`Your ${m[1]} is ${m[2]}`],
  [/\bi (?:work|am working) (?:as|at|on)\s+(.{2,60})/i,m=>`You work ${m[0].match(/as|at|on/i)[0]} ${m[1]}`],
  [/\bi(?:'m| am) from\s+(.{2,40})/i,m=>`You're from ${m[1]}`],
  [/\bmy (\w+(?: \w+)?) is (?:called|named)\s+(.{2,40})/i,m=>`Your ${m[1]} is called ${m[2]}`],
  [/\b(?:today|tomorrow|this week) i(?:'m| am| will| have)\s+(.{3,60})/i,m=>`You said: ${m[0]}`],
  [/\byou(?:'re| are) (?:my )?(.{2,30})/i,m=>`You called him ${m[1]}`]];
module.exports=function brain(app,{log,toPet,net}){
  const dir=path.join(app.getPath('userData'),'brain'),modelPath=process.env.BUNNY_BRAIN_MODEL||path.join(dir,MODEL_FILE),memPath=path.join(dir,'memory.json');
  fs.mkdirSync(dir,{recursive:true});
  let mem={facts:[],events:[],chats:0};try{mem={...mem,...JSON.parse(fs.readFileSync(memPath,'utf8'))};}catch{}
  let saveT=0;const save=()=>{clearTimeout(saveT);saveT=setTimeout(()=>{try{fs.writeFileSync(memPath,JSON.stringify(mem));}catch(e){log('memory save: '+e.message);}},800);};
  const sane=t=>{const l=(t.match(/[A-Za-z]/g)||[]).length;return l>=4&&l/t.length>0.6&&!/[\u0000-\u0008\u000e-\u001f\ufffd]/.test(t);};
  function remember(text,kind='chat'){text=String(text||'').replace(/\s+/g,' ').trim().replace(/[.!?]+$/,'');if(text.length<6||text.length>140||!sane(text))return false;
    const same=mem.facts.find(f=>similar(f.text,text)>=0.7);if(same){same.t=now();same.hits=(same.hits||1)+1;if(text.length>same.text.length)same.text=text;save();return false;}
    mem.facts.push({text,kind,t:now(),hits:1});
    if(mem.facts.length>240){mem.facts.sort((a,b)=>(b.hits||1)*b.t-(a.hits||1)*a.t);mem.facts.length=200;}
    save();return true;}
  function event(text){mem.events.push({text:String(text).slice(0,120),t:now()});if(mem.events.length>300)mem.events.splice(0,mem.events.length-300);save();}
  function traits(){const sc={};for(const k of Object.keys(TRAITS))sc[k]=0;
    const add=(text,t,w)=>{const age=(now()-t)/864e5,f=w*Math.pow(0.5,age/14);for(const [k,re] of Object.entries(TRAITS))if(re.test(text))sc[k]+=f;};
    for(const f of mem.facts)add(f.text,f.t,f.kind==='chat'?1.5:1);for(const e of mem.events)add(e.text,e.t,0.35);
    sc.affectionate+=Math.min(3,mem.chats/40);
    const out={};for(const [k,v] of Object.entries(sc))out[k]=Math.round(100*(1-Math.exp(-v/4)));return out;}
  const topTraits=n=>Object.entries(traits()).filter(([,v])=>v>=15).sort((a,b)=>b[1]-a[1]).slice(0,n);
  // ---- the model ----
  let llamaMod=null,llama=null,model=null,ctx=null,queue=Promise.resolve(),idleT=0,dl=null;
  const ready=()=>fs.existsSync(modelPath)&&(fs.statSync(modelPath).size===MODEL_SIZE||!!process.env.BUNNY_BRAIN_MODEL);
  async function load(){if(model)return true;if(!ready())return false;
    llamaMod=llamaMod||await import('node-llama-cpp');llama=llama||await llamaMod.getLlama({gpu:false,build:'never'});
    model=await llama.loadModel({modelPath});ctx=await model.createContext({contextSize:2048,threads:Math.max(2,Math.floor(os.cpus().length/2))});log('brain: model loaded');return true;}
  function idle(){clearTimeout(idleT);idleT=setTimeout(async()=>{try{await ctx?.dispose();await model?.dispose();}catch{}ctx=model=null;log('brain: model unloaded (idle)');},20*60000);}
  function run(fn){const p=queue.then(fn,fn);queue=p.catch(()=>{});return p;}
  async function gen(system,history,prompt,maxTokens,temperature=0.8){if(!await load())return null;idle();
    const seq=ctx.getSequence(),s=new llamaMod.LlamaChatSession({contextSequence:seq,systemPrompt:system});
    try{if(history.length)s.setChatHistory([{type:'system',text:system},...history.map(h=>h.me?{type:'user',text:h.t}:{type:'model',response:[h.t]})]);
      return (await s.prompt(prompt,{maxTokens,temperature,topP:0.9})).trim();}
    finally{s.dispose();seq.dispose();}}
  function persona(c){const tr=topTraits(3).map(([k])=>k).join(', ')||'still finding himself';
    const facts=[...mem.facts].sort((a,b)=>b.t-a.t).slice(0,18).map(f=>'- '+f.text).join('\n')||'- (nothing yet)';
    return `You are Bunny, a tiny hand-drawn doodle bunny who lives on ${c.name||'your friend'}'s desktop as a desk pet. `+
      `You are warm, cheeky and curious, and you speak in short, playful sentences (one to three, under 45 words). Never use emoji or markdown. `+
      `Your personality traits so far: ${tr}. Your mood right now: ${c.mood||'okay'}. It is ${c.time||''}; your friend is ${c.doing||'working'}.\n`+
      `Things you remember about your friend and your time together:\n${facts}\n`+
      `Use these memories naturally when they fit. If you don't know something, say so playfully; never invent facts about your friend.`;}
  async function chat(q,c){mem.chats++;save();
    for(const [re,fn] of RULES){const m=q.match(re);if(m)remember(fn(m).replace(/[.!?,;].*$/,''));}
    if(!ready())return {text:null};
    return run(async()=>{const hist=(c.history||[]).slice(-6);
      const a=await gen(persona(c),hist,q,90);if(!a||!sane(a))return {text:null};
      // a second, quick pass decides what (if anything) from this exchange is worth keeping
      const m=await gen('You extract memories for a desk pet. Output at most two short lines, each a fact about the user or about the user and the pet, written as "You ..." (under 14 words). Only lasting facts: likes, plans, people, work, feelings. If nothing is worth keeping, output NONE.',[],`User said: "${q}"\nPet replied: "${a}"`,48,0.2);
      if(m&&!/^none/i.test(m))for(const line of m.split('\n').map(l=>l.replace(/^[-*\d.\s]+/,'').trim()).filter(Boolean).slice(0,2))remember(line);
      return {text:a};});}
  // a thought for his board: built from a memory and his strongest trait, one short line
  async function thought(c){if(!mem.facts.length)return null;
    const rec=[...mem.facts].sort((x,y)=>y.t-x.t).slice(0,12),f=rec[Math.floor(Math.random()*rec.length)];
    if(ready()&&Math.random()<.8){try{const t=await run(()=>gen(persona(c),[],`Write one thought you'd scribble on your little board, inspired by this memory: "${f.text}". Under 10 words. No quotes.`,24,0.9));if(t&&sane(t))return t.replace(/^["']|["']$/g,'').split('\n')[0].slice(0,80);}catch(e){log('brain thought: '+e.message);}}
    return f.text.replace(/^You /,'You ').slice(0,70);}
  // ---- download, with resume; progress goes to the ring above his head ----
  async function download(){if(ready())return true;if(dl)return dl;
    dl=(async()=>{const part=modelPath+'.part';let have=fs.existsSync(part)?fs.statSync(part).size:0;
      const res=await net.fetch(MODEL_URL,{headers:have?{Range:`bytes=${have}-`}:{}});
      if(!(res.status===200||res.status===206))throw new Error('HTTP '+res.status);if(res.status===200)have=0;
      const out=fs.createWriteStream(part,{flags:have?'a':'w'}),reader=res.body.getReader();let got=have,last=0;
      while(true){const {done,value}=await reader.read();if(done)break;got+=value.length;if(!out.write(Buffer.from(value)))await new Promise(r=>out.once('drain',r));
        if(now()-last>400){last=now();toPet('brain-progress',{done:got,total:MODEL_SIZE});}}
      await new Promise(r=>out.end(r));if(fs.statSync(part).size!==MODEL_SIZE)throw new Error('size mismatch');fs.renameSync(part,modelPath);toPet('brain-progress',null);log('brain: model downloaded');return true;})()
      .catch(e=>{log('brain download: '+e.message);toPet('brain-progress',null);return false;}).finally(()=>{dl=null;});
    return dl;}
  return {chat,thought,remember,event,download,ready,downloading:()=>!!dl,
    state:()=>({ready:ready(),downloading:!!dl,facts:mem.facts.length,chats:mem.chats,traits:topTraits(5),recent:[...mem.facts].sort((a,b)=>b.t-a.t).slice(0,8).map(f=>f.text)}),
    forget:i=>{const r=[...mem.facts].sort((a,b)=>b.t-a.t)[i];if(r){mem.facts.splice(mem.facts.indexOf(r),1);save();}}};
};
