const B=window.bunny,$=id=>document.getElementById(id);
const bools=['onTop','routine','chatty','water','stretch','eyes','sleepAway','nightSleep','toasts','startup'],nums=['waterMin','waterGoal','stretchMin','eyesMin','breakMin','bw'];
let S;
const SCHED=[['wake','Wakes up'],['coffee','Coffee and the news'],['office','Office'],['lunch','Lunch dance, then a burger'],['tea','Tea time'],['pack','Packs his bag, reads back your notes'],['evening','Cozy evening'],['bed','Bed']];
const USUAL={wake:'07:00',coffee:'08:30',office:'09:30',lunch:'13:30',tea:'15:30',pack:'18:30',evening:'19:15',bed:'23:00'};
function sched(){const box=$('sched');box.innerHTML='';for(const [k,l] of SCHED){const lab=document.createElement('label');const t=document.createElement('input');t.type='time';t.id='at_'+k;t.value=(S.schedule||USUAL)[k]||USUAL[k];lab.append(t,' '+l);box.append(lab);}}
function list(){const ul=$('rList');ul.innerHTML='';for(const r of (S.custom||[]).slice().sort((a,b)=>a.at-b.at)){const li=document.createElement('li');li.textContent=`${new Date(r.at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}  ${r.text}`;ul.append(li);}}
async function load(){S=await B.invoke('get-settings');for(const k of bools)$(k).checked=!!S[k];for(const k of nums)$(k).value=S[k];$('bwv').textContent=S.bw+' px';list();sched();}
$('bw').oninput=()=>$('bwv').textContent=$('bw').value+' px';
$('save').onclick=()=>{const p={};for(const k of bools)p[k]=$(k).checked;for(const k of nums)p[k]=Math.max(1,+$(k).value||1);p.schedule={};for(const [k] of SCHED)p.schedule[k]=$('at_'+k).value||USUAL[k];B.send('set-settings',p);$('saved').style.opacity=1;setTimeout(()=>$('saved').style.opacity=0,1500);};
$('schedReset').onclick=()=>{S.schedule={...USUAL};sched();};
$('rAdd').onclick=async()=>{const text=$('rText').value.trim();if(!text){$('rText').focus();return;}B.send('add-reminder',{text,minutes:+$('rMin').value});$('rText').value='';setTimeout(load,200);};
function jump(s){if(s){$(s)?.scrollIntoView();if(s==='remind')$('rText').focus();}}
B.on('section',jump);load().then(()=>jump(location.hash.slice(1)));
