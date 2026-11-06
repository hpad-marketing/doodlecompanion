"""RX-07 flat soles (physics audit, 2026-11-06). At rest the foot block's sole sloped up 10 mm from the ball to the heel,
so the robot stood on the front edge of each foot and the toe blocks: its centre of mass (21 cm behind that edge) sat
outside what it stood on, and a real 1 t machine would tip backwards. This lowers the sole of foot_block.L/R onto the
floor along its whole length (only the bottom 6 cm of the block is reshaped, by up to 10 mm; nothing above moves).
python3 sole_fix.py in.blend out.blend"""
import bpy, sys
from mathutils import Vector
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects['RobotRig']; ad = rig.animation_data; keep = (ad.action, ad.action_slot); ad.action = None
for b in rig.pose.bones:
    if not b.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
BAND = 0.06; Z0 = 0.0
for S in 'LR':
    o = bpy.data.objects[f'foot_block.{S}']
    if o.data.users > 1: o.data = o.data.copy()
    M = o.matrix_world; Mi = M.inverted(); vs = o.data.vertices
    W = [M @ v.co for v in vs]
    # measure the sole as rendered (after the bevel modifier): lowest point near the front and near the back
    dg = bpy.context.evaluated_depsgraph_get(); e = o.evaluated_get(dg); me = e.to_mesh()
    E = [e.matrix_world @ v.co for v in me.vertices]; e.to_mesh_clear()
    y0, y1 = min(p.y for p in E), max(p.y for p in E); mid = (y0 + y1) / 2
    zf = min(p.z for p in E if p.y < mid); zb = min(p.z for p in E if p.y >= mid)
    yf = min((p for p in E if p.y < mid), key=lambda p: p.z).y; yb = min((p for p in E if p.y >= mid), key=lambda p: p.z).y
    slope = (zb - zf) / (yb - yf); zmin = min(p.z for p in W)
    for v, p in zip(vs, W):
        if p.z > zmin + BAND: continue
        fade = 1 - max(0.0, p.z - zmin - 0.02) / (BAND - 0.02)   # full shift on the sole and its bevel, easing out up the side
        dz = -(zf - Z0 + slope * (p.y - yf)) * fade
        v.co = Mi @ (p + Vector((0, 0, dz)))
    o.data.update()
    print(S, 'sole was front', round(zf * 1000, 1), 'mm, heel', round(zb * 1000, 1), 'mm')
ad.action = keep[0]
if keep[0]: ad.action_slot = keep[1]
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('SOLE_FIX ok')
