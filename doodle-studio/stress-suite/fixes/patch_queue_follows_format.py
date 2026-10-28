"""Export's format choice stayed on 9:16 after switching the canvas to 16:9: the default was only
refreshed by a menu hook the contextual Export page no longer calls. The queue now follows the canvas
format whenever the project changes, until you pick a format yourself.
Usage: python patch_queue_follows_format.py <src folder or built HTML>."""
import sys,os
OLD="Studio.register('menu:export',()=>{if(ratioUntouched){$('queue-portrait').checked=Camera.name()!=='landscape';$('queue-landscape').checked=Camera.name()==='landscape';}"
NEW=("/*queue-follows-format*/const syncRatio=()=>{if(ratioUntouched){$('queue-portrait').checked=Camera.name()!=='landscape';$('queue-landscape').checked=Camera.name()==='landscape';}};"
"window.addEventListener('bunny-model',syncRatio);window.addEventListener('bunny-workspace',syncRatio);document.getElementById('canvas-format-select')?.addEventListener('change',()=>setTimeout(syncRatio));"
"Studio.register('menu:export',()=>{syncRatio();")
t=sys.argv[1];p=os.path.join(t,'export-queue.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*queue-follows-format*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
