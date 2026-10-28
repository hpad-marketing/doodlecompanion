"""A detached Tools, Canvas or Timeline window lost the UX pass: its body never got the
'ux-overhaul' class, so removed buttons came back and the new layouts didn't apply (the detached
timeline toolbar stacked its buttons in tall columns and left about 90 px for the tracks).
Each detached body now carries the class when the main window has it.
Usage: python patch_detached_ux.py <src folder or built HTML>."""
import sys,os
UX="""'+(document.body.classList.contains('ux-overhaul')?' ux-overhaul':'')+'"""
PAIRS=[('detached-panels.js','<body class="studio dock-layout detached-panel" data-detached-panel="\'+id+\'">','<body class="studio dock-layout detached-panel'+UX+'" data-detached-panel="\'+id+\'">'),
       ('detached-timeline.js','<body class="studio detached-timeline">','<body class="studio detached-timeline'+UX+'">')]
t=sys.argv[1]
for name,old,new in PAIRS:
  p=os.path.join(t,name) if os.path.isdir(t) else t
  s=open(p,encoding='utf-8').read()
  if new in s:print('already patched',name);continue
  assert s.count(old)==1,(name,s.count(old));open(p,'w',encoding='utf-8').write(s.replace(old,new));print('patched',name)
