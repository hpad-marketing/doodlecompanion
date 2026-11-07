"""Screen modes + secondary functions for the tracked droid.
python3 features.py in.blend out.blend imgdir
- Screen display: one emissive layer under the glass with 8 modes (rig prop screen_mode):
  0 face, 1 scan sweep, 2 battery (screen_value = charge), 3 error static, 4 loading (screen_value = progress),
  5 direction arrow (screen_value = heading in degrees), 6 sticker gallery (shows stickers_shown), 7 sleep.
  The face shapes only light in mode 0.
- Scanner beams from both stalk caps (prop scan 0-1, scan_sweep in degrees): real spot lights + a faint visible cone.
- Work lights: spot lights behind the headlamps and the chin lamp, so the droid lights the set (prop lamps).
- Vent dust: puffs from the chassis vents (prop vent_puff 0-1), they rise out of the gap beside the tracks.
Effects are named fx_* and carry no rig_bone, so the collision checks skip them."""
import bpy, sys, os, math
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFont, ImageFilter
blend, out, IMG = sys.argv[-3:]
os.makedirs(IMG, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
arm = bpy.data.objects['TrackerRig']; ad = arm.data; pbs = arm.pose.bones
V = Vector
FONT = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
col = bpy.data.collections.get('Tracker_FX') or bpy.data.collections.new('Tracker_FX')
if col.name not in bpy.data.collections['Tracker'].children: bpy.data.collections['Tracker'].children.link(col)

def sprop(name, val, lo, hi, desc):
    arm[name] = val; arm.id_properties_ui(name).update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=desc)
sprop('screen_mode', 0, 0, 7, 'Screen: 0 face, 1 scan, 2 battery, 3 error, 4 loading, 5 arrow, 6 stickers, 7 sleep')
sprop('screen_value', 0.7, -360.0, 360.0, 'Battery charge / loading progress (0-1) or arrow heading (deg)')
sprop('scan', 0.0, 0.0, 1.0, 'Scanner beams from the stalk caps')
sprop('vent_puff', 0.0, 0.0, 1.0, 'Dust puffing from the chassis vents')

def var(d, nm, path, ido=None, idt='OBJECT'):
    v = d.variables.new(); v.name = nm; v.type = 'SINGLE_PROP'; v.targets[0].id_type = idt; v.targets[0].id = ido or arm
    v.targets[0].data_path = path
def drv(owner, path, expr, props, index=-1):
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    d = fc.driver; d.type = 'SCRIPTED'
    for p in props: var(d, p, f'["{p}"]')
    d.expression = expr; assert d.is_simple_expression, expr
    return d

# ---------------------------------------------------------------- screen mode art (cyan line art, 512 x 390)
W, H = 768, 584
CY = (67, 228, 255, 255)
def cv(): return Image.new('RGBA', (W, H), (0, 0, 0, 255))
def save(name, im):
    glow = im.filter(ImageFilter.GaussianBlur(6))
    im = Image.blend(glow, im, 0.75)
    p = os.path.join(IMG, f'screen_{name}.png'); im.save(p)
    img = bpy.data.images.load(p, check_existing=True); img.pack(); return img
def font(s): return ImageFont.truetype(FONT, s)
def scan():
    im = cv(); d = ImageDraw.Draw(im); c = (W // 2, H // 2)
    for rr in (60, 130, 200, 270): d.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), outline=CY, width=5)
    d.line((c[0] - 290, c[1], c[0] + 290, c[1]), fill=CY, width=3); d.line((c[0], c[1] - 290, c[0], c[1] + 290), fill=CY, width=3)
    for x, y in ((520, 180), (260, 380), (430, 120)): d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=CY)
    return save('scan', im)
def battery():
    im = cv(); d = ImageDraw.Draw(im)
    d.rounded_rectangle((150, 190, 590, 400), 26, outline=CY, width=14); d.rounded_rectangle((590, 255, 630, 335), 8, fill=CY)
    return save('battery', im)
