"""Objects in the library: 360° props, 3D scenery pieces, 2D cards, your own models."""
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import index, paths, style


def target_collection(name='Doodle Library'):
    sc = bpy.context.scene
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
    if coll.name not in [c.name for c in sc.collection.children_recursive] and coll is not sc.collection:
        try:
            sc.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll


def load_object(item):
    """Append one object datablock from its library .blend (not linked: you can edit it)."""
    path = paths.lib_path(item['file'])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if item['datablock'] not in src.objects:
            raise RuntimeError('%s is missing from %s' % (item['datablock'], item['file']))
        dst.objects = [item['datablock']]
    return dst.objects[0]


def insert_object(item, location=None, collection=None, style_it=True):
    ob = load_object(item)
    (collection or target_collection()).objects.link(ob)
    ob['dsl_id'] = item['id']
    if location is not None:
        ob.location = location
    if style_it:
        style.apply_style(ob, bpy.context.scene.camera, seed=hash(item['id']) % 97 * 0.13)
    if ob.get('dsl_pack') or ob.get('dsl_parts'):
        from . import packs
        packs.dress(ob)  # lids, wheels, typed labels, lights, seats ...
    index.mark_used(item['id'])
    return ob


def bunny_hand(side='R'):
    arm = bpy.data.objects.get('BUNNY_rig')
    if not arm:
        return None, None
    for name in ('DEF-hand.' + side, 'hand_fk.' + side):
        if name in arm.pose.bones:
            return arm, name
    return arm, None


def hand_point(side='R'):
    """World centre of Bunny's (posed) hand mesh: where the grip goes."""
    ob = bpy.data.objects.get('BUNNY_hand.' + side)
    if not ob:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    pts = [ev.matrix_world @ v.co for v in ev.data.vertices]
    return sum(pts, Vector()) / max(1, len(pts))


DS_TO_BLENDER = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # prop model axes (x right, y up, z to camera)


def _side_track(track, side):
    for base in ('armForward', 'arm', 'elbow', 'wrist'):
        for sd in 'LR':
            name = base[:3] + sd + base[3:] if base == 'armForward' else base + sd
            if track == name:
                return base[:3] + side + base[3:] if base == 'armForward' else base + side
    return track


def attach_prop(ob, side=None, pose=True, frame=None):
    """Put a prop in Bunny's hand with its researched hold (grip = object origin)."""
    arm, bone = bunny_hand('R')
    if not bone:
        raise RuntimeError('No Bunny hand to attach to.')
    item = index.get(ob.get('dsl_id', '')) or {}
    hold = (item.get('data') or {}).get('hold') or {}
    side = side or ('L' if hold.get('attach') == 'armL' else 'R')
    arm, bone = bunny_hand(side)
    sc = bpy.context.scene
    frame = sc.frame_current if frame is None else frame
    if pose and hold.get('pose'):
        ds_map = paths.bunny_module('ds_map')
        import json
        meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
        sides = [side] + ([('L' if side == 'R' else 'R')] if hold.get('hand') == 'two' else [])
        for sd in sides:
            vals = {_side_track(k, sd): v for k, v in hold['pose'].items()}
            for b, ds in (('upper_arm_fk.' + sd, 'UPPER_ARM.' + sd), ('forearm_fk.' + sd, 'FOREARM.' + sd),
                          ('hand_fk.' + sd, 'WRIST.' + sd)):
                pb = arm.pose.bones[b]
                from .motions import set_rot, rot_path
                set_rot(pb, ds_map.to_local(pb, ds_map.ds_world_rotation(meta['controls'], vals, ds)))
                pb.keyframe_insert(rot_path(pb), frame=frame, group=b)
        bpy.context.view_layer.update()
    p = hand_point(side)
    if p is None:
        p = arm.matrix_world @ arm.pose.bones[bone].head
    # carried orientation is in Bunny's body frame; turn it with Bunny's root
    o = hold.get('orientation')
    R = Matrix(o).transposed() if o else Matrix.Identity(3)
    Rb = DS_TO_BLENDER @ R @ DS_TO_BLENDER.inverted()
    root = arm.matrix_world @ arm.pose.bones['root'].matrix
    ob.matrix_world = Matrix.Translation(p) @ (root.to_3x3().normalized() @ Rb).to_4x4() @ Matrix.Scale(ob.matrix_world.to_scale()[0], 4)
    for c in [c for c in ob.constraints if c.type == 'CHILD_OF']:
        ob.constraints.remove(c)
    con = ob.constraints.new('CHILD_OF')
    con.name = 'Held by Bunny'
    con.target = arm
    con.subtarget = bone
    bpy.context.view_layer.update()
    con.inverse_matrix = (arm.matrix_world @ arm.pose.bones[bone].matrix).inverted()
    return con


def save_objects(objs, name, category='prop', sub=None, tags=()):
    """Write objects (joined copy) to the library as one asset with a preview."""
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        raise RuntimeError('Select at least one mesh object.')
    item_id = index.unique_id(category + '-' + name)
    dg = bpy.context.evaluated_depsgraph_get()
    import bmesh
    bm = bmesh.new()
    origin = objs[0].matrix_world.translation.copy()
    mats = []
    for o in objs:
        # bake everything except our own ink modifier
        ink = o.modifiers.get(style.MOD_NAME)
        if ink:
            ink.show_viewport = False
            dg.update()
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.transform(Matrix.Translation(-origin) @ o.matrix_world)
        offset = len(mats)
        for m in o.data.materials:
            mats.append(m)
        for p in me.polygons:
            p.material_index += offset
        bm.from_mesh(me)
        ev.to_mesh_clear()
        if ink:
            ink.show_viewport = True
    me = bpy.data.meshes.new(item_id)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    style.compute_creases(me)
    ob = bpy.data.objects.new(item_id, me)
    ob['dsl_id'] = item_id
    ob['dsl_kind'] = category
    ob.asset_mark()
    ob.asset_data.description = name
    for t in tags:
        ob.asset_data.tags.new(t)
    folder = {'prop': 'props', 'scenery': 'scenery', 'card': 'cards'}.get(category, 'props')
    rel = os.path.join(folder, 'user', item_id + '.blend')
    os.makedirs(os.path.dirname(paths.lib_path(rel)), exist_ok=True)
    bpy.data.libraries.write(paths.lib_path(rel), {ob}, fake_user=True, compress=True)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    for o in objs:
        o['dsl_id'] = item_id
    return index.add({'id': item_id, 'name': name, 'category': category, 'kind': 'object', 'sub': sub or 'My assets',
                      'file': rel.replace('\\', '/'), 'datablock': item_id, 'tags': list(tags), 'source': 'blender'})
