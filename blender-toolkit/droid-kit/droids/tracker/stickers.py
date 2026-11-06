"""Souvenir stickers: full-colour vinyl stickers, one per planet visited (the running gag). Each sits 0.4 mm off a flat
face (raycast-checked like the kit decals), corners lifting and peeling, scuffed and dirty.
python3 stickers.py in.blend out.blend imgdir"""
import bpy, sys, os, math, random
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFont, ImageFilter
blend, out, IMG = sys.argv[-3:]
os.makedirs(IMG, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
import os as _os
_here = _os.path.dirname(_os.path.abspath(__file__))
KIT = _os.environ.get('DROID_KIT') or next((p for p in (_os.path.join(_here, '..', '..'), '/home/user/doodlecompanion/blender-toolkit/droid-kit')
                                           if _os.path.isdir(_os.path.join(p, 'kit'))), '')
K = _os.path.join(KIT, 'kit', 'decals.py')
src = open(K).read()
FONT = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
ns = {'bpy': bpy, 'Vector': Vector, 'Matrix': Matrix}
exec(src[src.index('def frame(n, up)'):src.index("col = bpy.data.collections")].replace('scene.ray_cast(dg', 'SC.ray_cast(DG'), ns)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.data.pose_position = 'REST'; bpy.context.view_layer.update()
ns['DG'] = bpy.context.evaluated_depsgraph_get(); ns['SC'] = bpy.context.scene
place = ns['place']
col = bpy.data.collections.get('Stickers') or bpy.data.collections.new('Stickers')
if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)

