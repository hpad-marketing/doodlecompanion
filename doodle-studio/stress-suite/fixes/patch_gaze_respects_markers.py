"""Dragging a look/point target marker that sat over Bunny's eyes moved the eyes (wrote gaze
keys) instead of the marker. Eye dragging hit-tested the eye shapes under the pointer even when
a target marker or prop was drawn on top. A press on a target marker or prop now goes to that
object. Usage: python patch_gaze_respects_markers.py <src folder or built HTML>."""
import sys,os
OLD="""function hit(e){if(!available()||!el.stage.contains(e.target)||e.target.closest('[data-move-axis]'))return false;"""
NEW="""function hit(e){if(!available()||!el.stage.contains(e.target)||e.target.closest('[data-move-axis],[data-target-id],[data-prop-id]'/*gaze-respects-markers*/))return false;"""
t=sys.argv[1];p=os.path.join(t,'gaze-drag.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*gaze-respects-markers*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
