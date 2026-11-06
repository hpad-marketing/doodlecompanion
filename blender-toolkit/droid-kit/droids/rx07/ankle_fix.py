"""RX-07 ankles that can roll far enough to walk (physics audit, 2026-11-06).
To stand on one foot the body has to sway its weight over that foot, and the leg then leans ~15-20 degrees sideways
over the ankle. The ankle roll stage (GIM1-foot) is a square housing whose top corners hit the shin core at 12 degrees,
so the foot was dragged onto its outer edge instead. This:
  - rounds the top of ankle_joint.L/R into a drum around the roll axis (radius below the gap to the shin), so it turns
    freely inside the shin like a real trunnion
  - rounds the foot cheeks into clevis lugs around the ankle pin (their square tops hit the shin's clamps when rolled)
  - re-sweeps the roll range (with the foot pitched both ways too) until the first real contact and sets the ankle 'joint limits' (FK and deform) to it
  - lets the ankle frame absorb up to 10 degrees of leg twist so a planted foot never scrubs round on the floor
  - moves the knee pole targets 3 m ahead of the feet, so swaying the hips leans the leg instead of twisting it
    (the ankle has pitch + roll motors only; the leg's yaw comes from the hip)
python3 ankle_fix.py in.blend out.blend"""
import bpy, sys, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects['RobotRig']; pb = rig.pose.bones; arm = rig.data; ad = rig.animation_data
keep = (ad.action, ad.action_slot); ad.action = None
def rest():
    for b in pb:
        if not b.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
rest()
CLEAR = 0.006
# the shin's bone frame turns a few degrees about the leg as the hip sways over the foot (measured up to 9.4 deg);
# the foot must not follow it (it would scrub on the floor), so the ankle frame takes it
YAW = 10
for S in 'LR':
    o = bpy.data.objects[f'ankle_joint.{S}']; core = bpy.data.objects[f'shin_core.{S}']
    piv = rig.matrix_world @ pb[f'GIM1-foot.{S}'].head
    zc = min((core.matrix_world @ v.co).z for v in core.data.vertices)
    R = zc - piv.z - CLEAR
    if o.data.users > 1: o.data = o.data.copy()
    M = o.matrix_world; Mi = M.inverted(); n = 0
    for v in o.data.vertices:
        p = M @ v.co; d = Vector((p.x - piv.x, 0, p.z - piv.z))
        if p.z > piv.z and d.length > R:
            k = R / d.length; v.co = Mi @ Vector((piv.x + d.x * k, p.y, piv.z + d.z * k)); n += 1
    o.data.update(); print(S, 'ankle drum radius', round(R * 1000), 'mm,', n, 'verts rounded')

# the foot cheeks reached up past the ankle pin to the shin's bottom clamps; rounded into clevis lugs around the pin
# (radius LUG from the pin axis) so a rolled foot clears them
LUG = 0.045
for S in 'LR':
    pin = rig.matrix_world @ pb[f'DEF-foot.{S}'].head   # the pitch pin runs along x through the ankle head
    for n in (f'foot_cheek_i.{S}', f'foot_cheek_o.{S}'):
        o = bpy.data.objects[n]; M = o.matrix_world; Mi = M.inverted(); k = 0
        if o.data.users > 1: o.data = o.data.copy()
        for v in o.data.vertices:
            p = M @ v.co; d = Vector((0, p.y - pin.y, p.z - pin.z))
            if p.z > pin.z and d.length > LUG:
                d *= LUG / d.length; v.co = Mi @ Vector((p.x, pin.y + d.y, pin.z + d.z)); k += 1
        o.data.update()
    print(S, 'foot cheeks rounded into lugs, radius', LUG * 1000, 'mm')

# roll range: sweep until a leg part touches another it doesn't rest against
def trees(parts):
    dg = bpy.context.evaluated_depsgraph_get(); T = {}
    for o in parts:
        e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
        T[o.name] = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); e.to_mesh_clear()
    return T
lim = {}
for S in 'LR':
    parts = [o for o in bpy.data.objects if o.type == 'MESH' and str(o.get('rig_bone', '')).endswith('.' + S)
             and any(k in o['rig_bone'] for k in ('foot', 'toe', 'shin', 'ankle', 'knee', 'piston', 'thigh'))]
    for n_ in (f'DEF-foot.{S}', f'FK-foot.{S}'):
        for c in pb[n_].constraints:
            if c.type == 'LIMIT_ROTATION': c.min_y, c.max_y = math.radians(-40), math.radians(40)
    T = trees(parts); names = list(T)
    base = {frozenset((a, b)) for i, a in enumerate(names) for b in names[i + 1:] if T[a].overlap(T[b])}
    got = []
    for sign in (1, -1):
        ok = 0
        for d in range(1, 31):
            hit = False
            for pitch in (-20, 0, 25):   # rolled while the foot is also pitched (toe up / toe down), as in a walk
                pb[f'IK_foot.{S}'].rotation_euler = (math.radians(pitch), math.radians(d * sign), 0); bpy.context.view_layer.update(); T = trees(parts)
                if any(T[a].overlap(T[b]) for i, a in enumerate(names) for b in names[i + 1:] if frozenset((a, b)) not in base): hit = True; break
            if hit: break
            ok = d
        got.append(ok); pb[f'IK_foot.{S}'].rotation_euler = (0, 0, 0)
    r = min(25, min(got) - 1); lim[S] = r
    for n_ in (f'DEF-foot.{S}', f'FK-foot.{S}'):
        for c in pb[n_].constraints:
            if c.type == 'LIMIT_ROTATION':
                c.min_y, c.max_y = math.radians(-r), math.radians(r)
                c.use_limit_z = True; c.min_z, c.max_z = math.radians(-YAW), math.radians(YAW)
    print(S, 'ankle roll clear to', got, '-> limit +-', r)
rest()
# knee poles far ahead: the knee plane then holds the foot's forward direction
bpy.context.view_layer.objects.active = rig; rig.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
for S in 'LR':
    b = arm.edit_bones[f'pole_knee.{S}']; L = (b.tail - b.head).length
    b.head.y = -3.0; b.tail = b.head + Vector((0, -L, 0))
bpy.ops.object.mode_set(mode='OBJECT')
ad.action = keep[0]
if keep[0]: ad.action_slot = keep[1]
rig['ankle_roll_limit'] = lim
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('ANKLE_FIX ok')
