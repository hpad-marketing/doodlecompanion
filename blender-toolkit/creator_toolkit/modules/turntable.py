"""Turntables, clay renders and portfolio contact sheets."""
import math
import os
import bpy
from mathutils import Vector
from . import _util

LABEL, ICON, GROUP = 'Turntable + portfolio', 'FILE_REFRESH', 'Output'
PIVOT = 'CTK Turntable'


def _bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _linear(obj):
    from ..compat import fcurves_of
    for fc in fcurves_of(obj):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
        fc.extrapolation = 'LINEAR'


def make(context, seconds=6.0, mode='ORBIT', elevation=15.0, lens=50.0):
    sc = context.scene
    objs = [o for o in context.selected_objects if o.type in ('MESH', 'CURVE', 'FONT', 'EMPTY', 'ARMATURE')] \
        or [o for o in sc.objects if o.type == 'MESH']
    if not objs:
        raise RuntimeError('Nothing to turn: add or select a model')
    lo, hi = _bounds(objs)
    centre = (lo + hi) / 2
    size = max((hi - lo).length, 0.1)
    fps = sc.render.fps / sc.render.fps_base
    frames = max(2, int(round(seconds * fps)))
    old = bpy.data.objects.get(PIVOT)
    if old:
        bpy.data.objects.remove(old)
    piv = bpy.data.objects.new(PIVOT, None)
    piv.empty_display_type = 'CIRCLE'
    piv.empty_display_size = size * 0.6
    piv.location = (centre.x, centre.y, lo.z)
    sc.collection.objects.link(piv)
    cam = sc.camera
    if cam is None or cam.get('ctk_turntable'):
        if cam is None:
            cd = bpy.data.cameras.new('Turntable cam')
            cam = bpy.data.objects.new('Turntable cam', cd)
            sc.collection.objects.link(cam)
            sc.camera = cam
    cam['ctk_turntable'] = 1
    cam.data.lens = lens
    fov = cam.data.angle
    dist = size * 0.6 / math.tan(fov / 2) + size * 0.3
    e = math.radians(elevation)
    look = Vector((0, 0, (hi.z - lo.z) / 2))
    if mode == 'ORBIT':
        cam.parent = piv
        cam.location = look + Vector((0, -dist * math.cos(e), dist * math.sin(e)))
        spinner = piv
    else:
        cam.parent = None
        cam.location = piv.location + look + Vector((0, -dist * math.cos(e), dist * math.sin(e)))
        for o in objs:
            if o.parent is None:
                mw = o.matrix_world.copy()
                o.parent = piv
                o.matrix_parent_inverse = piv.matrix_world.inverted()
                o.matrix_world = mw
        spinner = piv
    tr = cam.constraints.get('CTK Aim') or cam.constraints.new('TRACK_TO')
    tr.name = 'CTK Aim'
    aim = bpy.data.objects.get('CTK Turntable aim') or bpy.data.objects.new('CTK Turntable aim', None)
    if aim.name not in sc.collection.objects:
        sc.collection.objects.link(aim)
    aim.location = piv.location + look
    tr.target = aim
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    f0 = sc.frame_start
    spinner.rotation_euler = (0, 0, 0)
    spinner.keyframe_insert('rotation_euler', index=2, frame=f0)
    spinner.rotation_euler.z = math.tau if mode == 'ORBIT' else -math.tau
    spinner.keyframe_insert('rotation_euler', index=2, frame=f0 + frames)
    _linear(spinner)
    sc.frame_end = f0 + frames - 1  # last frame != first frame: seamless loop
    return piv, cam


def clay(scene, on=True, colour='#B9B4AA'):
    vl = bpy.context.view_layer
    if not on:
        vl.material_override = None
        return
    m = bpy.data.materials.get('CTK Clay') or bpy.data.materials.new('CTK Clay')
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*_util.hex_to_linear(colour), 1)
    b.inputs['Roughness'].default_value = 0.75
    vl.material_override = m


