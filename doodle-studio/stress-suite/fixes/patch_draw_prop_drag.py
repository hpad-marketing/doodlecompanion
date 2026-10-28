"""Props open in the Draw workspace, but dragging a prop on the canvas there did nothing: the
Draw pen claimed the press and, with no drawing layer selected, only reported "Select a vector
drawing layer". A press that starts on a prop now goes to the prop whenever there is no vector
layer to draw on; with a drawing layer selected the pen still draws over props as before.
Usage: python patch_draw_prop_drag.py <src folder or built HTML>."""
import sys,os
OLD="""function down(event){if(!active()||['move','camera'].includes(window.BunnyCanvasTools?.mode)||!el.stage.contains(event.target))return;"""
NEW="""function down(event){if(!active()||['move','camera'].includes(window.BunnyCanvasTools?.mode)||!el.stage.contains(event.target))return;/*draw-prop-drag*/if(event.target.closest?.('[data-prop-id]')&&current()?.kind!=='vector')return;"""
t=sys.argv[1];p=os.path.join(t,'drawing.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if '/*draw-prop-drag*/' in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD);open(p,'w',encoding='utf-8').write(s.replace(OLD,NEW));print('patched',p)