def error():
    im = cv(); d = ImageDraw.Draw(im)
    d.line([(384, 110), (560, 430), (208, 430), (384, 110)], fill=CY, width=16, joint='curve')
    d.rounded_rectangle((372, 210, 396, 350), 10, fill=CY); d.ellipse((370, 370, 398, 398), fill=CY)
    return save('error', im)
def loading():
    im = cv(); d = ImageDraw.Draw(im)
    d.rounded_rectangle((120, 260, 648, 330), 30, outline=CY, width=10)
    f = font(56); d.text((W // 2, 190), 'LOADING', font=f, fill=CY, anchor='mm')
    return save('loading', im)
def arrow():
    im = cv(); d = ImageDraw.Draw(im)
    d.polygon([(384, 90), (540, 280), (440, 280), (440, 480), (328, 480), (328, 280), (228, 280)], fill=CY)
    return save('arrow', im)
def sleep():
    im = cv(); d = ImageDraw.Draw(im)
    for (x, y, s) in ((300, 380, 150), (450, 250, 105), (560, 150, 70)): d.text((x, y), 'Z', font=font(s), fill=CY, anchor='mm')
    return save('sleep', im)
def gallery():
    im = cv(); d = ImageDraw.Draw(im)
    files = sorted(f for f in os.listdir(os.path.join(os.path.dirname(IMG), 'stickers')) if f.endswith('.png'))
    order = ['ringed_planet', 'rocket', 'kepler', 'star_badge', 'comet', 'fish', 'zone']
    for k, nm in enumerate(order):
        x, y = 60 + (k % 4) * 170, 70 + (k // 4) * 230
        p = os.path.join(os.path.dirname(IMG), 'stickers', f'sticker_{nm}.png')
        if os.path.exists(p):
            st = Image.open(p).convert('RGBA').resize((150, 150)); im.alpha_composite(st, (x, y))
        d.rounded_rectangle((x - 6, y - 6, x + 156, y + 156), 16, outline=CY, width=3)
    return save('gallery', im)
ART = [None, scan(), battery(), error(), loading(), arrow(), gallery(), sleep()]

# ---------------------------------------------------------------- display plane under the glass (body bone, same frame as the face)
body_shell = bpy.data.objects['body_shell']; panel = bpy.data.objects['screen_panel']
bpy.context.view_layer.update()
pw = [panel.matrix_world @ v.co for v in panel.data.vertices]
xs = [p.x for p in pw]; zs = [p.z for p in pw]; ys = [p.y for p in pw]
cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
sw, sh = max(xs) - min(xs) - 0.004, max(zs) - min(zs) - 0.004
yf = min(ys) - 0.0006                          # 0.6 mm in front of the panel, behind the face shapes (2.9 mm) and the glass
me = bpy.data.meshes.new('screen_display')
me.from_pydata([(cx + sw / 2, yf, cz - sh / 2), (cx - sw / 2, yf, cz - sh / 2), (cx - sw / 2, yf, cz + sh / 2), (cx + sw / 2, yf, cz + sh / 2)], [], [(0, 1, 2, 3)])
me.uv_layers.new(name='UVMap')
for i, uv in enumerate(((1, 0), (0, 0), (0, 1), (1, 1))): me.uv_layers[0].data[i].uv = uv   # u = 0 at the viewer's left (droid's right)
disp = bpy.data.objects.new('screen_display', me); bpy.data.collections['Tracker_Lights'].objects.link(disp)
disp['rig_bone'] = 'body'; disp['rb_led'] = 'screen'
b = ad.bones['body']
disp.parent = arm; disp.parent_type = 'BONE'; disp.parent_bone = 'body'
disp.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()

m = bpy.data.materials.new('TR_screen_display'); nt = m.node_tree; N = nt.nodes; L = nt.links; N.clear()
outn = N.new('ShaderNodeOutputMaterial'); em = N.new('ShaderNodeEmission'); tr = N.new('ShaderNodeBsdfTransparent'); mixs = N.new('ShaderNodeMixShader')
tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['UV'], sep.inputs[0])
def val(name, prop=None, expr=None, props=()):
    n = N.new('ShaderNodeValue'); n.name = n.label = name
    if prop or expr: drv(n.outputs[0], 'default_value', expr or prop, props or [prop])
    return n.outputs[0]
mode = val('mode', 'screen_mode'); value = val('value', 'screen_value'); tsec = N.new('ShaderNodeValue'); tsec.name = 'time'
d = tsec.outputs[0].driver_add('default_value').driver; d.type = 'SCRIPTED'; d.expression = 'frame / 24'
power = val('power', expr='power * face_glow', props=['power', 'face_glow'])
def mth(op, a, b=None):
    n = N.new('ShaderNodeMath'); n.operation = op
    for i, x in enumerate((a, b)):
        if x is None: continue
        if isinstance(x, (int, float)): n.inputs[i].default_value = x
        else: L.new(x, n.inputs[i])
    return n.outputs[0]
total = None
U, Vv = sep.outputs[0], sep.outputs[1]
for k in range(1, 8):
    sel = mth('COMPARE', mode, float(k)); sel.node.inputs[2].default_value = 0.5
    uvn = tc.outputs['UV']
    if k == 5:      # arrow: rotate the UV about the centre by the heading
        mp = N.new('ShaderNodeMapping'); mp.vector_type = 'POINT'; L.new(tc.outputs['UV'], mp.inputs[0])
        sub = N.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (0.5, 0.5, 0)
        L.new(tc.outputs['UV'], sub.inputs[0])
        rot = N.new('ShaderNodeVectorRotate'); rot.rotation_type = 'Z_AXIS'; L.new(sub.outputs[0], rot.inputs[0])
        L.new(mth('MULTIPLY', value, math.pi / 180), rot.inputs['Angle'])
        add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'; add.inputs[1].default_value = (0.5, 0.5, 0); L.new(rot.outputs[0], add.inputs[0])
        uvn = add.outputs[0]
    tx = N.new('ShaderNodeTexImage'); tx.image = ART[k]; tx.extension = 'CLIP'; L.new(uvn, tx.inputs[0])
    lum = mth('MAXIMUM', N.new('ShaderNodeSeparateColor').outputs[2], 0.0)
    sc_ = lum.node.inputs[0].links[0].from_node; L.new(tx.outputs['Color'], sc_.inputs[0])
    layer = lum
    if k == 1:      # scan: a sweeping wedge + fading trail
        du = mth('SUBTRACT', U, 0.5); dv = mth('SUBTRACT', Vv, 0.5)
        ang = mth('ARCTAN2', dv, du); sw_ = mth('MULTIPLY', tsec.outputs[0], 2.6)
        rel = mth('FRACT', mth('DIVIDE', mth('SUBTRACT', ang, sw_), 2 * math.pi))
        trail = mth('POWER', mth('SUBTRACT', 1.0, rel), 6.0)
        layer = mth('ADD', mth('MULTIPLY', lum, 0.55), mth('MULTIPLY', trail, 0.65))
    if k == 2:      # battery: fill bar to the charge, blinking when under 20 %
        inside = mth('MULTIPLY', mth('MULTIPLY', mth('GREATER_THAN', U, 0.225), mth('LESS_THAN', U, mth('ADD', 0.225, mth('MULTIPLY', value, 0.53)))),
                     mth('MULTIPLY', mth('GREATER_THAN', Vv, 0.34), mth('LESS_THAN', Vv, 0.64)))
        blink = mth('MAXIMUM', mth('GREATER_THAN', value, 0.2), mth('GREATER_THAN', mth('SINE', mth('MULTIPLY', tsec.outputs[0], 12.0)), 0.0))
        layer = mth('ADD', lum, mth('MULTIPLY', inside, mth('MULTIPLY', blink, 0.85)))
    if k == 3:      # error: the icon flickers through scan-line static
        nz = N.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'; nz.inputs['Scale'].default_value = 140.0
        L.new(tc.outputs['UV'], nz.inputs[0]); L.new(mth('MULTIPLY', tsec.outputs[0], 30.0), nz.inputs['W'])
        lines = mth('GREATER_THAN', mth('SINE', mth('ADD', mth('MULTIPLY', Vv, 260.0), mth('MULTIPLY', tsec.outputs[0], 40.0))), 0.6)
        stat = mth('MULTIPLY', mth('POWER', nz.outputs['Fac'], 3.0), 0.9)
        layer = mth('ADD', mth('MULTIPLY', lum, mth('GREATER_THAN', mth('SINE', mth('MULTIPLY', tsec.outputs[0], 9.0)), -0.4)), mth('MULTIPLY', stat, mth('ADD', 0.4, lines)))
    if k == 4:      # loading: the bar fills to the progress value
        fill = mth('MULTIPLY', mth('MULTIPLY', mth('GREATER_THAN', U, 0.175), mth('LESS_THAN', U, mth('ADD', 0.175, mth('MULTIPLY', value, 0.65)))),
                   mth('MULTIPLY', mth('GREATER_THAN', Vv, 0.47), mth('LESS_THAN', Vv, 0.53)))
        layer = mth('ADD', lum, fill)
    if k == 7:      # sleep: slow breathing glow
        layer = mth('MULTIPLY', lum, mth('ADD', 0.55, mth('MULTIPLY', mth('SINE', mth('MULTIPLY', tsec.outputs[0], 1.6)), 0.35)))
    if k == 6:      # gallery keeps the sticker colours, so it is handled as colour below
        layer = mth('MULTIPLY', lum, 0.0)
    part = mth('MULTIPLY', layer, sel)
    total = part if total is None else mth('ADD', total, part)
    if k == 6: gal_sel, gal_tx = sel, tx
strength = mth('MULTIPLY', mth('MULTIPLY', total, power), 6.0)
# colour: cyan for line modes, the sticker art for the gallery
cmix = N.new('ShaderNodeMix'); cmix.data_type = 'RGBA'; L.new(gal_sel, cmix.inputs[0])
cmix.inputs[6].default_value = (0.06, 0.78, 1.0, 1); L.new(gal_tx.outputs['Color'], cmix.inputs[7])
L.new(cmix.outputs[2], em.inputs['Color'])
gal_strength = mth('MULTIPLY', mth('MULTIPLY', gal_sel, power), 2.2)
L.new(mth('ADD', strength, gal_strength), em.inputs['Strength'])
alpha = mth('MINIMUM', mth('ADD', total, gal_sel), 1.0)
L.new(alpha, mixs.inputs[0]); L.new(tr.outputs[0], mixs.inputs[1]); L.new(em.outputs[0], mixs.inputs[2])
glow = N.new('ShaderNodeEmission'); glow.name = glow.label = 'Glow'; glow.inputs['Strength'].default_value = 0.0; glow.inputs['Color'].default_value = (0.06, 0.78, 1.0, 1)
addn = N.new('ShaderNodeAddShader'); L.new(mixs.outputs[0], addn.inputs[0]); L.new(glow.outputs[0], addn.inputs[1]); L.new(addn.outputs[0], outn.inputs['Surface'])
me.materials.append(m); disp.visible_shadow = False
# the face shapes light only in mode 0
fm = bpy.data.materials['TR_face_glow']; bsdf = fm.node_tree.nodes['Principled BSDF']
bsdf.inputs['Emission Strength'].driver_remove('default_value')
drv(bsdf.inputs['Emission Strength'], 'default_value', '6.0 * face_glow * power * (screen_mode < 0.5)', ['face_glow', 'power', 'screen_mode'])
for o in bpy.data.objects:
    if o.name.startswith('face_'): drv(o, 'hide_render', 'screen_mode > 0.5', ['screen_mode'])

# ---------------------------------------------------------------- lights that light the set
def spot(name, bone, loc, direction, energy_expr, props, size_deg=60, blend=0.4, color=(1.0, 0.9, 0.75), radius=0.01):
    Ld = bpy.data.lights.new(name, 'SPOT'); Ld.spot_size = math.radians(size_deg); Ld.spot_blend = blend; Ld.color = color
    Ld.shadow_soft_size = radius; Ld.energy = 0
    o = bpy.data.objects.new(name, Ld); col.objects.link(o)
    o.matrix_world = Matrix.Translation(V(loc)) @ V(direction).to_track_quat('-Z', 'Z').to_matrix().to_4x4()
    bb = ad.bones[bone]; mw = o.matrix_world.copy()
    o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = bone
    o.matrix_parent_inverse = (arm.matrix_world @ bb.matrix_local @ Matrix.Translation((0, bb.length, 0))).inverted()
    o.matrix_world = mw
    drv(Ld, 'energy', energy_expr, props)
    return o
import bmesh
def beam(o, name, length, radius, color, strength_expr, props, blend=0.35):
    """a faint visible cone in haze: apex AT the lamp (light origin), opening along the light's -Z, no shadow, additive"""
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=radius, radius2=0.0, depth=length)
    bmesh.ops.translate(bm, vec=(0, 0, -length / 2), verts=bm.verts)      # tip at z=0, wide end at z=-length
    cm = bpy.data.meshes.new(name); bm.to_mesh(cm); bm.free()
    cone = bpy.data.objects.new(name, cm); col.objects.link(cone)
    cone.parent = o; cone.matrix_parent_inverse = Matrix.Identity(4); cone.location = (0, 0, 0)
    mt = bpy.data.materials.new('TR_' + name.split('.')[0]); n2 = mt.node_tree.nodes; l2 = mt.node_tree.links; n2.clear()
    o2 = n2.new('ShaderNodeOutputMaterial'); e2 = n2.new('ShaderNodeEmission'); t2 = n2.new('ShaderNodeBsdfTransparent'); a2 = n2.new('ShaderNodeAddShader')
    e2.inputs['Color'].default_value = (*color, 1); lw = n2.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = blend
    mul = n2.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; l2.new(lw.outputs['Facing'], mul.inputs[0])
    sv = n2.new('ShaderNodeValue'); sv.name = 'strength'; drv(sv.outputs[0], 'default_value', strength_expr, props)
    l2.new(sv.outputs[0], mul.inputs[1]); l2.new(mul.outputs[0], e2.inputs['Strength'])
    l2.new(e2.outputs[0], a2.inputs[0]); l2.new(t2.outputs[0], a2.inputs[1]); l2.new(a2.outputs[0], o2.inputs['Surface'])
    cm.materials.append(mt); cone.visible_shadow = False
    for c_ in ('diffuse', 'glossy', 'transmission', 'volume_scatter'): setattr(cone, 'visible_' + c_, False)
    off = f'{props[0]} < 0.02'
    drv(cone, 'hide_render', off, props[:1]); drv(cone, 'hide_viewport', off, props[:1])
    return cone
# work lights (brighter option approved at lock): stronger headlamps + chin lamp, each with a visible beam in the air
for S in 'LR':
    hl = bpy.data.objects[f'headlamp.{S}']; c = hl.matrix_world @ (sum((V(v.co) for v in hl.data.vertices), V()) / len(hl.data.vertices))
    o = spot(f'fx_worklight.{S}', 'chassis', c + V((0, -0.01, 0)), (0, -1, -0.25), '32.0 * lamps * power', ['lamps', 'power'], 70, 0.5)
    beam(o, f'fx_work_beam.{S}', 0.85, 0.30, (1.0, 0.88, 0.68), '0.35 * lamps * power', ['lamps', 'power'])
cl = bpy.data.objects['chin_lamp']; c = cl.matrix_world @ (sum((V(v.co) for v in cl.data.vertices), V()) / len(cl.data.vertices))
o = spot('fx_chinlight', 'body', c + V((0, -0.01, 0)), (0, -1, -0.5), '16.0 * lamps * power', ['lamps', 'power'], 90, 0.6)
beam(o, 'fx_chin_beam', 0.6, 0.30, (1.0, 0.88, 0.68), '0.25 * lamps * power', ['lamps', 'power'])
# scanner: a spot from each cap lens + a thin visible cone that starts at the lens
for S in 'LR':
    ln = bpy.data.objects[f'stalk_lens.{S}']; c = ln.matrix_world @ (sum((V(v.co) for v in ln.data.vertices), V()) / len(ln.data.vertices))
    o = spot(f'fx_scanner.{S}', f'stalk_tip.{S}', c + V((0, -0.004, 0)), (0, -1, -0.35), '9.0 * scan * power', ['scan', 'power'], 16, 0.15,
             color=(0.25, 0.85, 1.0), radius=0.002)
    beam(o, f'fx_scan_beam.{S}', 0.9, 0.20, (0.25, 0.85, 1.0), '0.6 * scan * power', ['scan', 'power'])
# ---------------------------------------------------------------- vent dust: volume puffs rising from the side vents
dust = bpy.data.materials.new('TR_vent_dust'); n3 = dust.node_tree.nodes; l3 = dust.node_tree.links; n3.clear()
o3 = n3.new('ShaderNodeOutputMaterial'); pv = n3.new('ShaderNodeVolumePrincipled'); pv.inputs['Color'].default_value = (0.55, 0.5, 0.42, 1)
dv = n3.new('ShaderNodeValue'); drv(dv.outputs[0], 'default_value', '40.0 * vent_puff', ['vent_puff'])
nz = n3.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 9.0; mu = n3.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'
l3.new(nz.outputs['Fac'], mu.inputs[0]); l3.new(dv.outputs[0], mu.inputs[1]); l3.new(mu.outputs[0], pv.inputs['Density'])
l3.new(pv.outputs[0], o3.inputs['Volume'])
import random
rnd = random.Random(4)
ch = bpy.data.objects['chassis_hull']
for S, s in (('L', 1), ('R', -1)):
    for k in range(5):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.03)
        p = bpy.context.object; p.name = f'fx_vent_dust_{k}.{S}'
        for cc in p.users_collection: cc.objects.unlink(p)
        col.objects.link(p); p.data.materials.append(dust)
        base = V((s * 0.225, -0.07 + k * 0.03, 0.30))
        bb = ad.bones['chassis']
        p.parent = arm; p.parent_type = 'BONE'; p.parent_bone = 'chassis'
        p.matrix_parent_inverse = (arm.matrix_world @ bb.matrix_local @ Matrix.Translation((0, bb.length, 0))).inverted()
        p.location = base
        ph = rnd.uniform(0, 1)
        # each puff rises and grows over a 1.2 s cycle, offset in phase; scale 0 when vent_puff is 0
        e = f'(frame / 29.0 + {ph:.3f} - floor(frame / 29.0 + {ph:.3f}))'
        drv(p, 'location', f'{base.z:.4f} + 0.24 * {e}', [], index=2)
        for i in range(3): drv(p, 'scale', f'vent_puff * (0.7 + 2.6 * {e})', ['vent_puff'], index=i)
        drv(p, 'hide_render', 'vent_puff < 0.02', ['vent_puff'])
print('FEATURES screen modes 8, lights', len([o for o in col.objects if o.type == 'LIGHT']), 'puffs', len([o for o in col.objects if 'dust' in o.name]))
bpy.ops.wm.save_as_mainfile(filepath=out)
