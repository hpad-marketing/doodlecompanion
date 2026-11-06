"""Grease Pencil kit: doodle canvas, ink from 3D, draw-on, line boil, pop-in,
even line weight, colour-in fills (5.2 holes) and onion-skin presets."""
import bpy
from mathutils import Vector
from ..compat import gp_data_new
from . import _util
from .. import uxfit

LABEL, ICON, GROUP = 'Grease Pencil kit', 'GREASEPENCIL', 'Procedural & 2D'

INKS = {'Ink': '#1F1F1D', 'Mustard': '#E0A64B', 'Brick': '#B5523B', 'Teal': '#2F7F7A', 'Sky': '#6FA8DC'}
ONION = {
    'Off': None,
    'Rough (2 each side)': dict(onion_mode='RELATIVE', ghost_before_range=2, ghost_after_range=2, onion_factor=0.4),
    'Spacing check (5 back)': dict(onion_mode='RELATIVE', ghost_before_range=5, ghost_after_range=0, onion_factor=0.3),
    'Every frame (3 each side)': dict(onion_mode='ABSOLUTE', ghost_before_range=3, ghost_after_range=3, onion_factor=0.35),
    'Loop check': dict(onion_mode='RELATIVE', ghost_before_range=1, ghost_after_range=1, onion_factor=0.5,
                       use_onion_loop=True),
}


def gp_material(name, hexcol, stroke=True, fill=False, holdout=False):
    key = 'CTK GP ' + name + (' fill' if fill and not stroke else '') + (' hole' if holdout else '')
    m = bpy.data.materials.get(key)
    if m is None:
        m = bpy.data.materials.new(key)
        bpy.data.materials.create_gpencil_data(m)
    g = m.grease_pencil
    rgb = _util.hex_to_linear(hexcol)
    g.color = (*rgb, 1.0)
    g.fill_color = (*rgb, 1.0)
    g.show_stroke = stroke
    g.show_fill = fill
    g.use_fill_holdout = holdout
    return m


def _mat_index(obj, mat):
    mats = obj.data.materials
    for i, m in enumerate(mats):
        if m == mat:
            return i
    mats.append(mat)
    return len(mats) - 1


def new_canvas(context, name='Doodle', ink='Ink'):
    d = gp_data_new(name)
    o = bpy.data.objects.new(name, d)
    context.scene.collection.objects.link(o)
    o.location = context.scene.cursor.location
    d.layers.new('Lines')
    d.materials.append(gp_material(ink, INKS[ink]))
    return o


def _gp(context):
    o = context.active_object
    return o if o and o.type == 'GREASEPENCIL' else None


def _mod(o, kind, name):
    m = o.modifiers.get(name)
    return m or o.modifiers.new(name, kind)


def draw_on(o, start, length):
    m = _mod(o, 'GREASE_PENCIL_BUILD', 'CTK Draw on')
    m.mode = 'SEQUENTIAL'
    m.transition = 'GROW'
    m.time_mode = 'FRAMES'
    m.start_delay = 0
    m.length = length
    m.use_restrict_frame_range = True
    m.frame_start = start
    m.frame_end = start + length + 10000
    return m


def boil(o, amount, every):
    m = _mod(o, 'GREASE_PENCIL_NOISE', 'CTK Line boil')
    m.factor = amount
    m.factor_strength = 0.0
    m.factor_thickness = amount * 0.6
    m.noise_scale = 0.4
    m.use_random = True
    m.step = max(1, int(every))
    return m


def even_lines(o, width):
    m = _mod(o, 'GREASE_PENCIL_THICKNESS', 'CTK Even line')
    m.use_uniform_thickness = True
    m.thickness = width
    return m


def ink_from_3d(context, source, width, ink):
    d = gp_data_new('Ink outline')
    o = bpy.data.objects.new('Ink outline', d)
    context.scene.collection.objects.link(o)
    layer = d.layers.new('Ink')
    mat = gp_material(ink, INKS[ink])
    d.materials.append(mat)
    m = o.modifiers.new('CTK Line art', 'LINEART')
    if source == 'SELECTED':
        coll = bpy.data.collections.new('Ink sources')
        context.scene.collection.children.link(coll)
        coll.hide_viewport = False
        for ob in [x for x in context.selected_objects if x.type == 'MESH']:
            coll.objects.link(ob)
        m.source_type = 'COLLECTION'
        m.source_collection = coll
    else:
        m.source_type = 'SCENE'
    m.target_layer = layer.name
    m.target_material = mat
    for k in ('thickness', 'radius'):
        if hasattr(m, k):
            setattr(m, k, width if k == 'thickness' else width / 1000.0)
    m.use_crease = True
    m.crease_threshold = 2.4
    return o


# ---------------------------------------------------------- colour-in fills (pick: gpfill)

def _closed(points, tol):
    if len(points) < 3:
        return False
    return (points[0].position - points[-1].position).length <= tol


