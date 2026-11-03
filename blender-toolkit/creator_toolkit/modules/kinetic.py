"""Kinetic type and logo reveals."""
import math
import bpy
from mathutils import Vector
from . import motion
from ..compat import fcurves_of

LABEL, ICON, GROUP = 'Kinetic type + logo reveals', 'FONT_DATA', 'Motion design'
STYLES = [('TYPEWRITER', 'Typewriter', ''), ('SLIDE_UP', 'Slide up', ''), ('POP', 'Pop', ''),
          ('DROP', 'Drop & bounce', ''), ('SPIN_IN', 'Flip in', ''), ('EXTRUDE', '3D extrude reveal', ''),
          ('WAVE', 'Wave (loop)', '')]


def _mat(color):
    name = 'CTK Type %02X%02X%02X' % tuple(int(c * 255) for c in color)
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        if p:
            p.inputs['Base Color'].default_value = (*color, 1)
            p.inputs['Roughness'].default_value = 0.4
        m.diffuse_color = (*color, 1)
    return m


def _measure(context, obj):
    context.view_layer.update()
    return obj.dimensions.x


def build_text(context, text, split, size, font, color, depth):
    root = bpy.data.objects.new('Title', None)
    root.empty_display_type = 'PLAIN_AXES'
    root.location = context.scene.cursor.location
    root.rotation_euler = (math.radians(90), 0, 0)
    context.scene.collection.objects.link(root)
    units = []
    m = _mat(color)
    y = 0.0
    for line in text.split('\\n') if '\\n' in text else text.splitlines() or [text]:
        x = 0.0
        if split == 'LINE':
            parts = [line]
        elif split == 'WORD':
            parts = line.split(' ')
        else:
            parts = list(line)
        space = size * 0.32
        for part in parts:
            if part == ' ' or part == '':
                x += space
                continue
            cu = bpy.data.curves.new(part, 'FONT')
            cu.body = part
            cu.size = size
            cu.extrude = depth
            cu.align_x = 'LEFT'
            if font:
                cu.font = font
            ob = bpy.data.objects.new(part, cu)
            ob.data.materials.append(m)
            context.scene.collection.objects.link(ob)
            ob.parent = root
            ob.location = (x, y, 0)
            w = _measure(context, ob)
            # pivot each unit at its own centre so pops and flips look right
            cu.offset_x = -w / 2
            ob.location.x = x + w / 2
            x += w + (space if split == 'WORD' else size * 0.04)
            units.append(ob)
        # centre the line
        line_units = [u for u in units if abs(u.location.y - y) < 1e-6]
        if line_units:
            shift = x / 2
            for u in line_units:
                u.location.x -= shift
        y -= size * 1.25
    return root, units


