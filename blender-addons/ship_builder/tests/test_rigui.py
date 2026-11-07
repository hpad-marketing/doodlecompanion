"""Controls panel draws for a real droid rig:  python3 tests/test_rigui.py -- <droid .blend>"""
import sys, bpy
sys.path.insert(0, "/home/user/doodlecompanion/blender-addons")
import ship_builder as SB
SB.register()
from ship_builder import rigui
sys.path.insert(0, "/home/user/doodlecompanion/blender-addons/ship_builder/tests")
blend = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/mnt/attach/project-files/robot-rx07/Robot_RX07.blend"
with bpy.data.libraries.load(blend, link=False) as (src, dst):
    dst.objects = list(src.objects)
objs=[o for o in dst.objects if o]
rig = next(o for o in objs if o.type == "ARMATURE")
col = bpy.data.collections.new("Droid RX-07 (droid 1)"); bpy.context.scene.collection.children.link(col)
for o in rigui.keep_family(rig, objs): col.objects.link(o)
rig["sb_droid"]="rx07"
rigui.show_controls(rig)
class L:
    calls=[]
    def __getattr__(self, n):
        def f(*a, **k):
            L.calls.append((n, k.get("text")))
            return L()
        return f
    def __setattr__(self, n, v): pass
class C: scene=bpy.context.scene; mode="OBJECT"
rigui.draw_controls(L(), C)
print("DRAW OK", rigui.label(rig), [t for n,t in L.calls if n=="operator"][:12])
