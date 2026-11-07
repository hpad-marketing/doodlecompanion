"""Every prop builds, stands on the floor, moves as one piece and has no parts inside each other.

    blender -b --factory-startup --python tests/test_props.py -- <extensions dir> <package>
"""
import importlib, sys
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, a[0])
pkg = a[1]
importlib.import_module(pkg)
Pr = importlib.import_module(pkg + ".props")
C = importlib.import_module(pkg + ".collide")
bad = 0
for k, pid in enumerate(Pr.PROPS):
    loc = Vector(((k % 5) * 4.0, (k // 5) * 4.0, 0))
    before = set(bpy.data.objects)
    ob = Pr.add(pid, loc)
    bpy.context.view_layer.update()
    new = [o for o in bpy.data.objects if o not in before]
    fam = [ob] + list(ob.children_recursive)
    stray = [o.name for o in new if o not in fam]
    pts = [o.matrix_world @ Vector(c) for o in fam if o.type == "MESH" for c in o.bound_box]
    lo = min(p.z for p in pts)
    cx = sum(p.x for p in pts) / len(pts) - loc.x
    hits = C.audit_objects(fam, 0.0015)
    ok = abs(lo) < 0.003 and not stray and not hits and abs(cx) < 0.6
    bad += not ok
    print("PROP", pid, "OK" if ok else "FAIL", len(fam), "parts, floor", round(lo, 4), "stray", stray[:3], "hits", [h[:2] for h in hits][:4])
print("PROPS DONE", len(Pr.PROPS), "bad", bad)
