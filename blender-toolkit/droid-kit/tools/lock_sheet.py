"""Model-lock sheet: every panel the user approves before a droid locks, on one page.
Renders 8 turntable views, each hero pose, each face/light state and close-ups, then a contact sheet and a manifest
(panels + captions) that the Approve/Fix page reads.  DROID=<id> python3 lock_sheet.py in.blend outdir [samples]
Uses the droid's own camera rig-free: the camera is placed from the droid's bounding box, so it works for any droid."""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
from mathutils import Vector, Quaternion
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
blend, outdir = args[0], args[1]; samples = int(args[2]) if len(args) > 2 and args[2].isdigit() else 32
bpy.ops.wm.open_mainfile(filepath=blend)
os.makedirs(outdir, exist_ok=True)
sc = bpy.context.scene; rig = bpy.data.objects[kit.rig_name()]
if rig.animation_data: rig.animation_data.action = None
for t in rig.animation_data.nla_tracks if rig.animation_data else []: t.mute = True
sc.render.use_motion_blur = False
cam = sc.camera; cam.animation_data_clear(); cam.delta_location = (0, 0, 0); cam.delta_rotation_euler = (0, 0, 0)
cam.data.dof.use_dof = False
for o in bpy.data.collections.get('Dust_Steps', bpy.data.collections.new('_')).objects: o.hide_render = True
parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o]
LS = kit.get('lock_sheet', {})
HIDE = tuple(LS.get('hide', ['Prop_', 'dust_', 'Dust_', 'Haze_']))   # set dressing and dust that would block a panel
for o in bpy.data.objects:
    if o.name.startswith(HIDE): o.hide_render = True
def bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in objs:
        M = o.evaluated_get(dg).matrix_world; pts += [M @ Vector(c) for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)]); return lo, hi
def aim(loc, tgt, lens):
    cam.location = loc; cam.data.lens = lens; cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
def shot(name, w=540, h=675):
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.cycles.samples = samples
    sc.render.filepath = os.path.join(outdir, name + '.png'); bpy.ops.render.render(write_still=True); return name + '.png'
def reset():
    for p in rig.pose.bones:
        if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
def frame_whole(az, el=12, lens=50):
    lo, hi = bbox(parts); c = (lo + hi) / 2; r = (hi - lo).length * 0.5
    d = r / math.tan(math.atan(18 / lens)) * 1.05
    a, e = math.radians(az), math.radians(el)
    aim(c + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d, c, lens)
panels = []
reset()
for k, az in enumerate(range(0, 360, 45) if LS.get('turntable', True) else []):
    frame_whole(az); panels.append({'group': 'Turntable', 'label': f'{az}°', 'file': shot(f'turn_{az:03d}')})
P = json.loads(rig.get('pose_presets', '{}'))
for name in kit.get('lock_sheet', {}).get('hero', list(P)):
    if name not in P: continue
    reset()
    for b, (rot, loc) in P[name].items():
        if b in rig.pose.bones: rig.pose.bones[b].rotation_euler = [math.radians(v) for v in rot]; rig.pose.bones[b].location = loc
    bpy.context.view_layer.update(); frame_whole(-35, 10)
    panels.append({'group': 'Hero poses', 'label': name, 'file': shot('pose_' + name.lower().replace(' ', '_'))})
reset()
H = kit.get('hooks', {})
def set_state(st):
    for m in H.get('leds', []):
        mm = bpy.data.materials.get(m)
        if mm and 'led' in st:
            b = mm.node_tree.nodes.get('Principled BSDF'); inp = b.inputs['Emission Strength']
            if mm.node_tree.animation_data:
                for d in list(mm.node_tree.animation_data.drivers): mm.node_tree.animation_data.drivers.remove(d)
            inp.default_value = st['led']
    for m in H.get('glow_materials', []):
        mm = bpy.data.materials.get(m)
        if mm and 'glow' in st:
            g = mm.node_tree.nodes.get(H.get('glow_node', 'Glow'))
            if g: g.inputs['Strength'].default_value = st['glow']
    for k, v in st.items():
        if k not in ('led', 'glow') and k in rig: rig[k] = v
for st in kit.get('lock_sheet', {}).get('states', []):
    set_state(st['set']); frame_whole(-20, 8, 70)
    lo, hi = bbox(parts); c = (lo + hi) / 2; top = Vector((c.x, lo.y, hi.z - (hi.z - lo.z) * 0.22))   # face the front, upper body
    if LS.get('state_framing', 'upper') == 'upper': aim(top + Vector((-0.4, -1.9, 0.25)), top, 55)   # 'full' keeps the whole droid (round droids)
    panels.append({'group': 'Face & light states', 'label': st['label'], 'file': shot('state_' + st['label'].lower().replace(' ', '_'))})
set_state({'led': 3, 'glow': 0})
for cu in LS.get('closeups', []):
    nm, view = (cu, None) if isinstance(cu, str) else (cu['object'], cu.get('view'))   # view: optional camera direction from the part
    o = bpy.data.objects.get(nm)
    if not o: continue
    lo, hi = bbox([o]); c = (lo + hi) / 2; r = max((hi - lo).length, 0.12)
    blo, bhi = bbox(parts); out = c - (blo + bhi) / 2; out.z = 0   # default: look at the part from its outer side
    side = out.normalized() if out.length > 0.15 else Vector((0, -1, 0))
    d = Vector(view) if view else side + Vector((-0.35 * side.y, 0.35 * side.x, 0.45))
    def clear(dv):   # can the camera see the part, or is a shell / arm in the way?
        loc = c + dv.normalized() * r * 3.2; hit, _, _, _, ob, _ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), loc, (c - loc).normalized())
        while ob and ob != o: ob = ob.parent
        return not hit or ob == o
    if not view and not clear(d):
        for k in range(1, 12):   # walk round the part until it is in view
            q = Quaternion((0, 0, 1), math.radians(30 * k)) @ d
            if clear(q): d = q; break
    aim(c + d.normalized() * r * 3.2, c, 60)
    panels.append({'group': 'Close-ups', 'label': nm, 'file': shot('close_' + nm.replace('.', '_'), 540, 540)})
json.dump({'droid': kit.get('name', ''), 'kit': kit.VERSION, 'panels': panels}, open(os.path.join(outdir, 'manifest.json'), 'w'), indent=1)
# contact sheet
from PIL import Image, ImageDraw
ims = [(p, Image.open(os.path.join(outdir, p['file'])).convert('RGB')) for p in panels]
W = 270; cols = 6; rows = (len(ims) + cols - 1) // cols; sheet = Image.new('RGB', (W * cols, int(W * 1.25 + 22) * rows), (31, 31, 29))
d = ImageDraw.Draw(sheet)
for i, (p, im) in enumerate(ims):
    im.thumbnail((W, int(W * 1.25))); x, y = (i % cols) * W, (i // cols) * int(W * 1.25 + 22)
    sheet.paste(im, (x, y)); d.text((x + 6, y + int(W * 1.25) + 4), f"{p['group']}: {p['label']}", fill=(243, 208, 142))
sheet.save(os.path.join(outdir, 'lock_sheet.png'))
print('LOCKSHEET', len(panels), 'panels ->', outdir)
