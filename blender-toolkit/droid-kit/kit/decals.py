"""Stencil decals: PIL-drawn images on thin planes 0.5 mm off a FLAT face, parented to the part (no rig_bone, so the
collision check ignores them). Each spot is raycast-checked at rest: every sample must hit the target part on one plane.
python3 decals.py in.blend out.blend imgdir"""
import bpy, sys, os, math
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFont, ImageFilter
blend, out, IMG = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=blend)
FONT = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
FONT2 = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'

def fit_font(d, text, path, w, h):
    s = int(h)
    while s > 6:
        f = ImageFont.truetype(path, s); b = d.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= w and b[3] - b[1] <= h: return f, b
        s -= 2
    return f, b

def text_img(name, lines, aspect, px=1024):
    """lines: [(text, share_of_height, font)] stacked; white on transparent, slight overspray"""
    W = px; H = max(8, int(px / aspect)); im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    y = 0.06 * H
    for text, share, path in lines:
        hh = share * H * 0.88
        f, b = fit_font(d, text, path, W * 0.92, hh)
        d.text(((W - (b[2] - b[0])) / 2 - b[0], y - b[1] + (hh - (b[3] - b[1])) / 2), text, font=f, fill=255)
        y += share * H * 0.94
    return save(name, im)

def chevron_img(name, aspect, px=1024):
    W = px; H = int(px / aspect); im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    n = 3; step = W / n; t = step * 0.26
    for i in range(n):
        x0 = i * step + step * 0.12
        # chevron pointing UP (texture up = forward)
        pts = [(x0, H * 0.82), (x0 + step * 0.38, H * 0.18), (x0 + step * 0.76, H * 0.82),
               (x0 + step * 0.76 - t, H * 0.82), (x0 + step * 0.38, H * 0.18 + t * 1.7), (x0 + t, H * 0.82)]
        d.polygon(pts, fill=255)
    return save(name, im)

def box_letter(name, ch, px=512):
    im = Image.new('L', (px, px), 0); d = ImageDraw.Draw(im)
    d.rectangle((px * 0.06, px * 0.06, px * 0.94, px * 0.94), outline=255, width=int(px * 0.07))
    f, b = fit_font(d, ch, FONT, px * 0.6, px * 0.6)
    d.text(((px - (b[2] - b[0])) / 2 - b[0], (px - (b[3] - b[1])) / 2 - b[1]), ch, font=f, fill=255)
    return save(name, im)

def save(name, im):
    im = im.filter(ImageFilter.GaussianBlur(1.2))           # sprayed edge, not a vector cut
    rgba = Image.merge('RGBA', [Image.new('L', im.size, 255)] * 3 + [im])
    p = os.path.join(IMG, name + '.png'); rgba.save(p)
    img = bpy.data.images.load(p, check_existing=True); img.pack(); return img

