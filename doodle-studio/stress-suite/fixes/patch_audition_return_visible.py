"""Auditioning a motion take showed no way back: "Return to current take" lived at the top of the
Animate pane's old main area, which the new Animate layout hides. The button now moves into the
timeline's Play group whenever an audition starts, sized like its neighbours (the build may rewrite
window.addEventListener, so only the handler is matched). Usage: python patch_audition_return_visible.py <src folder or built HTML>."""
import sys,os
OLD="""'bunny-audition',()=>stop.hidden=!audition)"""
NEW="""'bunny-audition',()=>{/*audition-return-visible*/const host=document.getElementById('timeline-playback');if(host&&stop.parentElement!==host){host.append(stop);stop.style.width='auto';}stop.hidden=!audition;})"""
t=sys.argv[1];p=os.path.join(t,'performance.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*audition-return-visible*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
