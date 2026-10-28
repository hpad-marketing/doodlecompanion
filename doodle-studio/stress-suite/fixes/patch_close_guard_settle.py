"""A fresh or new blank project counted as unsaved: modules that load after the close
guard (lighting, guides, motion smoothing) fill in default fields after the guard took
its baseline. Each project's baseline now follows those defaults until the first real
user input, or 1.5 s after the page has loaded, whichever comes first. Usage:
python patch_close_guard_settle.py path/to/close-guard.js (or the built HTML)."""
import sys
MARK='/*settle-baseline*/'
p=sys.argv[1];s=open(p,encoding='utf-8').read()
if MARK in s:print('already patched');sys.exit()
old="function state(){W.ensure();const id=proj.projectID;if(!states.has(id))states.set(id,{id,baseline:signature(),forced:flags[id]===true,dirty:flags[id]===true});return states.get(id);}"
new=MARK+"let lastInput=0;const settleMs=1500;for(const type of ['pointerdown','keydown','input','drop'])document.addEventListener(type,event=>{if(event.isTrusted)lastInput=performance.now();},true);const loaded=()=>document.readyState==='complete'?Promise.resolve():new Promise(r=>window.addEventListener('load',r,{once:true}));"\
"function settleState(item){loaded().then(()=>setTimeout(()=>{item.settleUntil=0;queue();},settleMs));}"\
"function state(){W.ensure();const id=proj.projectID;if(!states.has(id)){const item={id,baseline:signature(),forced:flags[id]===true,dirty:flags[id]===true,created:performance.now(),settleUntil:1};states.set(id,item);settleState(item);}const item=states.get(id);if(item.settleUntil&&!item.forced&&lastInput<=item.created)item.baseline=signature();else item.settleUntil=0;return item;}"
assert s.count(old)==1,'state() not found';s=s.replace(old,new)
open(p,'w',encoding='utf-8').write(s);print('patched',p)
