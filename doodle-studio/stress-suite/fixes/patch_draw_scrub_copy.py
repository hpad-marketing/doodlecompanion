"""Idempotent fix: timeline-workbench's applyPose wrapper read Drawing.layers (a deep copy of every layer, cel and
stroke) seven times per frame while in the Draw workspace. Scrub/playback cost grew with drawing size.
Look the selected layer up once per frame, through the live finder when it exists (read-only use).
Run from the source root: python tools/patch_draw_scrub_copy.py  (or pass the src folder)."""
import sys,pathlib
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'src')
p=src/'timeline-workbench.js';s=p.read_text(encoding='utf-8')
old="for(const id of ['autoBlink','autoEars','walkMode','noiseAmount','buildOn','earPhysics','onion']){const b=buttons.get(id),l=S.workspace==='draw'&&Drawing.layers.find(l=>l.uid===Drawing.selected),"
new="const drawLayer=S.workspace==='draw'&&(Drawing._fx?.find?Drawing._fx.find(Drawing.selected):Drawing.layers.find(l=>l.uid===Drawing.selected));for(const id of ['autoBlink','autoEars','walkMode','noiseAmount','buildOn','earPhysics','onion']){const b=buttons.get(id),l=drawLayer,"
if new in s: print('already patched')
elif old in s: p.write_text(s.replace(old,new),encoding='utf-8');print('patched')
else: sys.exit('pattern not found: timeline-workbench.js changed, patch by hand')
