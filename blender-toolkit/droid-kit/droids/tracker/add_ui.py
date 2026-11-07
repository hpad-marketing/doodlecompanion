"""Put the Tracker panel + Drive mode into the file as a registered text block, measure the scoop floor table,
and hook the voice slot (dv_level / dv_accent from Droid Voice) to the mouth.
python3 add_ui.py in.blend out.blend [kit_rig_ui.py]"""
import bpy, sys, math, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trcheck import Checker
blend, out = sys.argv[1], sys.argv[2]
import os as _os
_here = _os.path.dirname(_os.path.abspath(__file__))
KIT = _os.environ.get('DROID_KIT') or next((p for p in (_os.path.join(_here, '..', '..'), '/home/user/doodlecompanion/blender-toolkit/droid-kit')
                                           if _os.path.isdir(_os.path.join(p, 'kit'))), '')
kit_ui = sys.argv[3] if len(sys.argv) > 3 else _os.path.join(KIT, 'kit', 'rig_ui.py')
bpy.ops.wm.open_mainfile(filepath=blend)
arm = bpy.data.objects['TrackerRig']; pbs = arm.pose.bones; sc = bpy.context.scene
r = math.radians

# ---- assemble the UI module: tracker panels + the kit's gamepad reader + the physics model + tracker drive core
kit = open(kit_ui).read()
pad = kit[kit.index('# ================================================================== DRIVE MODE'):kit.index('class DriveInput:')]
phys = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tr_physics.py')).read()
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tr_ui.py')).read().replace('# @@PAD@@', pad).replace('# @@PHYSICS@@', phys)
compile(src, 'tracker_rig_ui.py', 'exec')
txt = bpy.data.texts.get('tracker_rig_ui.py') or bpy.data.texts.new('tracker_rig_ui.py')
txt.clear(); txt.write(src); txt.use_module = True

# ---- scoop floor table: lowest safe lift for each tilt, at rest suspension
if arm.animation_data: arm.animation_data.action = None
for pb in pbs: pb.location = (0, 0, 0); pb.rotation_euler = (0, 0, 0)
ck = Checker(arm)
parts = [o for o in ck.parts if o['rig_bone'] in ('scoop_lift', 'scoop_tilt')]
def low(lift, tilt):
    pbs['scoop_lift'].rotation_euler.x = r(lift); pbs['scoop_tilt'].rotation_euler.x = r(tilt)
    bpy.context.view_layer.update()
    return min(ck.world(o)[:, 2].min() for o in parts)
tbl = []
for tilt in range(-75, 21, 5):
    if low(8, tilt) >= 0.0015: tbl.append([tilt, 8.0]); continue
    a, b = -41.0, 8.0
    if low(a, tilt) < 0.0015: tbl.append([tilt, -41.0]); continue
    for _ in range(20):
        m = 0.5 * (a + b)
        if low(m, tilt) >= 0.0015: a = m
        else: b = m
    tbl.append([tilt, round(a, 2)])
arm['scoop_floor'] = json.dumps(tbl)
# how fast the teeth drop with lift, chassis pitch and heave (m per rad / m per m), measured near the floor
def grad(set_fn, h):
    set_fn(h); a = low(4.0, 10.0); set_fn(-h); b = low(4.0, 10.0); set_fn(0.0); return (a - b) / (2 * h)
def sp(v): pbs['suspension'].rotation_euler.x = v
def sh(v): pbs['suspension'].location.y = v
gl = (low(5.0, 10.0) - low(3.0, 10.0)) / r(2.0); gp = grad(sp, r(1.0)); gh = grad(sh, 0.004)
arm['scoop_floor_k'] = json.dumps([gl, gp, gh])
print('SCOOP K lift %.4f pitch %.4f heave %.4f' % (gl, gp, gh))
pbs['scoop_lift'].rotation_euler.x = 0; pbs['scoop_tilt'].rotation_euler.x = 0
print('SCOOP FLOOR', tbl)

# ---- voice slot: Droid Voice keys dv_level / dv_accent on the droid; the mouth opens with the level
for p in ('dv_level', 'dv_accent'):
    arm[p] = 0.0
    ui = arm.id_properties_ui(p); ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description='Droid Voice ' + p[3:])
arm['voice_cast'] = json.dumps({'id': 'tracker', 'name': 'Tracked porter', 'aliases': ['tracker', 'porter'], 'size_m': 0.9,
                                'hollow': 0.55, 'chain': 'crush', 'dials': {'bits': 5, 'hold_sr': 7000, 'ring_hz': 62, 'ring_mix': 0.35},
                                'engines': [{'engine': 'kokoro', 'voice': 'am_puck', 'speed': 1.12}, {'engine': 'espeak', 'voice': 'en-us+m4', 'speed': 1.15}]})
mouth = bpy.data.objects['face_mouth']
for d in mouth.data.shape_keys.animation_data.drivers:
    if d.data_path == 'key_blocks["open"].value' and 'lv' not in [v.name for v in d.driver.variables]:
        v = d.driver.variables.new(); v.name = 'lv'; v.type = 'SINGLE_PROP'
        v.targets[0].id = arm; v.targets[0].data_path = '["dv_level"]'
        d.driver.expression = 'max(v, min(1.0, 1.3 * lv))'
# screen flickers brighter on stressed syllables
for m in bpy.data.materials:
    if m.name == 'TR_face_glow' and m.node_tree.animation_data:
        for d in m.node_tree.animation_data.drivers:
            if 'acc' not in [v.name for v in d.driver.variables]:
                v = d.driver.variables.new(); v.name = 'acc'; v.type = 'SINGLE_PROP'
                v.targets[0].id = arm; v.targets[0].data_path = '["dv_accent"]'
                d.driver.expression = f'({d.driver.expression}) * (1 + 0.35 * acc)'
                print('accent hooked', d.data_path, d.driver.expression)
# pose presets in the kit format (lock sheet, collision check): {pose: {bone: [rot_deg xyz, loc xyz]}}
from bpy_extras import anim_utils
PP = {}
for act in sorted([a for a in bpy.data.actions if a.get('tracker_pose')], key=lambda a: a.get('order', 0)):
    d = {}
    for fc in anim_utils.action_get_channelbag_for_slot(act, act.slots[0]).fcurves:
        if not fc.data_path.startswith('pose.bones'): continue
        b = fc.data_path.split('"')[1]; e = d.setdefault(b, [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        v = fc.evaluate(1)
        if fc.data_path.endswith('rotation_euler'): e[0][fc.array_index] = round(math.degrees(v), 4)
        elif fc.data_path.endswith('location'): e[1][fc.array_index] = round(v, 6)
    PP[act['label']] = d
arm['pose_presets'] = json.dumps(PP)
print('POSE PRESETS', list(PP))
for o in bpy.data.objects:   # ship_foley: the sprocket spinners carry the tread sound, not 68 separate links
    if o.name.startswith(('track_link_', 'track_path', 'track_pin_')): o['foley_mech'] = 'none'
arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.wm.save_as_mainfile(filepath=out)
print('UI added', len(src.splitlines()), 'lines')
