"""Mocap and poses: retarget Mixamo / BVH / other rigs onto your rig, and a pose library."""
import os
import bpy
from mathutils import Matrix, Quaternion
from . import _util

LABEL, ICON, GROUP = 'Mocap + pose library', 'ARMATURE_DATA', 'Rigging'

# our rig bone -> source names (prefixes like "mixamorig:" are stripped before matching)
MAP = {
    'hips': ['Hips', 'hips', 'pelvis', 'Pelvis', 'mixamorig_Hips'],
    'chest': ['Spine2', 'Spine1', 'Chest', 'chest', 'spine_03', 'UpperChest', 'Spine'],
    'neck': ['Neck', 'neck', 'neck_01', 'Neck1'],
    'head': ['Head', 'head'],
    'upper_arm.L': ['LeftArm', 'upperarm_l', 'upper_arm.L', 'LeftUpperArm', 'L_UpperArm'],
    'forearm.L': ['LeftForeArm', 'lowerarm_l', 'forearm.L', 'LeftLowerArm', 'L_Forearm'],
    'hand.L': ['LeftHand', 'hand_l', 'hand.L', 'L_Hand'],
    'upper_arm.R': ['RightArm', 'upperarm_r', 'upper_arm.R', 'RightUpperArm', 'R_UpperArm'],
    'forearm.R': ['RightForeArm', 'lowerarm_r', 'forearm.R', 'RightLowerArm', 'R_Forearm'],
    'hand.R': ['RightHand', 'hand_r', 'hand.R', 'R_Hand'],
    'thigh.L': ['LeftUpLeg', 'thigh_l', 'thigh.L', 'LeftUpperLeg', 'L_Thigh', 'LHipJoint'],
    'shin.L': ['LeftLeg', 'calf_l', 'shin.L', 'LeftLowerLeg', 'L_Calf'],
    'foot.L': ['LeftFoot', 'foot_l', 'foot.L', 'L_Foot'],
    'thigh.R': ['RightUpLeg', 'thigh_r', 'thigh.R', 'RightUpperLeg', 'R_Thigh', 'RHipJoint'],
    'shin.R': ['RightLeg', 'calf_r', 'shin.R', 'RightLowerLeg', 'R_Calf'],
    'foot.R': ['RightFoot', 'foot_r', 'foot.R', 'R_Foot'],
}


def _short(n):
    return n.split(':')[-1].split('|')[-1]


def find_map(src, dst):
    names = {_short(b.name): b.name for b in src.data.bones}
    out = {}
    for t, cands in MAP.items():
        if t not in dst.pose.bones:
            continue
        for c in cands:
            if c in names:
                out[t] = names[c]
                break
    # same-name bones (CTK rig to CTK rig, or identical skeletons)
    for b in dst.pose.bones:
        if b.name not in out and b.name in src.pose.bones and not b.name.startswith(('IK_', 'pole_', 'root')):
            out[b.name] = b.name
    return out


def _rot(m):
    return m.to_quaternion().to_matrix().to_4x4()


def retarget(context, src, dst, frame_start=None, frame_end=None, keep_root_motion=True):
    bmap = find_map(src, dst)
    if 'hips' not in bmap and not bmap:
        raise RuntimeError('No matching bones found')
    sc = context.scene
    act = src.animation_data.action if src.animation_data else None
    if frame_start is None:
        if act:
            frame_start, frame_end = (int(x) for x in act.frame_range)
        else:
            frame_start, frame_end = sc.frame_start, sc.frame_end
    for k in [k for k in dst.keys() if k.startswith('IK ')]:
        dst[k] = 0.0
        dst.keyframe_insert(f'["{k}"]', frame=frame_start)
    Ws, Wt = _rot(src.matrix_world), _rot(dst.matrix_world)
    Wti = Wt.inverted()
    s_rest = {b.name: Ws @ _rot(b.matrix_local) for b in src.data.bones}
    hips_src = bmap.get('hips')
    s_h = src.data.bones[hips_src] if hips_src else None
    t_h = dst.data.bones.get('hips')
    ratio = 1.0
    if s_h and t_h:
        sh = (src.matrix_world @ s_h.head_local).z - src.matrix_world.translation.z
        th = (dst.matrix_world @ t_h.head_local).z - dst.matrix_world.translation.z
        ratio = th / sh if abs(sh) > 1e-6 else 1.0
    s_hips_rest = src.matrix_world @ s_h.head_local if s_h else None
    order = sorted(dst.pose.bones, key=lambda pb: len(pb.parent_recursive))
    for pb in order:
        if pb.name in bmap:
            pb.rotation_mode = 'QUATERNION'
    for f in range(frame_start, frame_end + 1):
        sc.frame_set(f)
        pose = {}
        for pb in order:
            b = pb.bone
            rest = _rot(b.matrix_local)
            if pb.parent:
                restrel = _rot(b.parent.matrix_local).inverted() @ rest
                ppose = pose[pb.parent.name]
            else:
                restrel, ppose = rest, Matrix.Identity(4)
            if pb.name in bmap:
                sp = src.pose.bones[bmap[pb.name]]
                D = (Ws @ _rot(sp.matrix)) @ s_rest[sp.name].inverted()
                desired = Wti @ D @ Wt @ rest
                basis = (restrel.inverted() @ ppose.inverted() @ desired).to_quaternion()
                pb.rotation_quaternion = basis
                pb.keyframe_insert('rotation_quaternion', frame=f, group=pb.name)
                pose[pb.name] = desired
            else:
                pose[pb.name] = ppose @ restrel @ _rot(pb.matrix_basis)
        if keep_root_motion and s_h and t_h and 'hips' in dst.pose.bones:
            sw = src.matrix_world @ src.pose.bones[hips_src].head
            delta = (sw - s_hips_rest) * ratio
            local = _rot(t_h.matrix_local).inverted() @ Wti @ delta
            pbh = dst.pose.bones['hips']
            pbh.location = local.to_3d() if hasattr(local, 'to_3d') else local
            pbh.keyframe_insert('location', frame=f, group='hips')
    return bmap, (frame_start, frame_end)


