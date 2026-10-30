"""Dump Blender's deformed meshes for test poses, to check the JS viewport rig against."""
import bpy, sys, json, os, base64, array
argv = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
sys.path.insert(0, os.path.join(os.path.dirname(argv[0]), 'lib'))
import ds_map
poses = json.load(open(argv[1]))
out = argv[2]
arm = bpy.data.objects['BUNNY_rig']
meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        for m in ob.modifiers:
            if m.type in ('CLOTH', 'NODES', 'COLLISION'):
                m.show_viewport = False
            if m.type == 'SUBSURF':
                m.levels = 1
res = {}
dg = bpy.context.evaluated_depsgraph_get()
for name, vals in poses.items():
    ds_map.apply_pose(arm, meta['controls'], vals, meta['S'])
    bpy.context.view_layer.update()
    dg.update()
    r = {}
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith('BUNNY_') or ob.hide_render or ob.name in ('BUNNY_face', 'BUNNY_head_surface'):
            continue
        e = ob.evaluated_get(dg)
        me = e.to_mesh()
        mw = ob.matrix_world
        r[ob.name] = base64.b64encode(array.array('f', [c for v in me.vertices for c in (mw @ v.co)]).tobytes()).decode()
        e.to_mesh_clear()
    res[name] = r
json.dump(res, open(out, 'w'))
print('dumped', len(res))
