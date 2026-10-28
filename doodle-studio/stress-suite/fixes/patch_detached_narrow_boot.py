"""Starting Doodle Studio in a narrow window threw "Cannot read properties of null (reading
'before')" at boot: the Canvas/Tools detach module looked for the docked Tools column, which only
exists in the wide layout. The module then never loaded, so Canvas/Tools could not be detached
even after widening the window. It now finds its dock homes when a panel is first detached.
Usage: python patch_detached_narrow_boot.py <src folder or built HTML>."""
import sys,os
A_OLD="""for(const id of ['canvas','tools']){hosts[id]=id==='canvas'?$('stage-wrap'):document.querySelector('.dock-tools');homes[id]=document.createComment(id+' dock home');hosts[id].before(homes[id]);}"""
A_NEW="""/*detached-narrow-boot*/function home(id){if(!homes[id]?.isConnected){const h=id==='canvas'?$('stage-wrap'):document.querySelector('.dock-tools');if(!h)return null;hosts[id]=h;homes[id]=document.createComment(id+' dock home');h.before(homes[id]);}return homes[id];}for(const id of ['canvas','tools'])home(id);"""
B_OLD="""if(!L.active)throw Error('Widen the Windows editor before detaching panels');"""
B_NEW="""if(!L.active)throw Error('Widen the Windows editor before detaching panels');if(!home(id))throw Error('Widen the Windows editor before detaching panels');"""
t=sys.argv[1];p=os.path.join(t,'detached-panels.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*detached-narrow-boot*/' in s:print('already patched');sys.exit()
# The build may route document.querySelector through DoodleSurfaces; accept either spelling.
for q in ["document.querySelector('.dock-tools')","DoodleSurfaces.querySelector('.dock-tools')"]:
  a=A_OLD.replace("document.querySelector('.dock-tools')",q)
  if s.count(a)==1:
    s=s.replace(a,A_NEW.replace("document.querySelector('.dock-tools')",q));break
else: raise SystemExit('anchor A not found')
assert s.count(B_OLD)==1,s.count(B_OLD);s=s.replace(B_OLD,B_NEW)
open(p,'w',encoding='utf-8').write(s);print('patched',p)
