import bpy, math, sys, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage
r = math.radians
POSES = {
 'hunch': dict(cam=((3.4, -3.6, 1.1), (0, 0, 0.95), 38), bones={
    'COG': dict(loc=(0, 0, -0.10)), 'hips': dict(rot=(10, 0, 0)),
    'IK_foot.L': dict(loc=(0, 0.15, 0)), 'IK_foot.R': dict(loc=(0, -0.10, 0)),
    'FK-upper_arm.L': dict(rot=(18, 0, 0)), 'FK-forearm.L': dict(rot=(25, 0, 0)), 'FK-hand.L': dict(rot=(10, 0, 0)),
    'FK-upper_arm.R': dict(rot=(8, 0, 0)), 'FK-forearm.R': dict(rot=(15, 0, 0)),
    **{f'f_{f}_1.{S}': dict(rot=(30, 0, 0)) for f in ('index', 'middle', 'ring', 'thumb') for S in 'LR'}}),
 'walk': dict(cam=((4.6, -1.2, 1.2), (0, -0.05, 1.0), 38), bones={
    'COG': dict(loc=(0, -0.03, -0.09)), 'waist': dict(rot=(0, 8, 0)), 'hips': dict(rot=(4, -6, 0)),
    'IK_foot.L': dict(loc=(0, 0.32, 0)), 'IK_foot.R': dict(loc=(0, -0.26, 0)), 'roll_ball.R': dict(rot=(30, 0, 0)),
    'FK-upper_arm.L': dict(rot=(-30, 0, 0)), 'FK-forearm.L': dict(rot=(15, 0, 0)),
    'FK-upper_arm.R': dict(rot=(35, 0, 0)), 'FK-forearm.R': dict(rot=(35, 0, 0)), 'FK-hand.R': dict(rot=(10, 0, 0)),
    **{f'f_{f}_1.{S}': dict(rot=(40, 0, 0)) for f in ('index', 'middle', 'ring', 'thumb') for S in 'LR'}}),
 'point': dict(cam=((-5.2, 0.9, 1.5), (0, -0.3, 1.3), 36), bones={
    'COG': dict(loc=(0, 0, -0.05)), 'waist': dict(rot=(0, -24, 0)),
    'IK_foot.L': dict(loc=(0, 0.10, 0)), 'IK_foot.R': dict(loc=(0, -0.05, 0)),
    'shoulder.R': dict(rot=(12, 0, 0)), 'FK-upper_arm.R': dict(rot=(82, 0, 0)), 'FK-forearm.R': dict(rot=(15, 0, 0)), 'FK-hand.R': dict(rot=(-15, 0, 0)),
    'f_index_1.R': dict(rot=(-5, 0, 0)), 'f_middle_1.R': dict(rot=(45, 0, 0)), 'f_middle_2.R': dict(rot=(30, 0, 0)),
    'f_ring_1.R': dict(rot=(45, 0, 0)), 'f_ring_2.R': dict(rot=(30, 0, 0)), 'f_thumb_1.R': dict(rot=(30, 0, 0)),
    'FK-upper_arm.L': dict(rot=(12, 0, 0)), 'FK-forearm.L': dict(rot=(40, 0, 0)),
    **{f'f_{f}_1.L': dict(rot=(45, 0, 0)) for f in ('index', 'middle', 'ring', 'thumb')}}),
 'crouch': dict(cam=((3.8, -3.2, 0.8), (0, -0.1, 0.8), 36), bones={
    'COG': dict(loc=(0, 0.05, -0.22)), 'hips': dict(rot=(14, 0, 0)),
    'IK_foot.L': dict(loc=(0, 0.06, 0), rot=(0, 0, 8)), 'IK_foot.R': dict(loc=(0, 0.06, 0), rot=(0, 0, -8)),
    'pole_knee.L': dict(loc=(0.15, 0, 0)), 'pole_knee.R': dict(loc=(-0.15, 0, 0)),
    'FK-upper_arm.L': dict(rot=(45, 0, 8)), 'FK-forearm.L': dict(rot=(50, 0, 0)), 'FK-hand.L': dict(rot=(-20, 0, 0)),
    'FK-upper_arm.R': dict(rot=(30, 0, 0)), 'FK-forearm.R': dict(rot=(65, 0, 0)),
    **{f'f_{f}_{i}.R': dict(rot=(60, 0, 0)) for f in ('index', 'middle', 'ring', 'thumb') for i in (1,)}}),
 'armour': dict(cam=((-3.6, 3.6, 2.4), (0, 0.1, 1.4), 38), bones={
    'hatch': dict(rot=(75, 0, 0)), 'sensor': dict(rot=(10, 50, 0)), 'skirt_back': dict(rot=(25, 0, 0)),
    'plate_thigh.L': dict(rot=(15, 0, 0)), 'plate_thigh.R': dict(rot=(15, 0, 0)),
    'plate_shield.L': dict(rot=(12, 0, 0)), 'plate_shield.R': dict(rot=(12, 0, 0)),
    'plate_forearm.L': dict(rot=(30, 0, 0)), 'plate_forearm.R': dict(rot=(30, 0, 0)),
    'plate_elbow.L': dict(rot=(20, 0, 0)), 'plate_elbow.R': dict(rot=(20, 0, 0)),
    'FK-upper_arm.L': dict(rot=(0, 0, 25)), 'FK-upper_arm.R': dict(rot=(0, 0, -25)),
    'FK-forearm.L': dict(rot=(30, 0, 0)), 'FK-forearm.R': dict(rot=(30, 0, 0))}),
 'hand': dict(cam=((1.75, -0.75, 0.75), (0.86, 0.02, 0.62), 60), bones={
    'FK-upper_arm.L': dict(rot=(20, 0, 0)), 'FK-forearm.L': dict(rot=(45, 0, 0)), 'FK-hand.L': dict(rot=(10, -30, 0)),
    'f_index_1.L': dict(rot=(10, 0, 0)), 'f_middle_1.L': dict(rot=(35, 0, 0)), 'f_middle_2.L': dict(rot=(25, 0, 0)),
    'f_ring_1.L': dict(rot=(44, 0, 0)), 'f_ring_2.L': dict(rot=(35, 0, 0)), 'f_ring_3.L': dict(rot=(30, 0, 0)),
    'f_thumb_1.L': dict(rot=(20, 0, 0)), 'f_thumb_0.L': dict(rot=(0, 45, 0))}),
}
FLIP_Z = True
def apply(arm, name):
    pbs = arm.pose.bones
    for pb in pbs: pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
    for b, v in POSES[name]['bones'].items():
        pb = pbs[b]
        if 'loc' in v: pb.location = v['loc']
        if 'rot' in v: pb.rotation_euler = [r(a) for a in v['rot']]
    bpy.context.view_layer.update()

