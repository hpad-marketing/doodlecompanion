"""Adding a Walk/Jump/Head sway/Blank clip from the timeline clip buttons, or deleting the
selected clips, saved the change but left the stage as it was until the playhead moved, so a
new Blank did not hide Bunny (and deleting one did not bring him back) until you scrubbed.
Both now redraw the stage at the playhead. Usage: python patch_clip_redraw.py
<src folder (editor.template.html) or built HTML>."""
import sys,os
MARK='/*clip-redraw*/'
PAIRS=[("    proj.clips.push(c);\n    sel.clear(); sel.add(c.uid);\n    changed();\n  }",
        "    proj.clips.push(c);\n    sel.clear(); sel.add(c.uid);\n    changed();\n    "+MARK+"applyPose(playhead);\n  }"),
       ("    proj.cues = proj.cues.filter((c) => !ids.has(c.uid));\n    sel.clear();\n    changed();\n  }",
        "    proj.cues = proj.cues.filter((c) => !ids.has(c.uid));\n    sel.clear();\n    changed();\n    "+MARK+"applyPose(playhead);\n  }")]
t=sys.argv[1];p=os.path.join(t,'editor.template.html') if os.path.isdir(t) else t
s=open(p,encoding='utf-8').read()
if MARK in s:print('already patched');sys.exit()
for o,n in PAIRS:
    assert s.count(o)==1,(o[:40],s.count(o));s=s.replace(o,n)
open(p,'w',encoding='utf-8').write(s);print('patched',p)