def contact_sheet(paths, out_path, columns=4, gap=16, bg='#1F1F1D'):
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p, check_existing=False)
        w, h = im.size
        px = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(px)
        imgs.append(px.reshape(h, w, 4))
        bpy.data.images.remove(im)
    if not imgs:
        raise RuntimeError('No images')
    ch = max(i.shape[0] for i in imgs)
    cw = max(i.shape[1] for i in imgs)
    rows = math.ceil(len(imgs) / columns)
    W = columns * cw + (columns + 1) * gap
    H = rows * ch + (rows + 1) * gap
    sheet = np.empty((H, W, 4), dtype=np.float32)
    sheet[:] = (*_util.hex_to_linear(bg), 1.0)
    for i, im in enumerate(imgs):
        r, c = divmod(i, columns)
        y = H - (r + 1) * (ch + gap)  # Blender pixels start bottom-left: first image top-left
        x = gap + c * (cw + gap)
        sheet[y:y + im.shape[0], x:x + im.shape[1]] = im
    out = bpy.data.images.new('CTK contact sheet', W, H, alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    return out_path


def render_angles(context, folder, count=8):
    sc = context.scene
    piv = bpy.data.objects.get(PIVOT)
    if not piv:
        make(context)
    os.makedirs(folder, exist_ok=True)
    paths = []
    f0, f1 = sc.frame_start, sc.frame_end
    keep = sc.render.filepath
    im = sc.render.image_settings
    keep_fmt = im.file_format
    if hasattr(im, 'media_type'):
        im.media_type = 'IMAGE'
    im.file_format = 'PNG'
    for i in range(count):
        f = f0 + int((f1 - f0 + 1) * i / count)
        sc.frame_set(f)
        p = os.path.join(folder, 'angle_%02d.png' % (i + 1))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    sc.render.filepath = keep
    try:
        im.file_format = keep_fmt
    except Exception:
        pass
    return paths


class CTK_OT_turntable(bpy.types.Operator):
    """Spin the selection (or orbit the camera) for a seamless looping turntable"""
    bl_idname = 'ctk.turntable'
    bl_label = 'Make turntable'
    bl_options = {'REGISTER', 'UNDO'}
    seconds: bpy.props.FloatProperty(name='Seconds per turn', default=6.0, min=0.5, max=120)
    mode: bpy.props.EnumProperty(items=[('ORBIT', 'Camera orbits', ''), ('SPIN', 'Model spins', '')])
    elevation: bpy.props.FloatProperty(name='Camera height (degrees)', default=15, min=-80, max=89)
    lens: bpy.props.FloatProperty(name='Lens (mm)', default=50, min=10, max=300)

    def execute(self, context):
        try:
            make(context, self.seconds, self.mode, self.elevation, self.lens)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class CTK_OT_clay(bpy.types.Operator):
    """Clay render: every object in one matte grey (switch off to get your materials back)"""
    bl_idname = 'ctk.clay'
    bl_label = 'Clay look'
    on: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        clay(context.scene, self.on)
        return {'FINISHED'}


class CTK_OT_contact_sheet(bpy.types.Operator):
    """Render 8 angles of the turntable and lay them out on one portfolio sheet"""
    bl_idname = 'ctk.contact_sheet'
    bl_label = 'Contact sheet'
    count: bpy.props.IntProperty(name='Angles', default=8, min=2, max=36)
    columns: bpy.props.IntProperty(name='Columns', default=4, min=1, max=12)
    folder: bpy.props.StringProperty(name='Images folder (optional)', subtype='DIR_PATH',
                                     description='Use existing images instead of rendering angles')

    def execute(self, context):
        from . import deliver
        proj, name = deliver.project_dir(context.scene)
        work = os.path.join(proj, 'work', 'sheet')
        if self.folder:
            src = bpy.path.abspath(self.folder)
            paths = sorted(os.path.join(src, f) for f in os.listdir(src)
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.exr')))
        else:
            paths = render_angles(context, work, self.count)
        out = contact_sheet(paths, os.path.join(proj, name + '_sheet.png'), self.columns)
        self.report({'INFO'}, 'Sheet: ' + out)
        return {'FINISHED'}


CLASSES = (CTK_OT_turntable, CTK_OT_clay, CTK_OT_contact_sheet)


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('ctk.turntable', text='Orbit', icon='CON_CAMERASOLVER').mode = 'ORBIT'
    row.operator('ctk.turntable', text='Spin model', icon='FILE_REFRESH').mode = 'SPIN'
    row = layout.row(align=True)
    on = context.view_layer.material_override is not None
    row.operator('ctk.clay', text='Clay off' if on else 'Clay look', icon='SHADING_SOLID').on = not on
    row.operator('ctk.contact_sheet', icon='IMGDISPLAY')