def animate_units(units, style, f0, dur, stagger, depth):
    for i, u in enumerate(units):
        s = f0 + i * stagger
        if style == 'TYPEWRITER':
            for a in range(3):
                u.scale[a] = 0
                u.keyframe_insert('scale', index=a, frame=s - 1)
                u.scale[a] = 1
                u.keyframe_insert('scale', index=a, frame=s)
            for fc in fcurves_of(u):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
        elif style == 'SLIDE_UP':
            z = u.location.y
            k = motion.Keys(u)
            k.key('location', 1, s, z - u.data.size * 0.8, 'BACK', 'EASE_OUT')
            k.key('location', 1, s + dur, z)
            for a in range(3):
                k.key('scale', a, s, 0.0, 'CUBIC', 'EASE_OUT')
                k.key('scale', a, s + max(2, dur // 3), 1.0)
            k.finish()
        elif style == 'POP':
            motion.apply(u, 'POP_IN', s, dur)
        elif style == 'DROP':
            k = motion.Keys(u)
            yv = u.location.y
            k.key('location', 1, s, yv + u.data.size * 3, 'BOUNCE', 'EASE_OUT')
            k.key('location', 1, s + dur, yv)
            k.finish()
        elif style == 'SPIN_IN':
            k = motion.Keys(u)
            k.key('rotation_euler', 1, s, math.radians(-90), 'BACK', 'EASE_OUT')
            k.key('rotation_euler', 1, s + dur, 0.0)
            k.finish()
        elif style == 'EXTRUDE':
            cu = u.data
            cu.extrude = 0.0
            cu.keyframe_insert('extrude', frame=s)
            cu.extrude = max(depth, cu.size * 0.15)
            cu.keyframe_insert('extrude', frame=s + dur)
            k = motion.Keys(u)
            k.key('rotation_euler', 0, s, math.radians(-70), 'BACK', 'EASE_OUT')
            k.key('rotation_euler', 0, s + dur, 0.0)
            for a in range(3):
                k.key('scale', a, s, 0.0, 'CUBIC', 'EASE_OUT')
                k.key('scale', a, s + 3, 1.0)
            k.finish()
        elif style == 'WAVE':
            k = motion.Keys(u)
            y = u.location.y
            h = u.data.size * 0.25
            k.key('location', 1, s, y, 'SINE', 'EASE_IN_OUT')
            k.key('location', 1, s + dur // 2, y + h, 'SINE', 'EASE_IN_OUT')
            k.key('location', 1, s + dur, y, 'SINE', 'EASE_IN_OUT')
            k.finish([('location', 1)])


class CTK_OT_kinetic_text(bpy.types.Operator):
    """Create animated text at the 3D cursor, facing the front view"""
    bl_idname = 'ctk.kinetic_text'
    bl_label = 'Animated text'
    bl_options = {'REGISTER', 'UNDO'}
    text: bpy.props.StringProperty(name='Text', default='Hello there')
    split: bpy.props.EnumProperty(name='Animate by', items=[('LETTER', 'Letter', ''), ('WORD', 'Word', ''), ('LINE', 'Line', '')], default='LETTER')
    style: bpy.props.EnumProperty(name='Style', items=STYLES, default='POP')
    size: bpy.props.FloatProperty(name='Size', default=0.5, min=0.01, unit='LENGTH')
    depth: bpy.props.FloatProperty(name='Thickness', default=0.04, min=0.0, unit='LENGTH')
    duration: bpy.props.IntProperty(name='Each one takes (frames)', default=12, min=1)
    stagger: bpy.props.IntProperty(name='Stagger (frames)', default=2, min=0)
    color: bpy.props.FloatVectorProperty(name='Colour', subtype='COLOR', size=3, default=(0.12, 0.12, 0.11), min=0, max=1)
    font_path: bpy.props.StringProperty(name='Font file (optional)', subtype='FILE_PATH')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def execute(self, context):
        font = None
        if self.font_path:
            try:
                font = bpy.data.fonts.load(bpy.path.abspath(self.font_path), check_existing=True)
            except Exception:
                self.report({'WARNING'}, 'Could not load the font; using the default')
        root, units = build_text(context, self.text, self.split, self.size, font, tuple(self.color), self.depth)
        animate_units(units, self.style, context.scene.frame_current, self.duration, self.stagger, self.depth)
        for o in context.selected_objects:
            o.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        self.report({'INFO'}, f'{len(units)} pieces animated. Move or scale the "Title" empty')
        return {'FINISHED'}


class CTK_OT_logo_reveal(bpy.types.Operator):
    """Import an SVG logo and animate its reveal"""
    bl_idname = 'ctk.logo_reveal'
    bl_label = 'Logo reveal from SVG'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.svg', options={'HIDDEN'})
    style: bpy.props.EnumProperty(name='Reveal', items=[('DRAW', 'Draw on, then fill', ''), ('POP', 'Pieces pop in', ''),
                                                       ('EXTRUDE', '3D extrude', ''), ('DROP', 'Pieces drop in', '')])
    width: bpy.props.FloatProperty(name='Width', default=2.0, min=0.01, unit='LENGTH')
    depth: bpy.props.FloatProperty(name='Thickness', default=0.05, min=0, unit='LENGTH')
    duration: bpy.props.IntProperty(name='Length (frames)', default=36, min=4)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import addon_utils
        try:
            addon_utils.enable('io_curve_svg', default_set=True)
        except Exception:
            pass
        before = set(bpy.data.objects)
        try:
            bpy.ops.import_curve.svg(filepath=self.filepath)
        except Exception as e:
            self.report({'WARNING'}, f'SVG import failed: {e}')
            return {'CANCELLED'}
        parts = [o for o in bpy.data.objects if o not in before and o.type == 'CURVE']
        if not parts:
            self.report({'WARNING'}, 'Nothing found in the SVG')
            return {'CANCELLED'}
        reveal_logo(context, parts, self.style, self.width, self.depth, context.scene.frame_current, self.duration)
        return {'FINISHED'}


def reveal_logo(context, parts, style, width, depth, f0, dur):
    context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in parts for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), 0))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), 0))
    s = width / max(hi.x - lo.x, 1e-6)
    root = bpy.data.objects.new('Logo', None)
    root.location = context.scene.cursor.location
    root.rotation_euler = (math.radians(90), 0, 0)
    root.scale = (s, s, s)
    context.scene.collection.objects.link(root)
    c = (lo + hi) / 2
    for o in parts:
        o.parent = root
        o.matrix_parent_inverse.identity()
        o.location = o.location - c
        o.data.extrude = depth / s
        o.data.dimensions = '2D'
    stagger = max(1, dur // (2 * max(len(parts), 1)))
    half = dur // 2
    if style == 'DRAW':
        for i, o in enumerate(parts):
            line = o.copy()
            line.data = o.data.copy()
            context.scene.collection.objects.link(line)
            line.parent = root
            line.data.dimensions = '3D'
            line.data.fill_mode = 'FULL'
            line.data.bevel_depth = 0.01 * width / s
            line.data.extrude = 0
            line.data.bevel_factor_end = 0
            line.data.keyframe_insert('bevel_factor_end', frame=f0 + i * stagger)
            line.data.bevel_factor_end = 1
            line.data.keyframe_insert('bevel_factor_end', frame=f0 + half)
            motion.apply(o, 'POP_IN', f0 + half + i, max(6, dur // 3))
    elif style == 'EXTRUDE':
        for i, o in enumerate(parts):
            o.data.extrude = 0
            o.data.keyframe_insert('extrude', frame=f0 + i * stagger)
            o.data.extrude = depth / s
            o.data.keyframe_insert('extrude', frame=f0 + i * stagger + half)
        k = motion.Keys(root)
        k.key('rotation_euler', 2, f0, math.radians(-35), 'BACK', 'EASE_OUT')
        k.key('rotation_euler', 2, f0 + dur, 0.0)
        k.finish()
    else:
        for i, o in enumerate(parts):
            motion.apply(o, 'POP_IN' if style == 'POP' else 'BOUNCE_IN', f0 + i * stagger, half)
    return root


CLASSES = (CTK_OT_kinetic_text, CTK_OT_logo_reveal)


def draw(layout, context):
    grid = layout.grid_flow(columns=2, align=True)
    for k, label, _ in STYLES:
        op = grid.operator('ctk.kinetic_text', text=label)
        op.style = k
    layout.operator('ctk.logo_reveal', icon='CURVE_BEZCURVE')
