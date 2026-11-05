"""Light rigs in one click, plus a list of every light (Gaffer-style)."""
import math
import bpy
from mathutils import Vector
from .. import uxfit

LABEL, ICON, GROUP = 'Light rigs', 'LIGHT', 'Look'
RIG = 'CTK Light Rig'
# name: list of (type, azimuth deg, elevation deg, distance, energy W, colour, size)
PRESETS = {
    'Studio product': [('AREA', -45, 35, 4, 400, (1, 0.98, 0.95), 2.5), ('AREA', 60, 20, 5, 150, (0.95, 0.97, 1), 3),
                       ('AREA', 180, 45, 4, 250, (1, 1, 1), 1.5)],
    'Three-point': [('AREA', -40, 35, 4, 500, (1, 0.96, 0.9), 1.0), ('AREA', 50, 15, 5, 150, (0.9, 0.95, 1), 2.0),
                    ('SPOT', 170, 40, 4, 600, (1, 1, 1), 0.2)],
    'Rim-lit hero': [('AREA', -30, 20, 4, 120, (1, 0.95, 0.9), 2), ('AREA', 150, 25, 3.5, 800, (1, 0.85, 0.6), 0.6),
                     ('AREA', -150, 25, 3.5, 800, (0.6, 0.8, 1), 0.6)],
    'Soft window': [('AREA', -70, 25, 4, 700, (0.95, 0.97, 1), 4), ('AREA', 100, 10, 6, 60, (1, 0.95, 0.9), 5)],
    'Golden hour': [('SUN', -60, 8, 1, 4, (1, 0.7, 0.4), 2), ('AREA', 110, 30, 6, 120, (0.6, 0.7, 1), 5)],
    'Neon night': [('AREA', -90, 15, 3, 500, (1, 0.2, 0.7), 1.5), ('AREA', 90, 15, 3, 500, (0.2, 0.6, 1), 1.5),
                   ('AREA', 180, 50, 4, 200, (0.6, 0.3, 1), 1)],
    'Flat illustration': [('SUN', -30, 60, 1, 2.5, (1, 1, 1), 30), ('SUN', 150, 40, 1, 1.2, (1, 1, 1), 30)],
}


def target_point(context):
    sel = [o for o in context.selected_objects if o.type in ('MESH', 'CURVE', 'FONT', 'ARMATURE')]
    if not sel:
        return context.scene.cursor.location.copy(), 1.0
    pts = [o.matrix_world @ Vector(c) for o in sel for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, max((hi - lo).length / 2, 0.3)


def remove_rig(context):
    old = bpy.data.objects.get(RIG)
    if old:
        for c in list(old.children):
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(old)


def build_rig(context, name):
    remove_rig(context)
    center, radius = target_point(context)
    root = bpy.data.objects.new(RIG, None)
    root.empty_display_type = 'CIRCLE'
    root.empty_display_size = radius * 1.5
    root.location = center
    context.scene.collection.objects.link(root)
    root['ctk_light_rig'] = name
    for i, (kind, az, el, dist, energy, col, size) in enumerate(PRESETS[name]):
        ld = bpy.data.lights.new(f'{name} {i + 1}', kind)
        ld.color = col
        scale = max(radius, 0.5)
        if kind == 'SUN':
            ld.energy = energy
            ld.angle = math.radians(size)
        else:
            ld.energy = energy * scale * scale
            if kind == 'AREA':
                ld.shape = 'DISK' if i else 'RECTANGLE'
                ld.size = size * scale
            else:
                ld.shadow_soft_size = size * scale
        lo = bpy.data.objects.new(ld.name, ld)
        context.scene.collection.objects.link(lo)
        a, e = math.radians(az), math.radians(el)
        d = dist * scale
        lo.parent = root
        lo.location = (d * math.cos(e) * math.sin(a), -d * math.cos(e) * math.cos(a), d * math.sin(e))
        t = lo.constraints.new('TRACK_TO')
        t.target = root
        t.track_axis = 'TRACK_NEGATIVE_Z'
        t.up_axis = 'UP_Y'
    return root


class CTK_OT_light_rig(bpy.types.Operator):
    """Place a light rig around the selected objects (replaces the previous rig)"""
    bl_idname = 'ctk.light_rig'
    bl_label = 'Light rig'
    bl_options = {'REGISTER', 'UNDO'}
    preset: bpy.props.EnumProperty(items=[(k, k, '') for k in PRESETS])
    strength: bpy.props.FloatProperty(name='Strength', default=1.0, min=0.05, max=10)
    turn: bpy.props.FloatProperty(name='Turn', default=0.0, subtype='ANGLE')
    hide_world: bpy.props.BoolProperty(name='Darken the world light', default=False)

    def execute(self, context):
        root = build_rig(context, self.preset)
        root.rotation_euler.z = self.turn
        for c in root.children:
            c.data.energy *= self.strength
        if self.hide_world and context.scene.world and context.scene.world.use_nodes:
            bg = context.scene.world.node_tree.nodes.get('Background')
            if bg:
                bg.inputs['Strength'].default_value = 0.05
        return {'FINISHED'}


class CTK_OT_light_solo(bpy.types.Operator):
    """Solo this light (click again to bring all lights back)"""
    bl_idname = 'ctk.light_solo'
    bl_label = 'Solo light'
    name: bpy.props.StringProperty()

    def execute(self, context):
        lights = [o for o in context.scene.objects if o.type == 'LIGHT']
        soloed = context.scene.get('ctk_solo')
        if soloed == self.name:
            for o in lights:
                o.hide_render = o.hide_viewport = False
            context.scene['ctk_solo'] = ''
        else:
            for o in lights:
                o.hide_render = o.hide_viewport = (o.name != self.name)
            context.scene['ctk_solo'] = self.name
        return {'FINISHED'}


class CTK_OT_light_select(bpy.types.Operator):
    """Select this light"""
    bl_idname = 'ctk.light_select'
    bl_label = 'Select light'
    name: bpy.props.StringProperty()

    def execute(self, context):
        o = bpy.data.objects.get(self.name)
        if o:
            for s in context.selected_objects:
                s.select_set(False)
            o.select_set(True)
            context.view_layer.objects.active = o
        return {'FINISHED'}


CLASSES = (CTK_OT_light_rig, CTK_OT_light_solo, CTK_OT_light_select)


def draw(layout, context):
    grid = uxfit.flow(layout, context, [str(_t) for _t in PRESETS], most=2)
    for k in PRESETS:
        grid.operator('ctk.light_rig', text=k).preset = k
    root = bpy.data.objects.get(RIG)
    if root:
        layout.prop(root, 'rotation_euler', index=2, text='Turn rig')
    lights = [o for o in context.scene.objects if o.type == 'LIGHT']
    if lights:
        layout.label(text='Every light in the scene', icon='OUTLINER_OB_LIGHT')
        col = layout.column(align=True)
        solo = context.scene.get('ctk_solo', '')
        for o in lights:
            row = col.row(align=True)
            row.operator('ctk.light_select', text=o.name, emboss=o.select_get()).name = o.name
            row.prop(o.data, 'color', text='')
            row.prop(o.data, 'energy', text='')
            row.prop(o, 'hide_render', text='', icon='RESTRICT_RENDER_OFF' if not o.hide_render else 'RESTRICT_RENDER_ON')
            row.operator('ctk.light_solo', text='', icon='SOLO_ON' if solo == o.name else 'SOLO_OFF').name = o.name
