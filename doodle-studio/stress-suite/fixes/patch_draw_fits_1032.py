"""Follow-up to patch_draw_fits_1080: on a 1080p screen with the Windows taskbar (a 1920x1032
window) the Draw tools still ran about 15 px past the panel, so the Guides and This drawing rows
needed a scroll. Frame-by-frame rows drop from 36 to 32 px and the section gaps tighten.
Usage: python patch_draw_fits_1032.py <src folder or built HTML>."""
import sys,os
MARK='/*draw-fits-1032*/'
CSS='.ux-overhaul #workspace-draw #draw-fbf{row-gap:10px!important;margin-top:4px}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-row{min-height:32px}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-section{padding:6px 8px 2px}\n'
t=sys.argv[1]
if os.path.isdir(t):
    p=os.path.join(t,'ux-overhaul.css');s=open(p,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    assert '/*draw-fits-1080*/' in s,'apply patch_draw_fits_1080 first'
    open(p,'w',encoding='utf-8').write(s.rstrip('\n')+'\n'+MARK+'\n'+CSS);print('patched',p)
else:
    s=open(t,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    assert '/*draw-fits-1080*/' in s,'apply patch_draw_fits_1080 first'
    anchor='\\n";document.head.append(style);\n document.body.classList.add(\'ux-overhaul\');'
    assert s.count(anchor)==1,s.count(anchor)
    s=s.replace(anchor,'\\n'+MARK+CSS.replace('\n','\\n')+anchor[2:]);open(t,'w',encoding='utf-8').write(s);print('patched',t)
