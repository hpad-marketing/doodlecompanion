"""In a window 900 px wide or less, the snap cube was a fixed 224 px. When the canvas is short
(a 900x700 window leaves about 270 px of canvas) the cube spilled past the canvas bottom over
the panels. It now shrinks to the canvas height, keeping the 224 px size when there is room.
Usage: python patch_cube_fits_short_canvas.py <src folder or built HTML>."""
import sys,os
OLD="""@media(max-width:900.5px){.studio #stage-wrap #view-gizmo-controls{width:224px;height:224px}}"""
NEW="""@media(max-width:900.5px){.studio #stage-wrap #view-gizmo-controls{width:224px;height:224px}.studio #stage-wrap #view-gizmo-controls{/*cube-fits-short*/width:auto;height:max(96px,min(224px,calc(100% - 72px)));aspect-ratio:1}}"""
t=sys.argv[1];p=os.path.join(t,'workspace-usability.css') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*cube-fits-short*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