def _bbox(points):
    xs = [p.position for p in points]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    return lo, hi


def _inside(a, b):
    """Box a inside box b."""
    return all(b[0][i] <= a[0][i] + 1e-6 and a[1][i] <= b[1][i] + 1e-6 for i in range(3))


def fill_shapes(o, colours, holes=True, gap=0.05):
    """Copy every closed line as a fill stroke behind it. Inner shapes become holes:
    5.2 groups them with fill_id; 4.x uses a holdout material."""
    d = o.data
    done = 0
    for layer in d.layers:
        for fr in layer.frames:
            dr = fr.drawing
            strokes = list(dr.strokes)
            shapes = []
            for s in strokes:
                pts = list(s.points)
                if s.cyclic or _closed(pts, gap):
                    shapes.append((s, _bbox(pts), [p.position.copy() for p in pts]))
            if not shapes:
                continue
            parent = {}
            for i, (_, bi, _) in enumerate(shapes):
                outer = [j for j, (_, bj, _) in enumerate(shapes) if j != i and _inside(bi, bj)]
                if outer:
                    parent[i] = min(outer, key=lambda j: (shapes[j][1][1] - shapes[j][1][0]).length)
            n0 = len(dr.strokes)
            dr.add_strokes([len(p) for _, _, p in shapes])
            has_fill_id = hasattr(dr.strokes[0], 'fill_id')
            for i, (src, _, pts) in enumerate(shapes):
                new = dr.strokes[n0 + i]
                for k, co in enumerate(pts):
                    new.points[k].position = co
                    new.points[k].radius = 0.0001
                new.cyclic = True
                depth = 0
                j = i
                while j in parent:
                    depth += 1
                    j = parent[j]
                is_hole = holes and depth % 2 == 1
                root = j
                if is_hole and has_fill_id:
                    new.fill_id = root + 1
                    shapes_root_fill = n0 + root
                    dr.strokes[shapes_root_fill].fill_id = root + 1
                    mat = gp_material('Fill %d' % (root % len(colours)), colours[root % len(colours)], stroke=False,
                                      fill=True)
                elif is_hole:
                    mat = gp_material('Hole', '#000000', stroke=False, fill=True, holdout=True)
                else:
                    mat = gp_material('Fill %d' % (i % len(colours)), colours[i % len(colours)], stroke=False, fill=True)
                new.material_index = _mat_index(o, mat)
                done += 1
            # fills go behind the lines
            try:
                order = list(range(n0, n0 + len(shapes))) + list(range(n0))
                dr.reorder_strokes(order)
            except Exception:
                pass
    return done


def palette_colours(context):
    from . import palette
    kit = palette.kits().get(context.scene.get('ctk_palette', ''), [])
    cols = [c for c in kit if c.upper() != INKS['Ink']]
    if cols:
        return cols
    return ['#E0A64B', '#6FA8DC', '#B5523B', '#2F7F7A', '#9C7BB8']


# ---------------------------------------------------------- operators

class CTK_OT_gp_canvas(bpy.types.Operator):
    """New Grease Pencil drawing with brand ink, ready to draw on"""
    bl_idname = 'ctk.gp_canvas'
    bl_label = 'New doodle'
    bl_options = {'REGISTER', 'UNDO'}
    ink: bpy.props.EnumProperty(items=[(k, k, '') for k in INKS])

    def execute(self, context):
        o = new_canvas(context, ink=self.ink)
        for x in context.selected_objects:
            x.select_set(False)
        o.select_set(True)
        context.view_layer.objects.active = o
        if context.area and context.area.type == 'VIEW_3D':
            try:
                bpy.ops.object.mode_set(mode='PAINT_GREASE_PENCIL')
            except Exception:
                pass
        return {'FINISHED'}


class CTK_OT_gp_effect(bpy.types.Operator):
    """Add a hand-drawn effect to the active Grease Pencil object"""
    bl_idname = 'ctk.gp_effect'
    bl_label = 'Doodle effect'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[('DRAW_ON', 'Draw on', ''), ('BOIL', 'Line boil', ''),
                                        ('POP', 'Pop in', ''), ('EVEN', 'Even line weight', ''),
                                        ('CLEAR', 'Remove effects', '')])
    seconds: bpy.props.FloatProperty(name='Seconds', default=1.0, min=0.05)
    amount: bpy.props.FloatProperty(name='Boil amount', default=0.4, min=0.0, max=5.0)
    every: bpy.props.IntProperty(name='Change every (frames)', default=3, min=1, max=24)
    width: bpy.props.IntProperty(name='Line width', default=6, min=1, max=200)

    def execute(self, context):
        o = _gp(context)
        if not o:
            self.report({'ERROR'}, 'Select a Grease Pencil object')
            return {'CANCELLED'}
        sc = context.scene
        fps = sc.render.fps / sc.render.fps_base
        if self.kind == 'DRAW_ON':
            draw_on(o, sc.frame_current, max(1, int(self.seconds * fps)))
        elif self.kind == 'BOIL':
            boil(o, self.amount, self.every)
        elif self.kind == 'EVEN':
            even_lines(o, self.width)
        elif self.kind == 'POP':
            from . import motion
            motion.apply(o, 'POP_IN', sc.frame_current, max(2, int(self.seconds * fps)), 1.0, 0)
        else:
            for m in list(o.modifiers):
                if m.name.startswith('CTK '):
                    o.modifiers.remove(m)
        return {'FINISHED'}