def C(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
INK, CREAM, ORANGE, RED, YEL, BLUE, MINT, PLUM = map(C, ('#1F1F1D', '#F1E6C8', '#E8722E', '#D9443A', '#F2C14E', '#3D7DCA', '#6CC4A1', '#7A4E9C'))
PX = 512
def canvas(): return Image.new('RGBA', (PX, PX), (0, 0, 0, 0))
def border(im, shape):
    """die-cut white border round the artwork, like a real vinyl sticker"""
    a = im.split()[3].filter(ImageFilter.MaxFilter(25))
    base = Image.new('RGBA', im.size, CREAM); base.putalpha(a)
    return Image.alpha_composite(base, im)
def font(s): return ImageFont.truetype(FONT, s)
def ringed_planet():
    im = canvas(); d = ImageDraw.Draw(im)
    d.ellipse((60, 190, 452, 330), outline=YEL, width=26)
    d.ellipse((140, 120, 372, 352), fill=ORANGE)
    d.chord((140, 120, 372, 352), 200, 340, fill=RED)
    d.arc((60, 190, 452, 330), 200, 340, fill=YEL, width=26)
    return border(im, 'round')
def rocket():
    im = canvas(); d = ImageDraw.Draw(im)
    d.polygon([(256, 40), (330, 160), (330, 360), (182, 360), (182, 160)], fill=CREAM)
    d.polygon([(256, 40), (330, 160), (182, 160)], fill=RED)
    d.ellipse((222, 200, 290, 268), fill=BLUE); d.ellipse((236, 214, 276, 254), fill=MINT)
    d.polygon([(182, 290), (120, 400), (182, 370)], fill=RED); d.polygon([(330, 290), (392, 400), (330, 370)], fill=RED)
    d.polygon([(206, 360), (306, 360), (256, 470)], fill=YEL); d.polygon([(226, 360), (286, 360), (256, 430)], fill=ORANGE)
    return border(im, 'shape')
def star_badge():
    im = canvas(); d = ImageDraw.Draw(im)
    d.ellipse((40, 40, 472, 472), fill=BLUE)
    pts = [(256 + (180 if k % 2 == 0 else 78) * math.cos(math.radians(-90 + 36 * k)), 256 + (180 if k % 2 == 0 else 78) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)]
    d.polygon(pts, fill=YEL)
    return border(im, 'round')
def text_sticker(word, sub, bg, fg):
    im = canvas(); d = ImageDraw.Draw(im)
    d.rounded_rectangle((30, 150, 482, 362), 46, fill=bg)
    f = font(120); b = d.textbbox((0, 0), word, font=f)
    while b[2] - b[0] > 400: f = font(f.size - 6); b = d.textbbox((0, 0), word, font=f)
    d.text(((PX - (b[2] - b[0])) / 2 - b[0], 175 - b[1]), word, font=f, fill=fg)
    f2 = font(40); b2 = d.textbbox((0, 0), sub, font=f2)
    d.text(((PX - (b2[2] - b2[0])) / 2 - b2[0], 305 - b2[1]), sub, font=f2, fill=fg)
    return border(im, 'rect')
def comet():
    im = canvas(); d = ImageDraw.Draw(im)
    for k in range(6):
        w = 60 - k * 8; d.line((120 + k * 10, 400 - k * 12, 330, 190), fill=[MINT, BLUE, PLUM][k % 3], width=max(w, 8))
    d.ellipse((290, 120, 420, 250), fill=CREAM); d.ellipse((318, 148, 392, 222), fill=YEL)
    return border(im, 'shape')
def fish():
    im = canvas(); d = ImageDraw.Draw(im)
    d.ellipse((80, 170, 380, 342), fill=MINT); d.polygon([(360, 256), (470, 170), (470, 342)], fill=MINT)
    d.ellipse((140, 220, 180, 260), fill=INK)
    for k in range(3): d.arc((200 + k * 45, 190, 270 + k * 45, 322), 300, 60, fill=BLUE, width=10)
    return border(im, 'shape')

ART = {'ringed_planet': ringed_planet, 'rocket': rocket, 'star_badge': star_badge, 'comet': comet, 'fish': fish,
       'kepler': lambda: text_sticker('KEPLER', 'GIFT SHOP', RED, CREAM), 'zone': lambda: text_sticker('I WAS', 'AT THE EDGE', YEL, INK)}

def sticker_mat(name, img, seed):
    m = bpy.data.materials.new('TR_sticker_' + name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    o = N.new('ShaderNodeOutputMaterial'); b = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); tx = N.new('ShaderNodeTexImage'); tx.image = img; tx.extension = 'CLIP'
    L.new(tc.outputs['UV'], tx.inputs[0])
    # scuffs: fine noise takes small flecks out of the print; a few scratches; corner lift = edge alpha erosion
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 90; nz.inputs['Detail'].default_value = 8
    nz.noise_dimensions = '4D'; nz.inputs['W'].default_value = seed; L.new(tc.outputs['UV'], nz.inputs[0])
    scuff = N.new('ShaderNodeMapRange'); scuff.inputs[1].default_value = 0.66; scuff.inputs[2].default_value = 0.6; L.new(nz.outputs['Fac'], scuff.inputs[0])
    gr = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['UV'], gr.inputs[0])
    # distance to the nearest corner -> the corner nearest the seed peels a little
    cx, cy = (seed * 0.37) % 1 > 0.5, (seed * 0.61) % 1 > 0.5
    v = N.new('ShaderNodeVectorMath'); v.operation = 'DISTANCE'; v.inputs[1].default_value = (1.0 if cx else 0.0, 1.0 if cy else 0.0, 0)
    L.new(tc.outputs['UV'], v.inputs[0])
    peel = N.new('ShaderNodeMapRange'); peel.inputs[1].default_value = 0.12; peel.inputs[2].default_value = 0.2; L.new(v.outputs['Value'], peel.inputs[0])
    a1 = N.new('ShaderNodeMath'); a1.operation = 'MULTIPLY'; L.new(tx.outputs['Alpha'], a1.inputs[0]); L.new(scuff.outputs[0], a1.inputs[1])
    a2 = N.new('ShaderNodeMath'); a2.operation = 'MULTIPLY'; L.new(a1.outputs[0], a2.inputs[0]); L.new(peel.outputs[0], a2.inputs[1])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 6; L.new(tc.outputs['Object'], nz2.inputs[0])
    dirt = N.new('ShaderNodeMix'); dirt.data_type = 'RGBA'; dirt.blend_type = 'MULTIPLY'
    fac = N.new('ShaderNodeMapRange'); fac.inputs[1].default_value = 0.35; fac.inputs[2].default_value = 0.75; fac.inputs[3].default_value = 0.1; fac.inputs[4].default_value = 0.55
    L.new(nz2.outputs['Fac'], fac.inputs[0]); L.new(fac.outputs[0], dirt.inputs[0])
    L.new(tx.outputs['Color'], dirt.inputs[6]); dirt.inputs[7].default_value = (0.42, 0.37, 0.3, 1)
    fade = N.new('ShaderNodeHueSaturation'); fade.inputs['Saturation'].default_value = 0.82; fade.inputs['Value'].default_value = 0.92
    L.new(dirt.outputs[2], fade.inputs['Color'])
    L.new(fade.outputs[0], b.inputs['Base Color']); L.new(a2.outputs[0], b.inputs['Alpha'])
    rough = N.new('ShaderNodeMapRange'); rough.inputs[3].default_value = 0.28; rough.inputs[4].default_value = 0.7; L.new(nz2.outputs['Fac'], rough.inputs[0])
    L.new(rough.outputs[0], b.inputs['Roughness'])
    L.new(b.outputs[0], o.inputs[0])
    return m

