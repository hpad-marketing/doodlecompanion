"""Draw's frame-by-frame rows ran 3 px past the tool panel at 1280 px on Windows: the #draw-fbf grid
sized its one column to the rows' content, and Windows UI fonts make that content a little wider.
The column now takes the panel's width and the rows shrink or wrap inside it.
Usage: python patch_fbf_fits_panel.py <src folder or built HTML>."""
import sys,os
MARK='/*fbf-fits-panel*/'
CSS='.ux-overhaul #workspace-draw #draw-fbf{grid-template-columns:minmax(0,1fr)!important;min-width:0;max-width:100%}\n.ux-overhaul #workspace-draw #draw-fbf>*{min-width:0;max-width:100%}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-row{min-width:0;max-width:100%;flex-wrap:wrap}\n'
t=sys.argv[1]
if os.path.isdir(t):
    p=os.path.join(t,'ux-overhaul.css');s=open(p,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    open(p,'w',encoding='utf-8').write(s.rstrip('\n')+'\n'+MARK+'\n'+CSS);print('patched',p)
else:
    s=open(t,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    anchor='\\n";document.head.append(style);\n document.body.classList.add(\'ux-overhaul\');'
    assert s.count(anchor)==1,s.count(anchor)
    s=s.replace(anchor,'\\n'+MARK+CSS.replace('\n','\\n')+anchor[2:]);open(t,'w',encoding='utf-8').write(s);print('patched',t)
