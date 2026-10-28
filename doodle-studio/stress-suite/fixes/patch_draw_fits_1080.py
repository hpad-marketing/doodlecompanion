"""On a 1080p screen the Draw panel hid its Frames, Guides and This drawing rows below the
fold (224 px of scrolling at 1920x1080). The undo/help/frame stepper/status/thumbnail strip
now shares one band, section titles sit on their borders, rows are 36 px, the layer name and
order labels sit beside their fields, and the shortcut hint lives inside Drawing help.
The band layout applies only when the Draw desk is at least 900 px wide (container query),
so narrow panes keep the stacked layout. Fits at 1920x1080 and 2560x1440.
Usage: python patch_draw_fits_1080.py <src folder or built HTML>."""
import sys,os
MARK='/*draw-fits-1080*/'
CSS='/* Draw fits a 1080p screen: undo, help, frame stepper, status and thumbnails share one band above the tools. */\n.ux-overhaul #workspace-draw .workspace-desk{container-type:inline-size;container-name:drawdesk}\n@container drawdesk (min-width:900px){\n.ux-overhaul #workspace-draw #draw-brush-shelf{display:grid!important;grid-template-columns:max-content max-content minmax(0,1fr);column-gap:10px;row-gap:4px;align-content:start;align-items:start}\n.ux-overhaul #workspace-draw #draw-brush-shelf>*{grid-column:1 / -1!important;grid-row:auto!important}\n.ux-overhaul #workspace-draw #draw-brush-shelf>.draw-undo-row{grid-column:1!important;grid-row:1!important;display:flex!important;gap:6px;align-items:center}\n.ux-overhaul #workspace-draw #draw-brush-shelf>.draw-frames{grid-column:2!important;grid-row:1!important;margin:0}\n.ux-overhaul #workspace-draw #draw-brush-shelf>#draw-frame-status{grid-column:1 / 3!important;grid-row:2!important;margin:0;min-height:0;line-height:1.2}\n.ux-overhaul #workspace-draw #draw-brush-shelf>#draw-thumbs{grid-column:3!important;grid-row:1 / span 2!important;min-width:0}\n.ux-overhaul #workspace-draw #draw-brush-shelf>#draw-fbf{grid-column:1 / -1!important;grid-row:3!important}\n.ux-overhaul #workspace-draw #draw-brush-shelf .drawing-help[open]{position:relative;z-index:3}\n}\n.ux-overhaul #workspace-draw #draw-fbf{row-gap:14px!important;margin-top:8px}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-section{position:relative;padding:8px 8px 4px}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-section>h4{position:absolute;top:-9px;left:8px;margin:0;padding:0 4px;background:#E0A64B;line-height:16px}\n.ux-overhaul #workspace-draw #draw-fbf .fbf-row{min-height:36px}\n.ux-overhaul #workspace-draw #draw-fbf label.fbf-inline{flex-direction:row;align-items:center;gap:3px}\n.ux-overhaul #workspace-draw #draw-layer-properties>label{flex-direction:row!important;align-items:center;gap:8px}\n.ux-overhaul #workspace-draw #draw-layer-properties>label>:is(input,select){flex:1 1 auto;min-width:0}\n.ux-overhaul #workspace-draw #draw-layer-properties>label{display:grid!important;grid-template-columns:84px minmax(0,1fr)}\n.ux-overhaul #workspace-draw .drawing-help .fbf-hint{margin:6px 0 0;font-size:12px}\n'
HINT_OLD="old.after(strip,kit);"
HINT_NEW="old.after(strip,kit);{const hint=kit.querySelector('.fbf-hint'),help=pane.querySelector('.drawing-help');if(hint&&help)help.append(hint);}"
t=sys.argv[1]
if os.path.isdir(t):
    p=os.path.join(t,'ux-overhaul.css');s=open(p,encoding='utf-8').read()
    if MARK not in s:open(p,'w',encoding='utf-8').write(s.rstrip('\n')+'\n'+MARK+'\n'+CSS)
    p=os.path.join(t,'drawing-frames.js');s=open(p,encoding='utf-8').read()
    if HINT_NEW not in s:
        assert s.count(HINT_OLD)==1;open(p,'w',encoding='utf-8').write(s.replace(HINT_OLD,HINT_NEW))
    print('patched folder',t)
else:
    s=open(t,encoding='utf-8').read()
    if MARK not in s:
        anchor='\\n";document.head.append(style);\n document.body.classList.add(\'ux-overhaul\');'
        assert s.count(anchor)==1,s.count(anchor)
        s=s.replace(anchor,'\\n'+MARK+CSS.replace('\n','\\n')+anchor[2:])
    if HINT_NEW not in s:
        assert s.count(HINT_OLD)==1;s=s.replace(HINT_OLD,HINT_NEW)
    open(t,'w',encoding='utf-8').write(s);print('patched',t)
