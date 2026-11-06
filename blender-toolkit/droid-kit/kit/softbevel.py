"""Softer, wider-looking edges: a 2-segment Bevel modifier (4 mm, angle-limited) on the metal armour and box parts.
A bevel only removes material at convex edges, so it cannot create a new clash. python3 softbevel.py in out"""
import bpy, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kit
BEV = kit.get('bevel', [0.004, 0.0025, 0.06])   # [big part width, small part width, 'small' below this size] in m; small droids: smaller
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
n = 0
for o in bpy.data.objects:
    if o.type != 'MESH' or 'rig_bone' not in o or not o.active_material: continue
    m = o.active_material.name
    if not m.startswith('RB_metal') or m == 'RB_metal_pin' or min(o.dimensions) < 0.03: continue
    if 'RB_soft' in o.modifiers: continue
    b = o.modifiers.new('RB_soft', 'BEVEL'); b.width = BEV[0] if min(o.dimensions) > BEV[2] else BEV[1]
    b.segments = 2; b.limit_method = 'ANGLE'; b.angle_limit = 0.6; b.use_clamp_overlap = True; b.profile = 0.6
    b.miter_outer = 'MITER_ARC'
    n += 1
print('SOFTBEVEL', n)
bpy.ops.wm.save_as_mainfile(filepath=out)