SPOTS = [  # art, part, face normal, up, u, v, size (m), tilt (deg)
    ('ringed_planet', 'body_shell', (1, 0, 0), (0, 0, 1), 0.62, 0.418, 0.054, -8),
    ('rocket', 'body_shell', (-1, 0, 0), (0, 0, 1), 0.70, 0.226, 0.058, 6),
    ('kepler', 'bin_lid_plate', (0, 0, 1), (0, -1, 0), 0.62, 0.30, 0.058, -5),
    ('star_badge', 'track_skirt.L', (1, 0, 0), (0, 0, 1), 0.30, 0.55, 0.060, 12),
    ('comet', 'track_skirt.R', (-1, 0, 0), (0, 0, 1), 0.62, 0.55, 0.065, -10),
    ('fish', 'bin_body', (0, 1, 0), (0, 0, 1), 0.25, 0.72, 0.060, 15),
    ('zone', 'chassis_hull', (0, 1, 0), (0, 0, 1), 0.82, 0.55, 0.058, 4),
]
arm['stickers_shown'] = len(SPOTS); arm.id_properties_ui('stickers_shown').update(min=0, max=len(SPOTS), description='Souvenir stickers shown (one more per planet)')
for k, (art, part, n, up, u, v, size, tilt) in enumerate(SPOTS):
    p = os.path.join(IMG, f'sticker_{art}.png'); ART[art]().filter(ImageFilter.GaussianBlur(0.6)).save(p)
    img = bpy.data.images.load(p, check_existing=True); img.pack()
    ob = bpy.data.objects[part]
    t = math.radians(tilt); nn = Vector(n); upv = Vector(up)
    upr = (Matrix.Rotation(t, 3, nn) @ upv)
    M = place(ob, n, tuple(upr), u, v, size, size)
    if M is None: M = place(ob, n, tuple(upv), u, v, size, size)   # untilted if the tilt does not fit
    if M is None: print('STICKER SKIP', art, part); continue
    bpy.ops.mesh.primitive_plane_add(size=1); pl = bpy.context.object; pl.name = f'sticker_{k}_{art}'
    for c in pl.users_collection: c.objects.unlink(pl)
    col.objects.link(pl); pl.data.materials.append(sticker_mat(art, img, k * 1.7 + 0.3))
    pl.visible_shadow = False; pl['rb_decal'] = part; pl['sticker_index'] = k
    pl.parent = ob; pl.matrix_parent_inverse = Matrix.Identity(4)
    pl.matrix_basis = ob.matrix_world.inverted() @ M
    # sticker k shows when stickers_shown > k (the running gag: one more per episode)
    for path in ('hide_render', 'hide_viewport'):
        d = pl.driver_add(path).driver; d.type = 'SCRIPTED'; vv = d.variables.new(); vv.name = 'n'
        vv.targets[0].id = arm; vv.targets[0].data_path = '["stickers_shown"]'; d.expression = f'n <= {k}'
    print('STICKER OK', art, part)
arm.data.pose_position = 'POSE'
bpy.ops.wm.save_as_mainfile(filepath=out)
