"""Spring bones: ears, tails, antennas and hoods follow through and jiggle (Wiggle-style)."""
import bpy
from bpy.app.handlers import persistent
from mathutils import Vector, Matrix, Quaternion

LABEL, ICON, GROUP = 'Spring bones', 'FORCE_HARMONIC', 'Rigging'
_state = {}  # (rig, bone) -> [pos, vel]
_last = {'frame': None}


def _animated(rig, pb):
    ad = rig.animation_data
    if not ad or not ad.action:
        return False
    from ..compat import action_fcurves
    path = f'pose.bones["{pb.name}"].rotation'
    return any(fc.data_path.startswith(path) for fc in action_fcurves(ad.action, rig))


def _springs(rig):
    out = [pb for pb in rig.pose.bones if pb.get('ctk_spring') and not pb.get('ctk_spring_baked')]
    out.sort(key=lambda pb: len(pb.parent_recursive))
    return out


def _rigs(scene):
    return [o for o in scene.objects if o.type == 'ARMATURE' and o.get('ctk_springs_on', 1) and
            any(pb.get('ctk_spring') for pb in o.pose.bones)]


def _apply_local(pb, L):
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = pb.rotation_quaternion @ L
    elif pb.rotation_mode == 'AXIS_ANGLE':
        return
    else:
        e = pb.rotation_euler.to_quaternion() @ L
        pb.rotation_euler = e.to_euler(pb.rotation_mode, pb.rotation_euler)


@persistent
def _pre(scene, depsgraph=None):
    for rig in _rigs(scene):
        for pb in reversed(_springs(rig)):
            q = pb.get('ctk_L')
            if q and not _animated(rig, pb):
                _apply_local(pb, Quaternion(q).inverted())
            if 'ctk_L' in pb:
                del pb['ctk_L']


@persistent
def _post(scene, depsgraph=None):
    f = scene.frame_current
    jump = _last['frame'] is None or f <= scene.frame_start or abs(f - _last['frame']) != 1
    _last['frame'] = f
    for rig in _rigs(scene):
        W = rig.matrix_world
        Wi = W.inverted()
        changed = {}
        for pb in _springs(rig):
            orig = pb.matrix.copy()
            M = orig.copy()
            par = pb.parent
            while par is not None and par.name not in changed:
                par = par.parent
            if par is not None:
                oldP, newP = changed[par.name]
                M = newP @ oldP.inverted() @ M
            head = M.translation.copy()
            tail = M @ Vector((0, pb.bone.length, 0))
            key = (rig.name, pb.name)
            tw = W @ tail
            hw = W @ head
            if jump or key not in _state:
                _state[key] = [tw.copy(), Vector()]
                changed[pb.name] = (orig, M)
                continue
            pos, vel = _state[key]
            k = float(pb.get('ctk_stiffness', 0.25))
            d = float(pb.get('ctk_damping', 0.75))
            g = float(pb.get('ctk_gravity', 0.0))
            vel += (tw - pos) * k
            vel *= (1.0 - d * 0.5)
            vel.z -= g * 0.01
            pos += vel
            ln = (tw - hw).length
            pos[:] = hw + (pos - hw).normalized() * ln
            dn = (Wi @ pos - head).normalized()
            do = (tail - head).normalized()
            q = do.rotation_difference(dn)
            newM = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ M
            L = (M.inverted() @ newM).to_quaternion()
            _apply_local(pb, L)
            pb['ctk_L'] = list(L)
            changed[pb.name] = (orig, newM)
            _state[key] = [pos, vel]


class CTK_OT_spring_toggle(bpy.types.Operator):
    """Make the selected bones springy (or not)"""
    bl_idname = 'ctk.spring_toggle'
    bl_label = 'Springy bones'
    bl_options = {'REGISTER', 'UNDO'}
    on: bpy.props.BoolProperty(default=True)
    stiffness: bpy.props.FloatProperty(name='Stiffness', default=0.25, min=0.01, max=1)
    damping: bpy.props.FloatProperty(name='Damping', default=0.75, min=0.0, max=1)
    gravity: bpy.props.FloatProperty(name='Droop', default=0.0, min=0.0, max=5)

    def execute(self, context):
        bones = context.selected_pose_bones or []
        if not bones:
            self.report({'WARNING'}, 'Select bones in Pose Mode')
            return {'CANCELLED'}
        for pb in bones:
            if self.on:
                pb['ctk_spring'] = 1
                pb['ctk_stiffness'] = self.stiffness
                pb['ctk_damping'] = self.damping
                pb['ctk_gravity'] = self.gravity
                pb.id_data['dm_phys_kind'] = 'SPRING'
            else:
                for k in ('ctk_spring', 'ctk_stiffness', 'ctk_damping', 'ctk_gravity', 'ctk_L', 'ctk_spring_baked'):
                    if k in pb:
                        del pb[k]
        return {'FINISHED'}


