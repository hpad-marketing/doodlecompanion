"""Blender version readiness: the API spots that moved between 4.5, 5.0, 5.1 and 5.2, run for real
in bpy. Every check here once broke (or would break) on 5.x. Run it with each Blender's bpy:
    for py in $BPY45 $BPY50 $BPY51 $BPY52; do "$py" -I tools/test_blender5.py; done
(bpy 4.5 needs Python 3.11, bpy 5.1 needs 3.13; `pip install bpy==5.1.*`.) It opens the shipped
Bunny3D_v2.blend, uses a throwaway library folder, and ends with BLENDER5 PASS or BLENDER5 FAIL."""
import json
import os
import shutil
import sys
import tempfile
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.join(HERE, '..', 'host', 'blender')
sys.path[:0] = [os.path.join(BL, 'lib'), os.path.join(BL, 'addons')]
lib = tempfile.mkdtemp(prefix='dsl5-')
# the real library's .blend files (packs, props...) when DSL_LIBRARY is set; its library.json stays untouched
src = os.environ.get('DSL_LIBRARY')
if src and os.path.isdir(src):
    for n in os.listdir(src):
        if n not in ('library.json', 'storytime', 'motions'):
            os.symlink(os.path.join(src, n), os.path.join(lib, n))
os.makedirs(os.path.join(lib, 'storytime', 'sounds'))
if src and os.path.isdir(os.path.join(src, 'storytime', 'fonts')):
    os.symlink(os.path.join(src, 'storytime', 'fonts'), os.path.join(lib, 'storytime', 'fonts'))
shutil.copy(os.path.join(HERE, 'fixtures', 'beat.wav'), os.path.join(lib, 'storytime', 'sounds', 'pop.wav'))
json.dump({'version': 1, 'items': []}, open(os.path.join(lib, 'library.json'), 'w'))
os.environ['DSL_LIBRARY'] = lib
os.environ['DSL_BUNNY'] = BL

bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'Bunny3D_v2.blend'))
import compat  # noqa: E402
from doodle_library import lighting, motions, storytime, style, text3d  # noqa: E402
import powers  # noqa: E402

print('Blender', bpy.app.version_string)
fails = []


def check(name, fn):
    try:
        r = fn()
        print('ok  ', name, '' if r is None else r)
    except Exception as e:
        fails.append(name)
        print('FAIL', name, '-', e)
        traceback.print_exc(limit=3)


sc = bpy.context.scene
arm = bpy.data.objects['BUNNY_rig']


def t_compat_fcurves():
    ob = bpy.data.objects.new('t_empty', None)
    sc.collection.objects.link(ob)
    for f in (1, 10):
        ob.location.x = f
        ob.keyframe_insert('location', frame=f)
    n = len(list(compat.fcurves(ob)))
    assert n == 3, n
    return f'{n} curves'


def t_compat_strips():
    se = sc.sequence_editor_create()
    s = compat.strips(se).new_sound('t_voice', os.path.join(HERE, 'fixtures', 'beat.wav'), 1, 1)
    assert s and len(compat.strips(se)) >= 1
    compat.strips(se).remove(s)


def t_video_output():
    compat.video_output(sc.render)
    assert sc.render.image_settings.file_format == 'FFMPEG'
    sc.render.image_settings.file_format = 'PNG' if not hasattr(sc.render.image_settings, 'media_type') else sc.render.image_settings.file_format
    if hasattr(sc.render.image_settings, 'media_type'):
        sc.render.image_settings.media_type = 'IMAGE'
        sc.render.image_settings.file_format = 'PNG'


def t_storytime_first_sound():
    if sc.sequence_editor:
        sc.sequence_editor_clear()
    s = storytime.sound('pop', 12)    # an empty 5.x strips list is falsy: this used to fall back to .sequences
    assert s is not None and s.frame_start == 12


def t_motion_curves():
    pb = arm.pose.bones[0]
    for f in (1, 20, 40):
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler.x = f / 40
        pb.keyframe_insert('rotation_euler', frame=f, group=pb.name)
    curves = motions.action_curves(arm.animation_data.action)
    assert curves and curves == motions._fcurves(arm)
    return f'{len(curves)} curves'


