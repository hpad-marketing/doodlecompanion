"""Loop preview's Stop button was invisible after the UX pass: it lived at the top of the Animate
pane's old main area, which the new Animate layout hides, so a looping preview could only be
stopped with Play. The button now moves into the timeline's Play group whenever a loop preview
starts (the build may rewrite window.addEventListener, so only the handler is matched). Usage: python patch_loop_stop_visible.py <src folder or built HTML>."""
import sys,os
OLD="""'bunny-loop-preview',()=>{back.hidden=!session;"""
NEW="""'bunny-loop-preview',()=>{/*loop-stop-visible*/const host=document.getElementById('timeline-playback');if(host&&back.parentElement!==host)host.append(back);back.hidden=!session;"""
t=sys.argv[1];p=os.path.join(t,'loops.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*loop-stop-visible*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
