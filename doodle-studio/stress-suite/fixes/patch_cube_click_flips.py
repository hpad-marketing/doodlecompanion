"""The view cube lost "click the face you're already looking at to flip to the opposite side" when
snaps became editor-only views. A plain click on the current face now snaps to the opposite face
again (front to back, above to below, front-left to back-right). Dragging and the snap API are unchanged.
Usage: python patch_cube_click_flips.py <src folder or built HTML>."""
import sys,os
OLD="else if(g.id)snap(g.id);"
NEW=("else if(g.id){/*cube-click-flips*/const ang=d=>Math.abs((((d%360)+540)%360)-180),o=values(),v=views[g.id];let id=g.id;"
"if(v&&Math.abs(o.view-v.view)<1&&(v.turn===undefined||ang(o.turn-v.turn)<1)){const turn=v.turn===undefined?undefined:v.turn+180,view=-v.view;"
"id=Object.keys(views).find(k=>{const w=views[k];return Math.abs(w.view-view)<1&&(turn===undefined?w.turn===undefined:w.turn!==undefined&&ang(w.turn-turn)<1);})||id;}snap(id);}")
t=sys.argv[1];p=os.path.join(t,'view-gizmo.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*cube-click-flips*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
