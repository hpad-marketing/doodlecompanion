"""Put things where the shot needs them without touching Bunny.

Place (click in the viewport) snaps an object onto whatever surface is under the mouse:
  floor   stands on floors and ground (easel, sign post, plant, crate)
  table   stands on any upward surface: tables, shelves, counters, the floor
  wall    hangs flat on walls (frames, posters, boards, clocks)
  free    floats where you click, turned to the camera (speech bubbles, 3D words)
Bunny is locked (not selectable) while you place, so a stray click can't grab the rig.
"""
import math

import bpy
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

MODES = ('floor', 'table', 'wall', 'free')


def bunny_objects():
    return [o for o in bpy.data.objects if o.name.startswith('BUNNY_') or o.name == 'DSL_mouth_set']


def lock_bunny(on=True):
    """Make every part of Bunny unselectable (on) or selectable again (off). Undo-safe."""
    for o in bunny_objects():
        o.hide_select = on
    bpy.context.scene['dsl_bunny_locked'] = bool(on)
    return on


def is_locked():
    return bool(bpy.context.scene.get('dsl_bunny_locked', False))


def place_mode(ob):
    m = ob.get('dsl_place')
    if m in MODES:
        return m
    from . import index
    it = index.get(ob.get('dsl_id', '')) or {}
    if it.get('category') == 'card':
        return 'wall'
    m = (it.get('data') or {}).get('place')
    if m in MODES:
        return m
    return 'table' if it.get('category') == 'prop' else 'floor'