class CTK_OT_gp_ink3d(bpy.types.Operator):
    """Draw ink lines around 3D models (Line Art) in brand ink"""
    bl_idname = 'ctk.gp_ink3d'
    bl_label = 'Ink outline from 3D'
    bl_options = {'REGISTER', 'UNDO'}
    source: bpy.props.EnumProperty(items=[('SCENE', 'Whole scene', ''), ('SELECTED', 'Selected models', '')])
    width: bpy.props.IntProperty(name='Line width', default=4, min=1, max=100)
    ink: bpy.props.EnumProperty(items=[(k, k, '') for k in INKS])

    def execute(self, context):
        if not context.scene.camera:
            self.report({'ERROR'}, 'Add a camera first: Line Art draws what the camera sees')
            return {'CANCELLED'}
        ink_from_3d(context, self.source, self.width, self.ink)
        return {'FINISHED'}


class CTK_OT_gp_fill(bpy.types.Operator):
    """Fill every closed shape with palette colours; shapes inside shapes become holes"""
    bl_idname = 'ctk.gp_fill'
    bl_label = 'Colour in'
    bl_options = {'REGISTER', 'UNDO'}
    holes: bpy.props.BoolProperty(name='Inner shapes are holes', default=True)
    gap: bpy.props.FloatProperty(name='Close gaps up to', default=0.05, min=0.0, max=1.0, unit='LENGTH')

    def execute(self, context):
        o = _gp(context)
        if not o:
            self.report({'ERROR'}, 'Select a Grease Pencil object')
            return {'CANCELLED'}
        n = fill_shapes(o, palette_colours(context), self.holes, self.gap)
        self.report({'INFO'}, f'Filled {n} shapes' if n else 'No closed shapes found (close the line or raise the gap)')
        return {'FINISHED'}


class CTK_OT_gp_onion(bpy.types.Operator):
    """Onion-skin presets for 2D animation"""
    bl_idname = 'ctk.gp_onion'
    bl_label = 'Onion skin'
    preset: bpy.props.EnumProperty(items=[(k, k, '') for k in ONION])

    def execute(self, context):
        o = _gp(context)
        if not o:
            self.report({'ERROR'}, 'Select a Grease Pencil object')
            return {'CANCELLED'}
        cfg = ONION[self.preset]
        d = o.data
        if cfg is None:
            d.onion_factor = 0.0
            for layer in d.layers:
                if hasattr(layer, 'use_onion_skinning'):
                    layer.use_onion_skinning = False
            return {'FINISHED'}
        for k, v in cfg.items():
            if hasattr(d, k):
                setattr(d, k, v)
        d.use_ghost_custom_colors = True
        d.before_color = (0.85, 0.35, 0.25)
        d.after_color = (0.25, 0.55, 0.85)
        for layer in d.layers:
            if hasattr(layer, 'use_onion_skinning'):
                layer.use_onion_skinning = True
        if context.space_data and hasattr(context.space_data, 'overlay'):
            context.space_data.overlay.use_gpencil_onion_skin = True
        return {'FINISHED'}


CLASSES = (CTK_OT_gp_canvas, CTK_OT_gp_effect, CTK_OT_gp_ink3d, CTK_OT_gp_fill, CTK_OT_gp_onion)


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('ctk.gp_canvas', icon='GREASEPENCIL')
    row.operator('ctk.gp_ink3d', icon='MOD_LINEART')
    o = _gp(context)
    if not o:
        uxfit.wrap(layout, context, 'Select a drawing for effects and fills')
        return
    g = uxfit.flow(layout, context, [str(_t[1]) for _t in (('DRAW_ON', 'Draw on'), ('BOIL', 'Line boil'), ('POP', 'Pop in'), ('EVEN', 'Even lines'))], most=2)
    for k, l in (('DRAW_ON', 'Draw on'), ('BOIL', 'Line boil'), ('POP', 'Pop in'), ('EVEN', 'Even lines')):
        g.operator('ctk.gp_effect', text=l).kind = k
    row = layout.row(align=True)
    row.operator('ctk.gp_fill', icon='MOD_PARTICLE_INSTANCE')
    row.operator_menu_enum('ctk.gp_onion', 'preset', text='Onion skin')
    layout.operator('ctk.gp_effect', text='Remove effects', icon='X').kind = 'CLEAR'
