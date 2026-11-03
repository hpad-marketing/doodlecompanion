"""Rig a Thing: one-click rigs for props (hinge, wheel, squash, bend, follow path, look-at)."""
import math
import bpy
from mathutils import Vector

LABEL, ICON, GROUP = 'Rig a Thing', 'CON_TRACKTO', 'Rigging'


def _ctrl(context, name, loc, size, shape='CIRCLE'):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = shape
    e.empty_display_size = size
    e.location = loc
    e.show_in_front = True
    context.scene.collection.objects.link(e)
    return e


def _size(o):
    return max(max(o.dimensions) * 0.6, 0.1)


def _drive(target, path, index, ctrl, prop, expr='v'):
    fc = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    d.expression = expr
    v = d.variables.new()
    v.name = 'v'
    v.targets[0].id = ctrl
    v.targets[0].data_path = prop
    return fc


def hinge(context, o, axis='X', limit=110.0):
    """Pivot at the 3D cursor, e.g. the edge of a door or lid."""
    piv = _ctrl(context, o.name + ' Hinge', context.scene.cursor.location.copy(), _size(o) * 0.5, 'SINGLE_ARROW')
    mw = o.matrix_world.copy()
    o.parent = piv
    o.matrix_world = mw
    piv['open'] = 0.0
    ui = piv.id_properties_ui('open'); ui.update(min=0.0, max=1.0, description='0 closed, 1 open')
    idx = 'XYZ'.index(axis)
    _drive(piv, 'rotation_euler', idx, piv, '["open"]', f'v*{math.radians(limit):.5f}')
    return piv


def wheel(context, o, axis='X'):
    """Wheel turns by itself as its controller moves forward (Y)."""
    r = max(o.dimensions) / 2
    ctl = _ctrl(context, o.name + ' Drive', o.matrix_world.translation.copy(), r * 1.5, 'CUBE')
    mw = o.matrix_world.copy()
    o.parent = ctl
    o.matrix_world = mw
    idx = 'XYZ'.index(axis)
    fc = o.driver_add('rotation_euler', idx)
    d = fc.driver; d.type = 'SCRIPTED'; d.expression = f'-y/{r:.5f}'
    v = d.variables.new(); v.name = 'y'; v.type = 'TRANSFORMS'
    v.targets[0].id = ctl; v.targets[0].transform_type = 'LOC_Y'; v.targets[0].transform_space = 'WORLD_SPACE'
    return ctl


def squash(context, o):
    m = o.modifiers.new('CTK Squash', 'SIMPLE_DEFORM')
    m.deform_method = 'STRETCH'
    m.deform_axis = 'Z'
    o['squash'] = 0.0
    o.id_properties_ui('squash').update(min=-0.9, max=2.0, description='Negative squashes, positive stretches')
    fc = m.id_data.driver_add(f'modifiers["{m.name}"].factor')
    d = fc.driver; d.type = 'SCRIPTED'; d.expression = 'v'
    v = d.variables.new(); v.name = 'v'; v.targets[0].id = o; v.targets[0].data_path = '["squash"]'
    return o


def bend(context, o, axis='Z'):
    m = o.modifiers.new('CTK Bend', 'SIMPLE_DEFORM')
    m.deform_method = 'BEND'
    m.deform_axis = axis
    o['bend'] = 0.0
    o.id_properties_ui('bend').update(min=-3.14, max=3.14, subtype='ANGLE', description='Bend amount')
    fc = o.driver_add(f'modifiers["{m.name}"].angle')
    d = fc.driver; d.type = 'SCRIPTED'; d.expression = 'v'
    v = d.variables.new(); v.name = 'v'; v.targets[0].id = o; v.targets[0].data_path = '["bend"]'
    return o


def follow(context, o, curve, frames=100):
    c = o.constraints.new('FOLLOW_PATH')
    c.target = curve
    c.use_curve_follow = True
    c.forward_axis = 'FORWARD_Y'
    c.use_fixed_location = True
    sc = context.scene
    c.offset_factor = 0.0
    o.keyframe_insert(f'constraints["{c.name}"].offset_factor', frame=sc.frame_current)
    c.offset_factor = 1.0
    o.keyframe_insert(f'constraints["{c.name}"].offset_factor', frame=sc.frame_current + frames)
    o.location = (0, 0, 0)
    return c


def look_at(context, o):
    t = _ctrl(context, o.name + ' Look', o.matrix_world.translation + Vector((0, -2 * _size(o), 0)), _size(o) * 0.3, 'SPHERE')
    c = o.constraints.new('DAMPED_TRACK')
    c.target = t
    c.track_axis = 'TRACK_NEGATIVE_Y'
    return t


class CTK_OT_thing_rig(bpy.types.Operator):
    """Rig the selected object"""
    bl_idname = 'ctk.thing_rig'
    bl_label = 'Rig a Thing'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[
        ('HINGE', 'Hinge (door, lid)', 'Pivots at the 3D cursor. Put the cursor on the hinge edge first'),
        ('WHEEL', 'Wheel', 'Spins by itself as you move its Drive control forward'),
        ('SQUASH', 'Squash & stretch', ''), ('BEND', 'Bend', ''),
        ('FOLLOW', 'Follow a path', 'Select the object, then Shift-select the curve'),
        ('LOOK', 'Look at', 'Always faces a control you can move')])
    axis: bpy.props.EnumProperty(name='Axis', items=[('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')], default='Z')
    limit: bpy.props.FloatProperty(name='Open angle', default=110, min=1, max=360)
    frames: bpy.props.IntProperty(name='Path length (frames)', default=100, min=1)

    def execute(self, context):
        o = context.active_object
        if self.kind == 'FOLLOW':
            curve = next((x for x in context.selected_objects if x.type == 'CURVE'), None)
            mover = next((x for x in context.selected_objects if x.type != 'CURVE'), None)
            if not curve or not mover:
                self.report({'WARNING'}, 'Select the object and a curve')
                return {'CANCELLED'}
            follow(context, mover, curve, self.frames)
            return {'FINISHED'}
        if not o:
            self.report({'WARNING'}, 'Select an object')
            return {'CANCELLED'}
        if self.kind == 'HINGE':
            ctl = hinge(context, o, self.axis, self.limit)
        elif self.kind == 'WHEEL':
            ctl = wheel(context, o, 'X' if self.axis == 'Z' else self.axis)
        elif self.kind == 'SQUASH':
            ctl = squash(context, o)
        elif self.kind == 'BEND':
            ctl = bend(context, o, self.axis)
        else:
            ctl = look_at(context, o)
        for s in context.selected_objects:
            s.select_set(False)
        ctl.select_set(True)
        context.view_layer.objects.active = ctl
        return {'FINISHED'}


KINDS = [('HINGE', 'Hinge (door, lid)'), ('WHEEL', 'Wheel'), ('SQUASH', 'Squash & stretch'),
         ('BEND', 'Bend'), ('FOLLOW', 'Follow a path'), ('LOOK', 'Look at')]
CLASSES = (CTK_OT_thing_rig,)


def draw(layout, context):
    grid = layout.grid_flow(columns=2, align=True)
    for k, label in KINDS:
        grid.operator('ctk.thing_rig', text=label).kind = k
    o = context.active_object
    if o:
        for k, label in (('open', 'Open'), ('squash', 'Squash / stretch'), ('bend', 'Bend')):
            if k in o:
                layout.prop(o, f'["{k}"]', text=label, slider=True)