def _local_bounds(ob):
    pts = [Vector(c) for c in ob.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def ray(context, coord, skip=()):
    """First surface under a 2D mouse position, ignoring `skip`, Bunny and helper empties."""
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    return ray_world(context, o, d, skip)


def ray_world(context, origin, direction, skip=()):
    dg = context.evaluated_depsgraph_get()
    ignore = set(o.name for o in skip) | set(o.name for o in bunny_objects())
    o = origin.copy()
    for _ in range(32):
        hit, loc, nrm, _, ob, _ = context.scene.ray_cast(dg, o, direction)
        if not hit:
            return None
        if ob.name in ignore or ob.get('dsl_socket') or not ob.visible_get():
            o = loc + direction * 1e-3
            continue
        nrm = nrm.normalized()
        if nrm.dot(direction) > 0:  # single-sided shells: face the normal back at the viewer
            nrm = -nrm
        return loc, nrm, ob
    return None


def place(ob, loc, nrm, mode=None, spin=0.0, lift=0.0, cam=None):
    """Snap `ob` to a surface hit. spin turns it about the surface normal (radians)."""
    mode = mode or place_mode(ob)
    scale = ob.matrix_world.to_scale()
    mn, mx = _local_bounds(ob)
    cam = cam or bpy.context.scene.camera
    to_cam = (cam.matrix_world.translation - loc) if cam else Vector((0, -1, 0))
    if mode in ('floor', 'table'):
        up = nrm if (nrm.z > 0.6 and mode == 'table') else Vector((0, 0, 1))
        if mode == 'floor' and nrm.z < 0.6:
            up = Vector((0, 0, 1))
        fwd = Vector((to_cam.x, to_cam.y, 0)).normalized() if to_cam.length else Vector((0, -1, 0))
        fwd = (Matrix.Rotation(spin, 3, up) @ fwd)
        fwd = (fwd - up * fwd.dot(up)).normalized()
        # model front is -y: so local -y -> fwd, local z -> up
        y = -fwd
        x = y.cross(up).normalized()
        R = Matrix((x, y, up)).transposed()
        base = Vector(((mn.x + mx.x) / 2 * scale.x, (mn.y + mx.y) / 2 * scale.y, mn.z * scale.z))
        p = loc + up * lift - R @ base
    elif mode == 'wall':
        n = Vector((nrm.x, nrm.y, 0))
        n = n.normalized() if n.length > 1e-4 else Vector((0, -1, 0))
        up = Vector((0, 0, 1))
        y = -n            # front (-y) faces out of the wall
        x = y.cross(up).normalized()
        R = Matrix((x, y, up)).transposed() @ Matrix.Rotation(spin, 3, 'Y')
        back = Vector(((mn.x + mx.x) / 2 * scale.x, mx.y * scale.y, (mn.z + mx.z) / 2 * scale.z))
        p = loc + up * lift - R @ back + n * 0.002
    else:  # free: hover a little off the surface, facing the camera
        f = Vector((to_cam.x, to_cam.y, 0)).normalized() if to_cam.length else Vector((0, -1, 0))
        y = -(Matrix.Rotation(spin, 3, 'Z') @ f)
        up = Vector((0, 0, 1))
        x = y.cross(up).normalized()
        R = Matrix((x, y, up)).transposed()
        p = loc + nrm * (0.05 + lift)
    ob.matrix_world = Matrix.Translation(p) @ R.to_4x4() @ Matrix.Diagonal(scale).to_4x4()
    return ob


def drop(ob, context=None):
    """Drop onto whatever is straight below (keeps the turn)."""
    context = context or bpy.context
    context.view_layer.update()
    mn, _ = _local_bounds(ob)
    c = ob.matrix_world @ Vector((0, 0, mn.z))
    hit = ray_world(context, c + Vector((0, 0, 0.5)), Vector((0, 0, -1)), skip=[ob])
    if not hit:
        return False
    mw = ob.matrix_world.copy()
    mw.translation.z += hit[0].z - c.z
    ob.matrix_world = mw
    return True


class DSL_OT_place(bpy.types.Operator):
    """Click where it should go. Wheel turns it, Ctrl+wheel raises it, Tab changes floor/table/wall/free"""
    bl_idname = 'dsl.place'
    bl_label = 'Place in scene'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Use this in the 3D viewport.')
            return {'CANCELLED'}
        self.objs = [o for o in context.selected_objects if not o.name.startswith('BUNNY_')]
        held = [o.name for o in self.objs if o.get('dsl_held_side')]
        if held:
            self.report({'WARNING'}, '%s is in Bunny\'s hand: use G or R (they stay inside the grip limits), '
                        'or Let go first.' % held[0])
            return {'CANCELLED'}
        if not self.objs:
            self.report({'WARNING'}, 'Select the object to place.')
            return {'CANCELLED'}
        self.ob = context.active_object if context.active_object in self.objs else self.objs[0]
        self.rest = {o.name: o.matrix_world.copy() for o in self.objs}
        self.rel = {o.name: self.ob.matrix_world.inverted() @ o.matrix_world for o in self.objs}
        self.mode = place_mode(self.ob)
        self.spin = 0.0
        self.lift = 0.0
        self.was_locked = is_locked()
        lock_bunny(True)
        self._status(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        context.area.header_text_set('Place %s: %s | click to drop | wheel turn | Ctrl+wheel raise | '
                                     'Tab floor/table/wall/free | Esc cancel' % (self.ob.name, self.mode.upper()))

    def _update(self, context, event):
        hit = ray(context, (event.mouse_region_x, event.mouse_region_y), skip=self.objs)
        if not hit:
            return
        loc, nrm, _ = hit
        place(self.ob, loc, nrm, self.mode, self.spin, self.lift)
        for o in self.objs:
            if o is not self.ob:
                o.matrix_world = self.ob.matrix_world @ self.rel[o.name]

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            self._update(context, event)
        elif event.type in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
            step = 1 if event.type == 'WHEELUPMOUSE' else -1
            if event.ctrl:
                self.lift += 0.02 * step
            else:
                self.spin += math.radians(15) * step
            self._update(context, event)
        elif event.type == 'TAB' and event.value == 'PRESS':
            self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
            self.ob['dsl_place'] = self.mode
            self._status(context)
            self._update(context, event)
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._end(context)
            return {'FINISHED'}
        elif event.type in ('RIGHTMOUSE', 'ESC') and event.value == 'PRESS':
            for o in self.objs:
                o.matrix_world = self.rest[o.name]
            self._end(context)
            return {'CANCELLED'}
        else:
            return {'PASS_THROUGH'} if event.type in ('MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM') else {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.area.header_text_set(None)
        if not self.was_locked:
            lock_bunny(False)


class DSL_OT_drop(bpy.types.Operator):
    """Drop the selected objects onto the surface straight below them"""
    bl_idname = 'dsl.drop'
    bl_label = 'Drop to surface'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = sum(1 for o in context.selected_objects if not o.get('dsl_held_side') and drop(o, context))
        self.report({'INFO'}, 'Dropped %d' % n)
        return {'FINISHED'}


class DSL_OT_lock_bunny(bpy.types.Operator):
    """Lock or unlock Bunny so clicks in the viewport can't select (and break) the rig"""
    bl_idname = 'dsl.lock_bunny'
    bl_label = 'Lock Bunny'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        on = lock_bunny(not is_locked())
        self.report({'INFO'}, 'Bunny locked' if on else 'Bunny unlocked')
        return {'FINISHED'}


classes = (DSL_OT_place, DSL_OT_drop, DSL_OT_lock_bunny)