class CTK_OT_spring_bake(bpy.types.Operator):
    """Bake the spring motion to keyframes (for export or hand tweaking)"""
    bl_idname = 'ctk.spring_bake'
    bl_label = 'Bake springs to keys'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sc = context.scene
        done = bake(sc, sc.frame_start, sc.frame_end)
        if not done:
            self.report({'WARNING'}, 'No springy bones in this scene')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Baked {len(done)} bones')
        return {'FINISHED'}


def bake(sc, f0, f1):
    """Key the spring motion from f0 to f1. Returns [[rig, bone], ...] that were baked."""
    rigs = _rigs(sc)
    if not rigs:
        return []
    keep = sc.frame_current
    keys = {}
    _last['frame'] = None
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for rig in rigs:
            for pb in _springs(rig):
                keys.setdefault((rig.name, pb.name), []).append((f, pb.rotation_mode, tuple(pb.rotation_quaternion), tuple(pb.rotation_euler)))
    for (rn, bn), rows in keys.items():
        pb = bpy.data.objects[rn].pose.bones[bn]
        for f, mode, q, e in rows:
            if mode == 'QUATERNION':
                pb.rotation_quaternion = q
                pb.keyframe_insert('rotation_quaternion', frame=f)
            else:
                pb.rotation_euler = e
                pb.keyframe_insert('rotation_euler', frame=f)
        pb['ctk_spring_baked'] = 1
        if 'ctk_L' in pb:
            del pb['ctk_L']
    sc.frame_set(keep)
    return [list(k) for k in keys]


def unbake_flags(pairs):
    for rn, bn in pairs:
        o = bpy.data.objects.get(rn)
        pb = o.pose.bones.get(bn) if o and o.pose else None
        if pb is not None and 'ctk_spring_baked' in pb:
            del pb['ctk_spring_baked']
    _state.clear()
    _last['frame'] = None


class CTK_OT_spring_reset(bpy.types.Operator):
    """Reset the simulation (use after jumping around the timeline)"""
    bl_idname = 'ctk.spring_reset'
    bl_label = 'Reset springs'

    def execute(self, context):
        _state.clear()
        _last['frame'] = None
        return {'FINISHED'}


CLASSES = (CTK_OT_spring_toggle, CTK_OT_spring_bake, CTK_OT_spring_reset)


def register_extra():
    bpy.app.handlers.frame_change_pre.append(_pre)
    bpy.app.handlers.frame_change_post.append(_post)


def unregister_extra():
    for h, f in ((bpy.app.handlers.frame_change_pre, _pre), (bpy.app.handlers.frame_change_post, _post)):
        if f in h:
            h.remove(f)


def draw(layout, context):
    pb = context.active_pose_bone
    row = layout.row(align=True)
    row.operator('ctk.spring_toggle', text='Make springy', icon='FORCE_HARMONIC').on = True
    row.operator('ctk.spring_toggle', text='Not springy').on = False
    if pb and pb.get('ctk_spring'):
        row = layout.row(align=True)
        row.prop(pb, '["ctk_stiffness"]', text='Stiffness', slider=True)
        row.prop(pb, '["ctk_damping"]', text='Damping', slider=True)
        row.prop(pb, '["ctk_gravity"]', text='Droop')
    rig = context.active_object
    if rig and rig.type == 'ARMATURE':
        layout.prop(rig, '["ctk_springs_on"]', text='Springs on') if 'ctk_springs_on' in rig else \
            layout.label(text='Springs play live; bake before export', icon='INFO')
    row = layout.row(align=True)
    row.operator('ctk.spring_bake', icon='KEYFRAME')
    row.operator('ctk.spring_reset', icon='FILE_REFRESH', text='')
