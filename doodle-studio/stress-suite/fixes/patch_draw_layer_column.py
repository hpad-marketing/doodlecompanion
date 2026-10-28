"""Draw layer column, part of fitting Draw on a 1080p screen: with a layer selected, the layer
list plus the layer settings ran well past the panel. The repeated "Draw & layers" heading is
hidden (the tabs name it), "Move, scale and flip" shares a row with Delete layer, and the layer
list's dividers are tighter. Saves about 30 px; the layer settings may still scroll at 1032 px.
Usage: python patch_draw_layer_column.py <src folder or built HTML>."""
import sys,os
MARK='/*draw-layer-column*/'
CSS='.ux-overhaul #workspace-draw .workspace-context>.context-heading{display:none}\n.ux-overhaul #workspace-draw #draw-layer-properties[open]{display:grid!important;grid-template-columns:minmax(0,1fr) auto;column-gap:6px;row-gap:6px;align-items:start}\n.ux-overhaul #workspace-draw #draw-layer-properties>*{grid-column:1 / -1}\n.ux-overhaul #workspace-draw #draw-layer-properties>#draw-layer-transform{grid-column:1;margin:0}\n.ux-overhaul #workspace-draw #draw-layer-properties>#draw-layer-transform[open]{grid-column:1 / -1}\n.ux-overhaul #workspace-draw #draw-layer-properties>#draw-delete-layer{grid-column:2;grid-row:auto}\n.ux-overhaul #workspace-draw .drawing-character-divider{padding-top:6px;padding-bottom:6px;margin:4px 0}\n.ux-overhaul #workspace-draw #drawing-layer-list>h3{margin:4px 0 2px}\n'
t=sys.argv[1]
anchor='\\n";document.head.append(style);\n document.body.classList.add(\'ux-overhaul\');'
if os.path.isdir(t):
    p=os.path.join(t,'ux-overhaul.css');s=open(p,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    open(p,'w',encoding='utf-8').write(s.rstrip('\n')+'\n'+MARK+'\n'+CSS);print('patched',p)
else:
    s=open(t,encoding='utf-8').read()
    if MARK in s:print('already patched');sys.exit()
    assert s.count(anchor)==1,s.count(anchor)
    s=s.replace(anchor,'\\n'+MARK+CSS.replace('\n','\\n')+anchor[2:]);open(t,'w',encoding='utf-8').write(s);print('patched',t)
