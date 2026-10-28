"""Clicks in the paged Tools panel could miss: clicking a control focused a large container (for
example Draw's frame-by-frame tools), and the shelf's keyboard focus-follow treated that container as
off screen and scrolled the panel about 380 px between mouse-down and mouse-up, so the click landed
elsewhere (Hold +, Add modifier). Focus-follow now applies only to keyboard focus, and only when the
focused control is fully out of view and fits on a page. Usage: python patch_shelf_focus_pointer.py <src folder or built HTML>."""
import sys,os
OLD="content.addEventListener('focusin',e=>{if(!desktop())return;const node=e.target,r=node.getBoundingClientRect(),c=content.getBoundingClientRect();if(r.top<c.top||r.bottom>c.bottom){"
NEW=("/*shelf-focus-pointer*/let pointerAt=0;content.addEventListener('pointerdown',()=>{pointerAt=performance.now();},true);"
"content.addEventListener('focusin',e=>{if(!desktop()||performance.now()-pointerAt<800)return;const node=e.target,r=node.getBoundingClientRect(),c=content.getBoundingClientRect();if(r.height<=c.height&&(r.bottom<=c.top||r.top>=c.bottom)){")
t=sys.argv[1];p=os.path.join(t,'tool-shelves.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*shelf-focus-pointer*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
