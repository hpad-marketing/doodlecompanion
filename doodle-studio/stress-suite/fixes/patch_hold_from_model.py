"""Draw > Hold + and - read the length shown in the Hold box. That box redraws on the next
animation frame, so a quick click right after adding or switching drawings (or while the
window is in the background) lengthened the drawing from the previous drawing's value
(a new 2-frame drawing jumped to 361 frames). The buttons now read the hold from the
drawing itself. Usage: python patch_hold_from_model.py <src folder or built HTML>."""
import sys,os
MARK='/*hold-from-model*/'
OLD="bind('draw-hold-less',()=>setHold(+q('#draw-hold-len').value-1));bind('draw-hold-more',()=>setHold(+q('#draw-hold-len').value+1));"
NEW=MARK+"const curHold=()=>{const l=fx.current(),c=l&&D.sample(l,f0());return c?fx.exposureEnd(l,c)-c.frame:+q('#draw-hold-len').value;};bind('draw-hold-less',()=>setHold(curHold()-1));bind('draw-hold-more',()=>setHold(curHold()+1));"
t=sys.argv[1];p=os.path.join(t,'drawing-frames.js') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if MARK in s:print('already patched');sys.exit()
assert s.count(OLD)==1,s.count(OLD)
s=s.replace(OLD,NEW);open(p,'w',encoding='utf-8').write(s);print('patched',p)