if __name__ == '__main__':
    blend, outdir = sys.argv[-2:]
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = bpy.data.objects['RobotRig']
    ns = {'__name__': 'robot_rig_ui'}; exec(bpy.data.texts['robot_rig_ui.py'].as_string(), ns)
    sc = bpy.context.scene; sc.cycles.device = 'CPU'; arm.hide_render = True
    sc.render.resolution_x = sc.render.resolution_y = 1080
    rep = {}
    only = [a for a in sys.argv if a.startswith('pose=')]
    names = only[0][5:].split(',') if only else list(POSES)
    for n in names:
        apply(arm, n)
        hits = ns['find_contacts'](arm, bpy.context)
        feet = min((o.matrix_world @ v.co).z for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and ('foot' in o.name or 'toe' in o.name) for v in o.data.vertices)
        rep[n] = dict(clashes=hits, lowest_foot_z=round(feet, 4))
        print(n, rep[n])
        l, t, lens = POSES[n]['cam']
        if n == 'hand':
            from mathutils import Vector
            p = bpy.data.objects['palm.L'].matrix_world @ Vector(bpy.data.objects['palm.L'].data.vertices[0].co)
            c = sum((bpy.data.objects['palm.L'].matrix_world @ v.co for v in bpy.data.objects['palm.L'].data.vertices), Vector()) / len(bpy.data.objects['palm.L'].data.vertices)
            t = c + Vector((0, -0.02, -0.07)); l = t + Vector((0.85, -0.7, 0.18)); lens = 50
        stage.aim(sc.camera, l, t, lens)
        sc.cycles.samples = 64; sc.render.filepath = f'{outdir}/{n}.png'
        if 'norender' not in sys.argv: bpy.ops.render.render(write_still=True)
    json.dump(rep, open(f'{outdir}/pose_report.json', 'w'), indent=1)