def t_save_motion_range():
    it = motions.save_action('T range', frame_range=(1, 20))
    path = os.path.join(lib, it['file'])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.actions = [it['datablock']]
    keys = sorted({kp.co[0] for fc in motions.action_curves(dst.actions[0]) for kp in fc.keyframe_points})
    assert keys and max(keys) <= 20, keys   # 5.x saved every key: the range trim found no curves
    return f'keys {keys}'


def t_lighting_keyed():
    lighting.set_time('night', frame=30)
    st = __import__('doodle_library.style', fromlist=['style']).settings()
    curves = motions.action_curves(st.animation_data.action)
    assert curves and all(k.interpolation == 'CONSTANT' for fc in curves for k in fc.keyframe_points)
    lighting.set_time('day')
    return f'{len(curves)} constant curves'


def t_fisheye():
    powers.fisheye(0.5, print)
    tree = sc.compositing_node_group if hasattr(sc, 'compositing_node_group') else sc.node_tree
    assert tree and any(n.bl_idname == 'CompositorNodeLensdist' for n in tree.nodes)


def t_gn_inputs():
    # 5.2: Geometry Nodes modifier inputs are no longer ID properties (mod["Socket_2"] raises)
    me = bpy.data.meshes.new('t_cube')
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.3); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('t_cube', me)
    sc.collection.objects.link(ob)
    mod = style.apply_style(ob)
    ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}
    assert compat.gn_get(mod, ids['Outline Material']) is not None and compat.gn_get(mod, ids['Outline']) is True
    assert compat.gn_get(mod, ids['Camera']) == sc.camera
    drv = [fc.data_path for fc in (ob.animation_data.drivers if ob.animation_data else [])]
    assert len(drv) >= 6, drv
    bpy.context.view_layer.update()
    return f'{len(drv)} drivers, e.g. {drv[0]}'


def t_text3d():
    ob = text3d.add_text('Hello')
    assert text3d.get_text(ob) == 'Hello'
    text3d.set_text(ob, 'Bye')
    assert text3d.get_text(ob) == 'Bye'
    f = bpy.data.fonts.load('<builtin>')
    text3d.set_font(ob, f.name)


def t_fur():
    import materials
    m = bpy.data.materials.new('t_fill')
    g = materials._fur_group(m, [], {'length': 0.02, 'density': 0.3, 'tilt': 0.3, 'mess': 0.2})
    assert g and len(g.nodes) > 5


def t_fx_and_story():
    if not src:
        return 'skipped (set DSL_LIBRARY for the packs)'
    ob = __import__('doodle_library.fx', fromlist=['fx']).add_effect('rain', frame=1)
    sk = storytime.time_skip('Later...', frame=5)
    bpy.context.view_layer.update()
    return f'{ob.name}, {getattr(sk, "name", sk)}'


def t_floor_bind():
    import collision
    n = collision.bind_shell_floor()
    return f'{n} ink modifiers drive Floor Z'


for name, fn in [('compat.fcurves', t_compat_fcurves), ('compat.strips + new_sound', t_compat_strips),
                 ('compat.video_output', t_video_output), ('storytime: first sound on a fresh sequencer', t_storytime_first_sound),
                 ('motions: action curves', t_motion_curves), ('motions: save a frame range', t_save_motion_range),
                 ('lighting: keyed time of day', t_lighting_keyed), ('powers: fisheye compositor', t_fisheye),
                 ('style: ink modifier inputs and drivers', t_gn_inputs), ('text3d: typed lettering', t_text3d),
                 ('collision: Floor Z drivers on the ink', t_floor_bind),
                 ('fx rain + storytime time skip', t_fx_and_story), ('materials: plush fur nodes', t_fur)]:
    check(name, fn)

shutil.rmtree(lib, ignore_errors=True)
print('BLENDER5', 'PASS' if not fails else 'FAIL ' + ', '.join(fails))
sys.exit(1 if fails else 0)