class CTK_OT_mocap_import(bpy.types.Operator):
    """Import a Mixamo FBX or BVH and put its motion on the active rig"""
    bl_idname = 'ctk.mocap_import'
    bl_label = 'Import mocap onto rig'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.fbx;*.bvh', options={'HIDDEN'})
    keep_source: bpy.props.BoolProperty(name='Keep the imported skeleton', default=False)
    root_motion: bpy.props.BoolProperty(name='Move the whole body (root motion)', default=True)

    def invoke(self, context, event):
        if not context.active_object or context.active_object.type != 'ARMATURE':
            self.report({'WARNING'}, 'Select your rig first')
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        dst = context.active_object
        before = set(bpy.data.objects)
        if self.filepath.lower().endswith('.bvh'):
            bpy.ops.import_anim.bvh(filepath=self.filepath, update_scene_fps=False, update_scene_duration=True)
        else:
            bpy.ops.import_scene.fbx(filepath=self.filepath, automatic_bone_orientation=False, ignore_leaf_bones=True)
        new = [o for o in bpy.data.objects if o not in before]
        src = next((o for o in new if o.type == 'ARMATURE'), None)
        if not src:
            self.report({'WARNING'}, 'No skeleton found in the file')
            return {'CANCELLED'}
        try:
            bmap, rng = retarget(context, src, dst, keep_root_motion=self.root_motion)
        except RuntimeError as e:
            self.report({'WARNING'}, str(e))
            return {'CANCELLED'}
        if dst.animation_data and dst.animation_data.action:
            dst.animation_data.action.name = os.path.splitext(os.path.basename(self.filepath))[0]
        if not self.keep_source:
            for o in new:
                bpy.data.objects.remove(o)
        context.view_layer.objects.active = dst
        self.report({'INFO'}, f'{len(bmap)} bones retargeted, frames {rng[0]}-{rng[1]}')
        return {'FINISHED'}


class CTK_OT_retarget_selected(bpy.types.Operator):
    """Copy motion from the selected skeleton onto the active rig"""
    bl_idname = 'ctk.retarget_selected'
    bl_label = 'Retarget from selected'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        dst = context.active_object
        src = next((o for o in context.selected_objects if o.type == 'ARMATURE' and o != dst), None)
        if not dst or dst.type != 'ARMATURE' or not src:
            self.report({'WARNING'}, 'Select the source skeleton, then Shift-click your rig')
            return {'CANCELLED'}
        bmap, rng = retarget(context, src, dst)
        self.report({'INFO'}, f'{len(bmap)} bones, frames {rng[0]}-{rng[1]}')
        return {'FINISHED'}


class CTK_OT_pose_save(bpy.types.Operator):
    """Save the current pose of the selected bones to your Vault's pose library"""
    bl_idname = 'ctk.pose_save'
    bl_label = 'Save pose'
    name: bpy.props.StringProperty(name='Pose name', default='Pose')
    category: bpy.props.StringProperty(name='Category', default='Poses')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        rig = context.active_object
        bones = context.selected_pose_bones or (rig.pose.bones if rig and rig.type == 'ARMATURE' else [])
        if not bones:
            self.report({'WARNING'}, 'Select bones in Pose Mode')
            return {'CANCELLED'}
        ad = rig.animation_data_create()
        old = ad.action
        act = bpy.data.actions.new(self.name)
        ad.action = act
        for pb in bones:
            for path in ('location', 'rotation_quaternion' if pb.rotation_mode == 'QUATERNION' else 'rotation_euler', 'scale'):
                pb.keyframe_insert(path, frame=1, group=pb.name)
        ad.action = old
        from .vault import catalog_id
        act.asset_mark()
        act.asset_data.catalog_id = catalog_id(self.category)
        d = os.path.join(_util.vault_dir(), self.category)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, ''.join(c if c.isalnum() or c in ' -_' else '_' for c in self.name) + '.blend')
        bpy.data.libraries.write(p, {act}, fake_user=True)
        from .vault import ensure_library
        ensure_library()
        self.report({'INFO'}, f'Pose saved. Apply it from the Asset Browser (Creator Vault › {self.category})')
        return {'FINISHED'}


class CTK_OT_pose_flip(bpy.types.Operator):
    """Mirror the current pose left to right"""
    bl_idname = 'ctk.pose_flip'
    bl_label = 'Flip pose'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE'

    def execute(self, context):
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.copy()
        bpy.ops.pose.paste(flipped=True)
        return {'FINISHED'}


CLASSES = (CTK_OT_mocap_import, CTK_OT_retarget_selected, CTK_OT_pose_save, CTK_OT_pose_flip)


def draw(layout, context):
    col = layout.column(align=True)
    col.operator('ctk.mocap_import', icon='IMPORT')
    col.operator('ctk.retarget_selected', icon='ARMATURE_DATA')
    layout.label(text='Free mocap: mixamo.com (FBX, without skin)', icon='URL')
    row = layout.row(align=True)
    row.operator('ctk.pose_save', icon='ADD')
    row.operator('ctk.pose_flip', icon='MOD_MIRROR')
    layout.label(text='Apply saved poses from the Asset Browser', icon='ASSET_MANAGER')
