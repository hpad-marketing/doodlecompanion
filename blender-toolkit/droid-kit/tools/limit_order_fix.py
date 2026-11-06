"""Joint limits that do nothing (physics audit, 2026-11-06). Blender applies constraints top to bottom, so a
'joint limits' LIMIT_ROTATION placed above a COPY_ROTATION / COPY_TRANSFORMS is overwritten by the copy and the
joint can turn past its stop (RX-07: the hip skirt plates followed the thighs 23 degrees into their own brackets).
This moves every such limit below the last copy on its bone, and lists them.
DROID=<id> python3 limit_order_fix.py in.blend out.blend"""
import bpy, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
rig = bpy.data.objects[kit.rig_name()]; fixed = []
# plates the limb pushes along (they must follow past their nominal range or the limb would cut through them)
SKIP = tuple((kit.get('physics', {}) or {}).get('limit_order_skip', []))
for pb in rig.pose.bones:
    if SKIP and pb.name.startswith(SKIP): continue
    cs = list(pb.constraints)
    copies = [i for i, c in enumerate(cs) if c.type in ('COPY_ROTATION', 'COPY_TRANSFORMS') and not c.mute]
    if not copies: continue
    for i, c in enumerate(cs):
        if c.type == 'LIMIT_ROTATION' and i < copies[-1]:
            pb.constraints.move(i, len(cs) - 1); fixed.append(pb.name); break
print('LIMIT_ORDER moved below the copy on', len(fixed), 'bones:', fixed)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True, relative_remap=False)
print('LIMIT_ORDER_FIX ok')
