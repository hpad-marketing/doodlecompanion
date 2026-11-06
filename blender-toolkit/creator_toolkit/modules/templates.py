"""Starter scenes: product shot, motion graphics 16:9 and 9:16 (IG safe zone), isometric,
curved backdrop stage. Save any scene as your own template and start from it later."""
import math
import os
import bpy
from mathutils import Vector
from . import _util
from .. import uxfit

LABEL, ICON, GROUP = 'Starter templates', 'SCENE_DATA', 'Output'

KINDS = [
    ('PRODUCT', 'Product shot', 'Curved backdrop, studio lights, 85 mm camera'),
    ('MOTION_16x9', 'Motion graphics 16:9', 'Flat front camera, 1920x1080, 30 fps'),
    ('REEL_9x16', 'Social reel 9:16', '1080x1920, 30 fps, with the Instagram safe zone shown'),
    ('ISOMETRIC', 'Isometric', 'True isometric orthographic camera'),
    ('STAGE', 'Curved stage (mustard)', 'Curved mustard backdrop like the Doodle 3D look'),
]
BACKDROP = {'PRODUCT': '#8D877C', 'STAGE': '#E0A64B', 'ISOMETRIC': '#C9B48F', 'MOTION_16x9': '#2D3047',
            'REEL_9x16': '#2D3047'}
# IG reel UI covers about 14% top and 35% bottom; 6% on the sides
SAFE = dict(top=0.14, bottom=0.35, side=0.06)


