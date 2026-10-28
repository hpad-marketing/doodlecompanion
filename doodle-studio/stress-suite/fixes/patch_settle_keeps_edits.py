"""Follow-up to patch_close_guard_settle (fix 6). During the first 1.5 s the close guard's baseline
followed every change, so an assistant/MCP edit that landed before the first click or key was
absorbed and the window could close without the save reminder. Two changes:
1. The baseline now follows only defaults that modules fill in: new fields (at any depth) that hold
   no list items, such as empty key tracks or guides.scaleFrom. Any changed value or added list item
   ends the settle window and counts as unsaved work.
2. When the settle window ends, the baseline catches up one last time (defaults only), so a default
   filled in without a model event no longer marks a fresh project unsaved.
Usage: python patch_settle_keeps_edits.py <src folder or built HTML>."""
import sys,os
MARK='/*settle-keeps-edits*/'
OLD="if(item.settleUntil&&!item.forced&&lastInput<=item.created)item.baseline=signature();else item.settleUntil=0;return item;}"
NEW=MARK+"if(item.settleUntil&&settleFollows(item))item.baseline=signature();else item.settleUntil=0;return item;}"
OLD2="setTimeout(()=>{item.settleUntil=0;queue();},settleMs)"
NEW2="setTimeout(()=>{if(item.settleUntil&&proj.projectID===item.id&&settleFollows(item))item.baseline=signature();item.settleUntil=0;queue();},settleMs)"
HELPER=("function blankDefault(v){return Array.isArray(v)?v.length===0:v&&typeof v==='object'?Object.values(v).every(blankDefault):true;}"
 "function onlyDefaults(a,b){if(Array.isArray(a))return Array.isArray(b)&&a.length===b.length&&a.every((v,i)=>onlyDefaults(v,b[i]));"
 "if(a&&typeof a==='object'){if(!b||typeof b!=='object'||Array.isArray(b))return false;for(const k in a)if(k!=='updatedAt'&&!(k in b&&onlyDefaults(a[k],b[k])))return false;for(const k in b)if(!(k in a)&&!blankDefault(b[k]))return false;return true;}return a===b;}"
 "function settleFollows(item){if(item.forced||lastInput>item.created)return false;let now;try{now=JSON.parse(JSON.stringify(proj));}catch{return false;}if(item.fields&&!onlyDefaults(item.fields,now))return false;item.fields=now;return true;}")
t=sys.argv[1];p=os.path.join(t,'close-guard.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if MARK in s:print('already patched');sys.exit()
assert '/*settle-baseline*/' in s,'apply patch_close_guard_settle first'
assert s.count(OLD)==1 and s.count(OLD2)==1,(s.count(OLD),s.count(OLD2))
s=s.replace(OLD,NEW).replace(OLD2,NEW2).replace('/*settle-baseline*/','/*settle-baseline*/'+HELPER,1)
open(p,'w',encoding='utf-8').write(s);print('patched',p)