def decal_mat(name, img, colour):
    m = bpy.data.materials.new('RB_decal_' + name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    o = N.new('ShaderNodeOutputMaterial'); b = N.new('ShaderNodeBsdfPrincipled')
    tc = N.new('ShaderNodeTexCoord'); tx = N.new('ShaderNodeTexImage'); tx.image = img; tx.extension = 'CLIP'
    L.new(tc.outputs['UV'], tx.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 60; nz.inputs['Detail'].default_value = 10
    nz.inputs['Roughness'].default_value = 0.7; L.new(tc.outputs['Object'], nz.inputs[0])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 7; L.new(tc.outputs['Object'], nz2.inputs[0])
    chip = N.new('ShaderNodeMapRange'); chip.inputs[1].default_value = 0.6; chip.inputs[2].default_value = 0.52
    L.new(nz.outputs['Fac'], chip.inputs[0])                                      # 1 = paint stays, 0 = flaked
    fade = N.new('ShaderNodeMapRange'); fade.inputs[1].default_value = 0.3; fade.inputs[2].default_value = 0.7
    fade.inputs[3].default_value = 0.95; fade.inputs[4].default_value = 0.55; L.new(nz2.outputs['Fac'], fade.inputs[0])
    a1 = N.new('ShaderNodeMath'); a1.operation = 'MULTIPLY'; L.new(tx.outputs['Alpha'], a1.inputs[0]); L.new(chip.outputs[0], a1.inputs[1])
    a2 = N.new('ShaderNodeMath'); a2.operation = 'MULTIPLY'; L.new(a1.outputs[0], a2.inputs[0]); L.new(fade.outputs[0], a2.inputs[1])
    dirt = N.new('ShaderNodeMix'); dirt.data_type = 'RGBA'; dirt.blend_type = 'MULTIPLY'
    dirt.inputs[6].default_value = colour; dirt.inputs[7].default_value = (0.55, 0.5, 0.42, 1)
    L.new(nz2.outputs['Fac'], dirt.inputs[0])
    L.new(dirt.outputs[2], b.inputs['Base Color']); L.new(a2.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.62
    L.new(b.outputs[0], o.inputs[0])
    return m

# ---------------------------------------------------------------- placement
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.data.pose_position = 'REST'; bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); scene = bpy.context.scene

def frame(n, up):
    n = n.normalized(); up = (up - n * up.dot(n)).normalized(); right = (-n).cross(up)
    return right, up

def try_spot(ob, c, n, up, w, h):
    """c: world centre on the face. returns plane world matrix or None"""
    right, upv = frame(n, up)
    hits = []
    for i in range(5):
        for j in range(5):
            p = c + right * w * (i / 4 - 0.5) + upv * h * (j / 4 - 0.5)
            ok, loc, nor, idx, hob, _ = scene.ray_cast(dg, p + n * 0.25, -n, distance=0.4)
            if not ok or hob.name != ob.name or nor.dot(n) < 0.998: return None
            hits.append(loc)
    plane_d = [(h_ - c).dot(n) for h_ in hits]
    if max(plane_d) - min(plane_d) > 0.0006: return None
    base = c + n * (sum(plane_d) / len(plane_d) + 0.0005)
    M = Matrix((right * w, upv * h, n)).transposed().to_4x4(); M.translation = base
    return M

def place(ob, approach, up, u, v, w, h, search=True):
    """approach: world dir of the face normal; u,v: preferred spot as fraction of the face's bbox"""
    ok, loc, nor, *_ = None, None, None
    cs = [ob.matrix_world @ Vector(x) for x in ob.bound_box]
    n0 = Vector(approach).normalized(); r0, u0 = frame(n0, Vector(up))
    rs = [p.dot(r0) for p in cs]; us = [p.dot(u0) for p in cs]; ns = [p.dot(n0) for p in cs]
    def world(uu, vv):
        return r0 * (min(rs) + uu * (max(rs) - min(rs))) + u0 * (min(us) + vv * (max(us) - min(us))) + n0 * max(ns)
    cands = [(0, 0)] + ([(dx, dy) for dx in (-0.2, -0.1, 0, 0.1, 0.2) for dy in (-0.2, -0.1, 0, 0.1, 0.2)] if search else [])
    cands.sort(key=lambda d: d[0] ** 2 + d[1] ** 2)
    for dx, dy in cands:
        p = world(u + dx, v + dy)
        hit, loc, nor, idx, hob, _ = scene.ray_cast(dg, p + n0 * 0.25, -n0, distance=0.5)
        if not hit or hob.name != ob.name: continue
        M = try_spot(ob, loc, nor, Vector(up), w, h)
        if M: return M
    return None

col = bpy.data.collections.get('Decals') or bpy.data.collections.new('Decals')
if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
CREAM = (0.72, 0.68, 0.56, 1); YEL = (0.78, 0.55, 0.06, 1); WHITE = (0.8, 0.79, 0.74, 1)

def decal(name, part, approach, up, u, v, w, h, img, colour):
    ob = bpy.data.objects[part]
    M = place(ob, approach, up, u, v, w, h)
    if M is None: print('DECAL SKIP', name, part); return None
    bpy.ops.mesh.primitive_plane_add(size=1); pl = bpy.context.object; pl.name = 'decal_' + name
    for c in pl.users_collection: c.objects.unlink(pl)
    col.objects.link(pl)
    pl.data.materials.append(decal_mat(name, img, colour))
    pl.visible_shadow = False; pl['rb_decal'] = part
    pl.parent = ob; pl.matrix_parent_inverse = Matrix.Identity(4)
    pl.matrix_basis = ob.matrix_world.inverted() @ M
    print('DECAL OK', name, part, [round(x, 3) for x in M.translation])
    return pl

import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import kit
FONTS = {'bold': FONT, 'mono': FONT2}
COLS = {'cream': CREAM, 'yellow': YEL, 'white': WHITE}
for d in kit.get('decals', []):
    for S in (d.get('sides') or ['']):
        f = lambda t: t.replace('{S}', S)
        w, h = d['size']
        if d['kind'] == 'text': img = text_img(f(d['name']), [(f(t), sh, FONTS[fn]) for t, sh, fn in d['lines']], w / h)
        elif d['kind'] == 'chevrons': img = chevron_img(f(d['name']), w / h)
        else: img = box_letter(f(d['name']), f(d['letter']))
        col_ = COLS.get(d.get('colour'), CREAM) if isinstance(d.get('colour'), str) else tuple(d['colour'])
        decal(f(d['name']), f(d['part']), tuple(d['normal']), tuple(d['up']), d['uv'][0], d['uv'][1], w, h, img, col_)
arm.data.pose_position = 'POSE'
bpy.ops.wm.save_as_mainfile(filepath=out)