def _mat(name, hexcol, emit=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    col = (*_util.hex_to_linear(hexcol), 1)
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = 0.85
    if emit:
        b.inputs['Emission Color' if 'Emission Color' in b.inputs else 'Emission'].default_value = col
        b.inputs['Emission Strength'].default_value = 1.0
    return m


def backdrop(sc, colour, size=12.0):
    """Floor that curves up into a wall: no horizon line."""
    import bmesh
    me = bpy.data.meshes.new('Backdrop')
    bm = bmesh.new()
    prof = []
    r = size * 0.25
    for i in range(0, 11):
        y = -size / 2 + i * (size / 2 - r) / 10
        prof.append((y, 0.0))
    for i in range(1, 13):
        a = i / 12 * (math.pi / 2)
        prof.append((size / 2 - r + r * math.sin(a), r - r * math.cos(a)))
    for i in range(1, 9):
        prof.append((size / 2, r + i * size * 0.6 / 8))
    rows = []
    for x in (-size, size):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for j in range(len(prof) - 1):
        bm.faces.new((rows[0][j], rows[1][j], rows[1][j + 1], rows[0][j + 1]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new('Backdrop', me)
    sc.collection.objects.link(o)
    o.data.materials.append(_mat('CTK Backdrop ' + colour, colour))
    o['ctk_role'] = 'background'
    return o


def _camera(sc, name, loc, rot, lens=50, ortho=None):
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = [math.radians(a) for a in rot]
    cd.lens = lens
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    sc.camera = cam
    return cam


def safe_zone(sc, cam):
    """Wire frame inside the camera view marking where captions and faces stay clear of the IG UI.
    Never renders."""
    w, h = sc.render.resolution_x, sc.render.resolution_y
    me = bpy.data.meshes.new('IG safe zone')
    ar = w / h
    d = 1.0
    if cam.data.type == 'ORTHO':
        fw = cam.data.ortho_scale
    else:
        fw = 2 * d * math.tan(cam.data.angle / 2) if ar >= 1 else 2 * d * math.tan(cam.data.angle / 2) * ar
    fh = fw / ar
    l, r = -fw / 2 + fw * SAFE['side'], fw / 2 - fw * SAFE['side']
    t, b = fh / 2 - fh * SAFE['top'], -fh / 2 + fh * SAFE['bottom']
    vs = [(l, b, -d), (r, b, -d), (r, t, -d), (l, t, -d)]
    me.from_pydata(vs, [(0, 1), (1, 2), (2, 3), (3, 0)], [])
    o = bpy.data.objects.new('IG safe zone', me)
    sc.collection.objects.link(o)
    o.parent = cam
    o.hide_render = True
    o.hide_select = True
    o.display_type = 'WIRE'
    o.show_in_front = True
    return o


def build(context, kind):
    sc = bpy.data.scenes.new(dict((k, l) for k, l, _ in KINDS)[kind])
    if context.window:
        context.window.scene = sc
    r = sc.render
    r.fps = 30
    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg:
        bg.inputs[0].default_value = (*_util.hex_to_linear(BACKDROP[kind]), 1)
        bg.inputs[1].default_value = 0.6
    if kind in ('PRODUCT', 'STAGE'):
        r.resolution_x, r.resolution_y = (1920, 1080) if kind == 'PRODUCT' else (1080, 1920)
        backdrop(sc, BACKDROP[kind])
        cam = _camera(sc, 'Camera', (0, -9, 1.4), (84, 0, 0), lens=85 if kind == 'PRODUCT' else 40)
        if kind == 'STAGE':
            cam.location = (0, -7, 1.1)
            safe_zone(sc, cam)
        _placeholder(sc, kind)
        _lights(context, sc, 'Studio product' if kind == 'PRODUCT' else 'Soft window')
    elif kind == 'MOTION_16x9':
        r.resolution_x, r.resolution_y = 1920, 1080
        _camera(sc, 'Camera', (0, -10, 0), (90, 0, 0), ortho=16)
        _plate(sc, 16, 9)
    elif kind == 'REEL_9x16':
        r.resolution_x, r.resolution_y = 1080, 1920
        cam = _camera(sc, 'Camera', (0, -10, 0), (90, 0, 0), ortho=9)
        _plate(sc, 9, 16)
        safe_zone(sc, cam)
    elif kind == 'ISOMETRIC':
        r.resolution_x, r.resolution_y = 1080, 1350
        _camera(sc, 'Camera', (10, -10, 10 * math.sqrt(2) * math.tan(math.radians(35.264))),
                (90 - 35.264, 0, 45), ortho=10)
        backdrop(sc, BACKDROP[kind], 20)
        _placeholder(sc, kind)
        _lights(context, sc, 'Flat illustration')
    sc.frame_start, sc.frame_end = 1, 150
    return sc


def _plate(sc, w, h):
    me = bpy.data.meshes.new('Background plate')
    me.from_pydata([(-w / 2, 1, -h / 2), (w / 2, 1, -h / 2), (w / 2, 1, h / 2), (-w / 2, 1, h / 2)], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new('Background plate', me)
    sc.collection.objects.link(o)
    o.data.materials.append(_mat('CTK Plate', BACKDROP['MOTION_16x9'], emit=True))
    o['ctk_role'] = 'background'


def _placeholder(sc, kind):
    me = bpy.data.meshes.new('Hero placeholder')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.6)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.6))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new('Hero (replace me)', me)
    sc.collection.objects.link(o)
    o.data.materials.append(_mat('CTK Hero', '#1F1F1D' if kind == 'STAGE' else '#5C80BC'))
    o['ctk_role'] = 'main'
    return o


def _lights(context, sc, preset):
    from . import lights
    win = context.window
    try:
        if win:
            win.scene = sc
        with context.temp_override(scene=sc) if hasattr(context, 'temp_override') else _nullctx():
            lights.build_rig(bpy.context, preset)
    except Exception:
        pass


class _nullctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---------------------------------------------------------- my templates

def my_dir():
    d = os.path.join(_util.vault_dir(), 'Templates')
    os.makedirs(d, exist_ok=True)
    return d


def my_templates():
    return sorted(f[:-6] for f in os.listdir(my_dir()) if f.endswith('.blend'))


def save_mine(scene, name):
    import re
    path = os.path.join(my_dir(), (re.sub(r'[\\/:*?"<>|]+', '_', name).strip() or 'Template') + '.blend')
    bpy.data.libraries.write(path, {scene}, fake_user=True, compress=True)
    return path


def load_mine(name):
    path = os.path.join(my_dir(), name + '.blend')
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.scenes = list(src.scenes[:1])
    return dst.scenes[0]


def _mine_items(self, context):
    items = [(n, n, '') for n in my_templates()]
    return items or [('', 'No templates saved yet', '')]


class CTK_OT_template_new(bpy.types.Operator):
    """Start a new scene from a ready-made template"""
    bl_idname = 'ctk.template_new'
    bl_label = 'New from template'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=KINDS)

    def execute(self, context):
        sc = build(context, self.kind)
        if context.window:
            context.window.scene = sc
        self.report({'INFO'}, f'New scene: {sc.name}')
        return {'FINISHED'}


class CTK_OT_template_save(bpy.types.Operator):
    """Save this whole scene as one of your templates"""
    bl_idname = 'ctk.template_save'
    bl_label = 'Save as my template'
    name: bpy.props.StringProperty(name='Name')

    def invoke(self, context, event):
        self.name = self.name or context.scene.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        p = save_mine(context.scene, self.name or context.scene.name)
        self.report({'INFO'}, 'Saved ' + p)
        return {'FINISHED'}


class CTK_OT_template_load(bpy.types.Operator):
    """Start a new scene from one of your templates"""
    bl_idname = 'ctk.template_load'
    bl_label = 'My templates'
    bl_property = 'name'
    name: bpy.props.EnumProperty(items=_mine_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.name:
            return {'CANCELLED'}
        sc = load_mine(self.name)
        if context.window:
            context.window.scene = sc
        return {'FINISHED'}


CLASSES = (CTK_OT_template_new, CTK_OT_template_save, CTK_OT_template_load)


def draw(layout, context):
    g = uxfit.flow(layout, context, [str(_t[1]) for _t in KINDS], most=2)
    for k, l, _ in KINDS:
        g.operator('ctk.template_new', text=l).kind = k
    row = uxfit.flow(layout, context, ['Save as my template', 'My templates'], most=2, icon=True)
    row.operator('ctk.template_save', icon='FILE_TICK')
    row.operator('ctk.template_load', icon='FILE_FOLDER')
