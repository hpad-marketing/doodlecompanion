import os
import bpy

C = bpy.context
CASES = []


def case(fn):
    CASES.append((fn.__name__, fn))
    return fn


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    a = bpy.context.preferences.addons.get('creator_toolkit')


def cube(name='Cube', loc=(0, 0, 0), size=2):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    o = C.active_object
    o.name = name
    m = bpy.data.materials.new(name + 'Mat'); m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.2, 0.5, 0.9, 1)
    o.data.materials.append(m)
    return o


@case
def doodle_master_dict():
    import creator_toolkit as ctk
    tools = ctk.DOODLE_MASTER['tools']
    assert len(tools) == 8 and all(t['id'].startswith('tk_') and 61 <= t['order'] <= 69 for t in tools), tools
    total = sum(len(t['sections']) for t in tools)
    assert total == len(ctk.MODULES), total


@case
def draw_every_module():
    import creator_toolkit as ctk

    class FakeLayout:
        def __getattr__(self, k):
            def f(*a, **kw):
                if k in ('operator',):
                    class P:
                        def __setattr__(s, a, b): pass
                    return P()
                return FakeLayout()
            return f
    for m in ctk.MODULES:
        m.draw(FakeLayout(), C)


@case
def vault_save():
    o = cube('VaultCube')
    o.select_set(True)
    r = bpy.ops.ctk.vault_save(kind='OBJECTS', name='Test Cube', category='Props/Test', tags='a, b')
    assert r == {'FINISHED'}, r
    from creator_toolkit.modules import _util
    d = _util.vault_dir()
    assert os.path.exists(os.path.join(d, 'Props', 'Test', 'Test Cube.blend')), os.listdir(d)
    assert 'Props/Test' in open(os.path.join(d, 'blender_assets.cats.txt')).read()
    with bpy.data.libraries.load(os.path.join(d, 'Props', 'Test', 'Test Cube.blend'), assets_only=True) as (src, dst):
        assert 'VaultCube' in src.objects, src.objects
    r = bpy.ops.ctk.vault_save(kind='MATERIAL', name='Blue', category='Materials')
    assert r == {'FINISHED'}


@case
def clean_import():
    o = cube('Messy', size=200)
    o.scale = (1, 1, 1)
    o.select_set(True)
    r = bpy.ops.ctk.clean_selected(target_height=1.5, name='Prop')
    assert r == {'FINISHED'}
    ob = bpy.data.objects['Prop']
    assert abs(ob.dimensions.z - 1.5) < 1e-3, ob.dimensions
    assert min(v.co.z for v in ob.data.vertices) > -1e-4
    # export and reimport an OBJ
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), 'chair.obj')
    bpy.ops.wm.obj_export(filepath=p)
    r = bpy.ops.ctk.import_clean(filepath=p, target_height=0.9)
    assert r == {'FINISHED'} and 'chair_01' in bpy.data.objects, list(bpy.data.objects.keys())


@case
def master_material():
    o = cube('MatCube', loc=(4, 0, 0))
    for s in C.selected_objects:
        s.select_set(False)
    o.select_set(True); C.view_layer.objects.active = o
    for p in ('Clay', 'Glass', 'Toon', 'Metal'):
        assert bpy.ops.ctk.material_apply(preset=p) == {'FINISHED'}
    from creator_toolkit.modules.material import master_node
    n = master_node(o.active_material)
    assert n and abs(n.inputs['Metallic'].default_value - 1) < 1e-6
    assert abs(n.inputs['Color'].default_value[2] - 0.9) < 1e-3  # kept blue
    from creator_toolkit.modules import material
    material.CTK_OT_material_save_preset  # noqa
    assert bpy.ops.ctk.material_convert(scope='FILE') == {'FINISHED'}
    assert 'CubeMat' in material.presets() or 'VaultCubeMat' in material.presets() or len(material.presets()) > len(material.BUILTIN)


@case
def style_switch():
    o = cube('StyleCube', loc=(-4, 0, 0))
    for s in C.selected_objects:
        s.select_set(False)
    o.select_set(True); C.view_layer.objects.active = o
    orig = o.active_material.name
    for st in ('FLAT', 'CEL', 'COMIC', 'CLAY', 'PAPER', 'DOODLE', 'INK'):
        assert bpy.ops.ctk.style_apply(style=st) == {'FINISHED'}, st
    assert o.modifiers.get('CTK Ink')
    assert bpy.ops.ctk.style_revert() == {'FINISHED'}
    assert o.material_slots[0].material.name == orig and not o.modifiers.get('CTK Ink')


@case
def palette():
    bpy.ops.mesh.primitive_plane_add(size=20); fl = C.active_object; fl.name = 'Floor'
    m = bpy.data.materials.new('FloorMat'); m.use_nodes = True; fl.data.materials.append(m)
    a = cube('PalA', loc=(0, 3, 1)); b = cube('PalB', loc=(0, -3, 1))
    b.active_material = bpy.data.materials.new('B'); b.active_material.use_nodes = True
    b['dm_lock'] = True
    before = tuple(b.active_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)
    assert bpy.ops.ctk.palette_apply(kit='Teal + coral', reguess=True) == {'FINISHED'}
    assert m.get('ctk_role') == 'floor', m.get('ctk_role')
    assert tuple(b.active_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value) == before
    img = bpy.data.images.new('t', 32, 32)
    import numpy as np
    px = np.zeros((32, 32, 4), np.float32); px[..., 3] = 1
    px[:16, :, 0] = 1; px[16:, :16, 2] = 1; px[16:, 16:, :3] = 0.9
    img.pixels.foreach_set(px.ravel())
    from creator_toolkit.modules.palette import extract_palette
    hx = extract_palette(img, 5)
    assert len(hx) == 5 and all(h.startswith('#') for h in hx), hx


@case
def light_rigs():
    o = cube('LitCube')
    for s in C.selected_objects:
        s.select_set(False)
    o.select_set(True)
    from creator_toolkit.modules.lights import PRESETS
    for p in PRESETS:
        assert bpy.ops.ctk.light_rig(preset=p) == {'FINISHED'}, p
    rig = bpy.data.objects['CTK Light Rig']
    assert len(rig.children) == len(PRESETS['Flat illustration'])
    name = rig.children[0].name
    assert bpy.ops.ctk.light_solo(name=name) == {'FINISHED'}
    assert bpy.ops.ctk.light_solo(name=name) == {'FINISHED'}


def select_only(o):
    for s in C.selected_objects:
        s.select_set(False)
    o.select_set(True)
    C.view_layer.objects.active = o


@case
def rig_builder_and_springs():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.4, depth=2, location=(0, 0, 1))
    body = C.active_object
    body.name = 'Body'
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=8)
    bpy.ops.object.mode_set(mode='OBJECT')
    p = C.scene.ctk_rig
    p.use_ears = True
    p.use_tail = True
    select_only(body)
    assert bpy.ops.ctk.rig_markers() == {'FINISHED'}
    assert bpy.data.objects.get('M:ear.L')
    assert bpy.ops.ctk.rig_build() == {'FINISHED'}
    rig = bpy.data.objects['Body Rig']
    names = set(rig.pose.bones.keys())
    for n in ('hips', 'head', 'upper_arm.R', 'IK_foot.L', 'ear_tip.R', 'tail.3'):
        assert n in names, (n, names)
    assert body.parent == rig and len(body.vertex_groups) > 5
    assert 'IK arm L' in rig.keys()
    # picker selects bones (5.x keeps selection on pose bones)
    select_only(rig)
    assert bpy.ops.ctk.rig_pick(bone='head') == {'FINISHED'}
    pbh = rig.pose.bones['head']
    assert (pbh.select if hasattr(pbh, 'select') else rig.data.bones['head'].select)
    bpy.ops.object.mode_set(mode='OBJECT')
    # FK/IK driver works
    rig['IK arm L'] = 0.0
    rig.update_tag(); C.view_layer.update()
    assert rig.pose.bones['forearm.L'].constraints['CTK IK'].influence == 0.0
    # springs: move the head and check the ear lags then settles
    select_only(rig)
    bpy.ops.object.mode_set(mode='POSE')
    head = rig.pose.bones['head']
    head.rotation_mode = 'XYZ'
    sc = C.scene
    sc.frame_start, sc.frame_end = 1, 40
    head.rotation_euler = (0, 0, 0); head.keyframe_insert('rotation_euler', frame=1)
    head.rotation_euler = (0, 0.8, 0); head.keyframe_insert('rotation_euler', frame=5)
    bpy.ops.object.mode_set(mode='OBJECT')
    lags = []
    for f in range(1, 41):
        sc.frame_set(f)
        lags.append(abs(rig.pose.bones['ear_tip.L'].get('ctk_L', [1, 0, 0, 0])[0] - 1))
    assert max(lags[3:10]) > 1e-4, lags
    assert lags[-1] < max(lags), lags
    select_only(rig)
    assert bpy.ops.ctk.spring_bake() == {'FINISHED'}
    assert rig.pose.bones['ear.L'].get('ctk_spring_baked')


@case
def mocap_retarget():
    rig = bpy.data.objects['Body Rig']
    # make a fake source skeleton with Mixamo names by duplicating our rig and renaming
    src = rig.copy(); src.data = rig.data.copy(); src.animation_data_clear()
    C.scene.collection.objects.link(src)
    ren = {'hips': 'mixamorig:Hips', 'chest': 'mixamorig:Spine2', 'head': 'mixamorig:Head',
           'upper_arm.L': 'mixamorig:LeftArm', 'forearm.L': 'mixamorig:LeftForeArm'}
    for a, b in ren.items():
        src.data.bones[a].name = b
    for pb in src.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    pb = src.pose.bones['mixamorig:LeftArm']
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0); pb.keyframe_insert('rotation_euler', frame=1)
    pb.rotation_euler = (0.9, 0, 0); pb.keyframe_insert('rotation_euler', frame=10)
    from creator_toolkit.modules.mocap import retarget
    bmap, rng = retarget(C, src, rig, 1, 10)
    assert bmap.get('upper_arm.L') == 'mixamorig:LeftArm', bmap
    C.scene.frame_set(10)
    C.view_layer.update()
    a = (src.matrix_world @ src.pose.bones['mixamorig:LeftArm'].tail)
    b = (rig.matrix_world @ rig.pose.bones['upper_arm.L'].tail)
    assert (a - b).length < 1e-3, (a, b)


@case
def thing_rigs():
    bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0)); door = C.active_object
    C.scene.cursor.location = (4, 0, 0)
    assert bpy.ops.ctk.thing_rig(kind='HINGE', axis='Z') == {'FINISHED'}
    piv = C.active_object
    piv['open'] = 1.0
    piv.update_tag(); C.view_layer.update()
    assert abs(piv.rotation_euler.z - 1.9199) < 1e-3, piv.rotation_euler
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.2, location=(8, 0, 0.5)); wh = C.active_object
    assert bpy.ops.ctk.thing_rig(kind='WHEEL', axis='X') == {'FINISHED'}
    ctl = C.active_object
    ctl.location.y += 3.14159 * 0.5 * 2
    ctl.update_tag(); C.view_layer.update()
    assert abs(abs(wh.rotation_euler.x) - 6.2832) < 0.01, wh.rotation_euler
    bpy.ops.mesh.primitive_cube_add(location=(0, 6, 0)); sq = C.active_object
    for k in ('SQUASH', 'BEND', 'LOOK'):
        select_only(sq)
        assert bpy.ops.ctk.thing_rig(kind=k) == {'FINISHED'}, k
    bpy.ops.curve.primitive_bezier_circle_add(radius=3); cv = C.active_object
    bpy.ops.mesh.primitive_cube_add(size=0.3); car = C.active_object
    cv.select_set(True)
    assert bpy.ops.ctk.thing_rig(kind='FOLLOW', frames=50) == {'FINISHED'}


@case
def motion_presets():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obs = []
    for i in range(3):
        bpy.ops.mesh.primitive_cube_add(location=(i * 3, 0, 0))
        obs.append(C.active_object)
    for o in obs:
        o.select_set(True)
    from creator_toolkit.modules.motion import PRESETS
    for k, _ in PRESETS:
        C.scene.frame_set(1)
        assert bpy.ops.ctk.motion_preset(kind=k, duration=20, stagger=4) == {'FINISHED'}, k
    C.scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_cube_add(location=(0, 8, 0)); o = C.active_object
    assert bpy.ops.ctk.motion_preset(kind='POP_IN', duration=10, stagger=0) == {'FINISHED'}
    C.scene.frame_set(1); assert o.scale.x < 0.01
    C.scene.frame_set(11); assert abs(o.scale.x - 1) < 1e-4


@case
def tween_and_ease():
    bpy.ops.mesh.primitive_cube_add(location=(0, 20, 0)); o = C.active_object
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); C.view_layer.objects.active = o
    o.location.x = 0; o.keyframe_insert('location', index=0, frame=1)
    o.location.x = 10; o.keyframe_insert('location', index=0, frame=21)
    C.scene.frame_set(11)
    assert bpy.ops.ctk.breakdown('EXEC_DEFAULT', factor=0.25) == {'FINISHED'}
    C.scene.frame_set(1); C.scene.frame_set(11)
    assert abs(o.location.x - 2.5) < 1e-3, o.location.x
    for k in ('SNAP', 'OVERSHOOT', 'SMOOTH'):
        assert bpy.ops.ctk.ease(kind=k, only_selected_keys=False) == {'FINISHED'}
    from creator_toolkit.compat import fcurves_of
    assert all(kp.interpolation == 'BEZIER' for fc in fcurves_of(o) for kp in fc.keyframe_points)


    # anim offset: change the pose on one frame, every key moves by the same amount
    C.scene.ctk_offset.span = 'ALL'
    o.animation_data_clear()
    o.location.x = 0; o.keyframe_insert('location', index=0, frame=1)
    o.location.x = 10; o.keyframe_insert('location', index=0, frame=21)
    C.scene.frame_set(11)
    o.location.x += 3
    assert bpy.ops.ctk.anim_offset() == {'FINISHED'}
    ys = sorted(round(k.co.y, 4) for fc in fcurves_of(o) for k in fc.keyframe_points)
    assert ys == [3.0, 13.0], ys
    # around the playhead: the far key keeps most of its value
    C.scene.ctk_offset.span = 'AROUND'; C.scene.ctk_offset.hold = 0; C.scene.ctk_offset.blend = 15
    C.scene.frame_set(1)
    o.location.x += 2
    bpy.ops.ctk.anim_offset()
    ys = [k.co.y for fc in fcurves_of(o) for k in sorted(fc.keyframe_points, key=lambda k: k.co.x)]
    assert abs(ys[0] - 5.0) < 1e-4 and abs(ys[1] - 13.0) < 1e-4, ys
    # live mode through the update handler
    C.scene.ctk_offset.span = 'ALL'; C.scene.ctk_offset.live = True
    o.location.x += 1
    C.view_layer.update()
    ys2 = [k.co.y for fc in fcurves_of(o) for k in sorted(fc.keyframe_points, key=lambda k: k.co.x)]
    assert [round(y, 4) for y in ys2] == [6.0, 14.0], ys2
    C.scene.ctk_offset.live = False

    # silhouette view round trip (scene shading has the same settings as a viewport)
    from creator_toolkit.modules import tween
    sh = C.scene.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
    assert tween.silhouette(sh, True, 'test')
    assert sh.light == 'FLAT' and sh.color_type == 'SINGLE' and not sh.show_cavity
    assert tween.silhouette(sh, False, 'test')
    assert sh.light == 'STUDIO' and sh.color_type == 'MATERIAL' and sh.show_cavity

def _voice_wav(path, seconds=3.0):
    import wave
    import numpy as np
    rate = 16000
    t = np.arange(int(rate * seconds)) / rate
    env = (np.sin(t * 2 * np.pi * 2.5) > 0).astype(float) * (0.3 + 0.7 * (np.sin(t * 2 * np.pi * 0.7) > 0))
    sig = env * (np.sin(t * 2 * np.pi * 180) + 0.4 * np.sign(np.sin(t * 2 * np.pi * 2200)) * (t % 1 > 0.5))
    pcm = (sig / np.abs(sig).max() * 30000).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())


@case
def lip_sync():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), 'voice.wav')
    _voice_wav(p)
    bpy.ops.mesh.primitive_plane_add(location=(0, 30, 0)); m = C.active_object
    m.shape_key_add(name='Basis')
    for n in ('rest', 'closed', 'mid', 'open', 'wide', 'round', 'oo'):
        m.shape_key_add(name=n)
    lp = C.scene.ctk_lip
    lp.source = 'FILE'; lp.filepath = p; lp.target = 'SHAPEKEYS'
    assert bpy.ops.ctk.lipsync() == {'FINISHED'}
    kb = m.data.shape_keys.key_blocks
    from creator_toolkit.compat import fcurves_of
    ad = m.data.shape_keys.animation_data
    assert ad and ad.action, 'no keys'
    # property target for 2D swaps
    lp.target = 'PROPERTY'; lp.mapping = 'X=0, A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8'
    assert bpy.ops.ctk.lipsync() == {'FINISHED'}
    vals = set()
    for f in range(1, 80):
        C.scene.frame_set(f)
        vals.add(m.get('mouth'))
    assert len(vals) >= 3, vals
    # sound strip source
    se = C.scene.sequence_editor_create()
    from creator_toolkit.compat import strips
    strips(C.scene).new_sound('v', p, 1, 10)
    lp.source = 'STRIPS'
    assert bpy.ops.ctk.lipsync() == {'FINISHED'}


@case
def kinetic_type():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules.kinetic import STYLES
    for k, *_ in STYLES:
        assert bpy.ops.ctk.kinetic_text('EXEC_DEFAULT', text='Hi there', style=k, split='LETTER') == {'FINISHED'}, k
    assert bpy.ops.ctk.kinetic_text('EXEC_DEFAULT', text='Two lines\nhere', split='WORD') == {'FINISHED'}
    import tempfile
    svg = os.path.join(tempfile.mkdtemp(), 'logo.svg')
    open(svg, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect x="0" y="0" width="40" height="40"/><circle cx="70" cy="20" r="18"/></svg>')
    for st in ('DRAW', 'POP', 'EXTRUDE', 'DROP'):
        assert bpy.ops.ctk.logo_reveal(filepath=svg, style=st) == {'FINISHED'}, st


@case
def camera_moves():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_monkey_add()
    from creator_toolkit.modules.camera import MOVES, SHAKES
    for k, _ in MOVES:
        C.scene.frame_set(1)
        assert bpy.ops.ctk.camera_move(kind=k, seconds=1, bpm=120) == {'FINISHED'}, k
    for p in SHAKES:
        assert bpy.ops.ctk.camera_shake(preset=p) == {'FINISHED'}
    cam = C.scene.camera
    a = cam.matrix_world.translation.copy(); C.scene.frame_set(7); b = cam.matrix_world.translation.copy()
    assert (a - b).length > 0
    assert bpy.ops.ctk.camera_shake(remove=True) == {'FINISHED'}
    assert bpy.ops.ctk.beat_markers(bpm=120) == {'FINISHED'} and len(C.scene.timeline_markers) > 5


@case
def gn_kit():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import bmesh
    from creator_toolkit.modules import gnkit
    bpy.ops.mesh.primitive_plane_add(size=4)
    ground = C.active_object
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(5, 0, 0))
    rock = C.active_object
    bpy.ops.curve.primitive_bezier_curve_add()
    path = C.active_object
    base = len(ground.evaluated_get(C.evaluated_depsgraph_get()).data.vertices)
    for k, _, _ in gnkit.KINDS:
        tgt = path if k in gnkit.NEEDS_CURVE else ground
        bpy.ops.object.select_all(action='DESELECT')
        if k in gnkit.NEEDS_COPY:
            rock.hide_set(False); rock.select_set(True)
        tgt.select_set(True); C.view_layer.objects.active = tgt
        assert bpy.ops.ctk.gn_add(kind=k) == {'FINISHED'}, k
        dg = C.evaluated_depsgraph_get()
        ev = tgt.evaluated_get(dg)
        m = ev.to_mesh()
        n = len(m.vertices) if m else 0
        if k == 'WOBBLE':
            moved = max((m.vertices[i].co - ground.data.vertices[i].co).length for i in range(4))
            assert moved > 1e-4, moved
            n = 99
        ev.to_mesh_clear()
        inst = sum(1 for d in dg.object_instances if d.is_instance and d.parent and d.parent.original == tgt)
        n += inst
        assert n > (4 if tgt == ground else 0) and (k not in gnkit.NEEDS_COPY or inst > 1), (k, n, inst)
        print('  gn', k, n)
        for md in list(tgt.modifiers):
            tgt.modifiers.remove(md)


@case
def gp_kit():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import gpkit
    assert bpy.ops.ctk.gp_canvas(ink='Ink') == {'FINISHED'}
    o = C.active_object
    assert o.type == 'GREASEPENCIL'
    dr = o.data.layers[0].frames[0].drawing if len(o.data.layers[0].frames) else o.data.layers[0].frames.new(1).drawing
    import math
    def ring(r, n=24, cx=0.0):
        return [(cx + r * math.cos(a * 2 * math.pi / n), 0, r * math.sin(a * 2 * math.pi / n)) for a in range(n + 1)]
    shapes = [ring(1.0), ring(0.4), ring(0.3, cx=3.0), [(0, 0, 0), (1, 0, 1), (2, 0, 0)]]
    dr.add_strokes([len(s) for s in shapes])
    for st, pts in zip(dr.strokes, shapes):
        for p, co in zip(st.points, pts):
            p.position = co
            p.radius = 0.02
    for k in ('DRAW_ON', 'BOIL', 'POP', 'EVEN'):
        assert bpy.ops.ctk.gp_effect(kind=k) == {'FINISHED'}, k
    assert {m.type for m in o.modifiers} >= {'GREASE_PENCIL_BUILD', 'GREASE_PENCIL_NOISE', 'GREASE_PENCIL_THICKNESS'}
    assert bpy.ops.ctk.gp_fill() == {'FINISHED'}
    assert len(dr.strokes) == 7, len(dr.strokes)
    fills = [s for s in dr.strokes if o.data.materials[s.material_index].grease_pencil.show_fill]
    assert len(fills) == 3, len(fills)
    if hasattr(dr.strokes[0], 'fill_id'):
        ids = sorted(s.fill_id for s in fills)
        assert ids.count(ids[-1]) >= 2, ids  # outer ring + hole share a fill
    for p in gpkit.ONION:
        assert bpy.ops.ctk.gp_onion(preset=p) == {'FINISHED'}
    assert bpy.ops.ctk.gp_effect(kind='CLEAR') == {'FINISHED'} and not any(m.name.startswith('CTK ') for m in o.modifiers)
    bpy.ops.mesh.primitive_monkey_add()
    cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); C.scene.collection.objects.link(cam)
    cam.location = (0, -6, 0); cam.rotation_euler = (1.5708, 0, 0); C.scene.camera = cam
    assert bpy.ops.ctk.gp_ink3d(source='SCENE') == {'FINISHED'}


@case
def node_tidy():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    o = C.active_object
    m = bpy.data.materials.new('T'); m.use_nodes = True; o.data.materials.append(m)
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise'); ramp = nt.nodes.new('ShaderNodeValToRGB'); junk = nt.nodes.new('ShaderNodeMath')
    for n in (tex, ramp, junk):
        n.location = (500, 500)
    nt.links.new(tex.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], nt.nodes['Principled BSDF'].inputs['Base Color'])
    assert bpy.ops.ctk.node_tidy() == {'FINISHED'}
    assert tex.location.x < ramp.location.x < nt.nodes['Principled BSDF'].location.x < nt.nodes['Material Output'].location.x
    assert bpy.ops.ctk.node_clean() == {'FINISHED'}
    assert junk.name not in nt.nodes
    for n in nt.nodes:
        n.select = True
    assert bpy.ops.ctk.node_frame(label='Look') == {'FINISHED'}
    assert any(n.type == 'FRAME' for n in nt.nodes)


@case
def pie_and_updates():
    import creator_toolkit as ctk
    from creator_toolkit.modules import updates
    assert hasattr(bpy.types, 'CTK_MT_pie')
    assert updates._v('1.2.10') > updates._v('1.2.9') and updates.installed_version() == '1.0.0'
    assert bpy.ops.ctk.keydial_text() == {'FINISHED'} and 'Shift+Q' in bpy.data.texts['Keydial shortcuts'].as_string()
    km = bpy.context.window_manager.keyconfigs.addon
    if km:
        names = [k.idname for m in km.keymaps for k in m.keymap_items]
        assert 'wm.call_menu_pie' in names


@case
def deliver_panel():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import deliver
    sc = C.scene
    d = sc.ctk_deliver
    d.project = 'Test Reel'; d.fmt = 'Reel 9:16 (1080x1920)'
    for c, *_ in deliver.COLOURS:
        d.colour = c
        assert bpy.ops.ctk.deliver_setup() == {'FINISHED'}, c
    assert (sc.render.resolution_x, sc.render.resolution_y) == (1080, 1920)
    assert sc.render.image_settings.file_format == 'FFMPEG' and sc.render.ffmpeg.codec in ('H264', 'H265')
    assert 'Test Reel_v001' in sc.render.filepath and '/work/renders' in sc.render.filepath.replace('\\', '/')
    d.preview = True
    bpy.ops.ctk.deliver_setup()
    assert sc.render.resolution_percentage == 50 and '_preview' in sc.render.filepath
    d.preview = False
    bpy.ops.ctk.deliver_setup()
    assert sc.render.resolution_percentage == 100
    d.output = 'PNG'
    bpy.ops.ctk.deliver_setup()
    assert sc.render.image_settings.file_format == 'PNG'
    folder, name = deliver.project_dir(sc)
    work = os.path.join(folder, 'work', 'renders')
    open(os.path.join(work, name + '_v007.mp4'), 'w').write('x')
    assert bpy.ops.ctk.deliver_final() == {'FINISHED'} and os.path.exists(os.path.join(folder, name + '.mp4'))
    deliver.save_queue([{'id': '1', 'file': '/x/a.blend', 'scene': 'S', 'start': 1, 'end': 9, 'status': 'waiting'}])
    cmd = deliver.command(deliver.queue()[0], 'blender')
    assert cmd == ['blender', '-b', '/x/a.blend', '-S', 'S', '-s', '1', '-e', '9', '-a'], cmd
    assert bpy.ops.ctk.queue_clear(everything=True) == {'FINISHED'} and deliver.queue() == []


@case
def turntable_and_sheet():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_monkey_add()
    from creator_toolkit.modules import turntable
    assert bpy.ops.ctk.turntable(seconds=2, mode='ORBIT') == {'FINISHED'}
    sc = C.scene
    cam = sc.camera
    sc.frame_set(sc.frame_start); a = cam.matrix_world.translation.copy()
    sc.frame_set(sc.frame_start + 15); b = cam.matrix_world.translation.copy()
    assert (a - b).length > 0.5 and sc.frame_end == sc.frame_start + 2 * sc.render.fps - 1
    assert bpy.ops.ctk.turntable(seconds=2, mode='SPIN') == {'FINISHED'}
    assert bpy.ops.ctk.clay(on=True) == {'FINISHED'} and C.view_layer.material_override
    bpy.ops.ctk.clay(on=False)
    import tempfile
    tmp = tempfile.mkdtemp()
    paths = []
    for i, col in enumerate([(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1)]):
        im = bpy.data.images.new('t%d' % i, 20, 10)
        im.pixels[:] = col * 200
        p = os.path.join(tmp, 't%d.png' % i); im.filepath_raw = p; im.file_format = 'PNG'; im.save(); paths.append(p)
    out = turntable.contact_sheet(paths, os.path.join(tmp, 'sheet.png'), columns=2, gap=4)
    im = bpy.data.images.load(out)
    assert tuple(im.size) == (2 * 20 + 3 * 4, 2 * 10 + 3 * 4), tuple(im.size)


@case
def starter_templates():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import templates
    for k, *_ in templates.KINDS:
        assert bpy.ops.ctk.template_new(kind=k) == {'FINISHED'}, k
        sc = bpy.data.scenes[-1] if not C.window else C.scene
    sc = next(s for s in bpy.data.scenes if s.name.startswith('Social reel'))
    assert sc.render.resolution_y == 1920 and 'IG safe zone' in [o.name for o in sc.objects] and sc.camera
    sz = sc.objects['IG safe zone']; assert sz.hide_render
    p = templates.save_mine(sc, 'My reel')
    assert os.path.exists(p) and 'My reel' in templates.my_templates()
    s2 = templates.load_mine('My reel')
    assert s2.render.resolution_y == 1920


@case
def doodle_library_browser():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import json, tempfile
    lib = tempfile.mkdtemp()
    os.environ['DSL_LIBRARY'] = lib
    bpy.ops.mesh.primitive_cube_add(); cub = C.active_object; cub.name = 'PROP_mug'
    os.makedirs(os.path.join(lib, 'props')); os.makedirs(os.path.join(lib, 'previews', 'prop'))
    bpy.data.libraries.write(os.path.join(lib, 'props', 'mug.blend'), {cub})
    im = bpy.data.images.new('p', 8, 8); im.filepath_raw = os.path.join(lib, 'previews', 'prop', 'prop-mug.png'); im.file_format = 'PNG'; im.save()
    json.dump({'version': 1, 'items': [
        {'id': 'prop-mug', 'category': 'prop', 'name': 'Mug', 'file': 'props/mug.blend', 'datablock': 'PROP_mug',
         'preview': 'previews/prop/prop-mug.png', 'tags': ['kitchen']},
        {'id': 'face-01', 'category': 'expression', 'name': 'Happy'}]}, open(os.path.join(lib, 'library.json'), 'w'))
    bpy.data.objects.remove(cub)
    from creator_toolkit.modules import doodle
    doodle._cache['mtime'] = None
    p = C.scene.ctk_doodle
    p.category = 'prop'
    items = doodle._items(p, C)
    assert items[0][0] == 'prop-mug' and len(doodle._previews()) == 1, items  # icon ids are 0 without a GPU
    p.search = 'kitch'
    assert doodle.filtered('prop', 'kitch')
    assert bpy.ops.ctk.doodle_insert(item='prop-mug') == {'FINISHED'}
    assert any(o.get('dsl_id') == 'prop-mug' for o in C.scene.objects)
    if not doodle.dl_api():
        try:
            doodle.insert('face-01')
            raise AssertionError('should need the add-on')
        except RuntimeError:
            pass
    del os.environ['DSL_LIBRARY']


@case
def physics_52():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import physics52 as ph
    if not ph.available():
        print('  (skipped: needs 5.2)')
        return
    sc = C.scene
    a = bpy.data.objects.new('A', None); b = bpy.data.objects.new('B', None)
    for o, l in ((a, (-1, 0, 2)), (b, (1, 0, 2))):
        sc.collection.objects.link(o); o.location = l
    def ev_pts(ob):
        e = ob.evaluated_get(C.evaluated_depsgraph_get())
        if ob.type == 'CURVES':
            return [e.matrix_world @ p.position for p in e.data.points]
        return [e.matrix_world @ v.co for v in e.data.vertices]
    for k in ph.ROPES:
        sc.frame_set(1)
        bpy.ops.object.select_all(action='DESELECT')
        a.select_set(True); b.select_set(True); C.view_layer.objects.active = b
        assert bpy.ops.ctk.rope(kind=k) == {'FINISHED'}, k
    rope = next(o for o in sc.objects if o.get('ctk_rope') == 'ROPE')
    sc.frame_set(1)
    p0 = ev_pts(rope)
    assert abs(p0[0].x + 1) < 0.05 and abs(p0[0].z - 2) < 0.05, p0[0]  # pinned at A, not doubled
    b.keyframe_insert('location', frame=1); b.location.z += 1.0; b.keyframe_insert('location', frame=6)
    for f in range(2, 16):
        sc.frame_set(f)
    p1 = ev_pts(rope)
    mid = len(p1) // 2
    assert (p1[mid] - p0[mid]).length > 0.1, ('rope does not follow', p0[mid], p1[mid])
    assert abs(p1[0].x + 1) < 0.05 and abs(p1[-1].z - 3) < 0.1, ('pins', p1[0], p1[-1])
    bpy.ops.mesh.primitive_cube_add(location=(4, 0, 1))
    body = C.active_object
    for k in ph.CLOTHS:
        C.view_layer.objects.active = body
        assert bpy.ops.ctk.cloth_preset(kind=k) == {'FINISHED'}, k
    for k in ph.HAIRS:
        C.view_layer.objects.active = body
        assert bpy.ops.ctk.hair_preset(kind=k) == {'FINISHED'}, k
    pony = next(o for o in sc.objects if o.name.startswith('Ponytail'))
    sc.frame_set(1)
    body.keyframe_insert('location', frame=1); body.location.x += 1.5; body.keyframe_insert('location', frame=8)
    tips = []
    for f in range(1, 12):
        sc.frame_set(f)
        pts = ev_pts(pony)
        tips.append((pts[9] - pts[0]).x)  # tip relative to root: lags when the body moves
    assert max(abs(t) for t in tips) > 0.02, tips


def _test_wav():
    import numpy as np, wave, tempfile
    p = os.path.join(tempfile.mkdtemp(), 'beat.wav'); sr = 44100
    t = np.arange(sr * 2) / sr
    sig = np.where(t < 1, np.sin(2 * np.pi * 80 * t), np.sin(2 * np.pi * 5000 * t)) * 0.8
    w = wave.open(p, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((sig * 32767).astype('<i2').tobytes()); w.close()
    return p


@case
def music_kit():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import music
    from creator_toolkit.compat import strips
    sc = C.scene
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 48
    p = _test_wav()
    strips(sc).new_sound('beat', p, 1, 1)
    # bones: works in every version
    arm = bpy.data.armatures.new('A'); ob = bpy.data.objects.new('A', arm); sc.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones.new('ear.L'); eb.head = (0, 0, 0); eb.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='POSE')
    n = music.bop_bones(C, [ob.pose.bones['ear.L']], 20, 'Bass')
    bpy.ops.object.mode_set(mode='OBJECT')
    assert n == 48
    sc.frame_set(10); a = ob.pose.bones['ear.L'].rotation_euler.x
    sc.frame_set(40); b = ob.pose.bones['ear.L'].rotation_euler.x
    assert a > b + 0.1, (a, b)  # bass in the first second only
    if not music.available():
        print('  (visualizer skipped: needs 5.2)')
        return
    for k, *_ in music.LOOKS:
        assert bpy.ops.ctk.visualizer(look=k) == {'FINISHED'}, k
    def size(o):
        e = o.evaluated_get(C.evaluated_depsgraph_get())
        zs = [v.co.z for v in e.data.vertices]
        return (max(zs) - min(zs)) if zs else 0
    bars = next(o for o in sc.objects if o.name.startswith('Visualizer Bars'))
    sc.frame_set(12); loud = size(bars)
    assert loud > 0.3, loud
    for o in sc.objects:
        if o.name.startswith('Visualizer'):
            assert size(o) > 0, o.name
    bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0))
    cube = C.active_object
    m = bpy.data.materials.new('C'); m.use_nodes = True; cube.data.materials.append(m)
    for how, *_ in music.REACTS:
        assert bpy.ops.ctk.react(how=how) == {'FINISHED'}, how
    bpy.ops.ctk.react(how='SCALE')
    sc.frame_set(12)
    e = cube.evaluated_get(C.evaluated_depsgraph_get())
    assert max(v.co.x for v in e.data.vertices) > 1.05
    assert 'ctk_glow' in e.data.attributes and 'CTK glow' in m.node_tree.nodes


@case
def speed_playback_online_pin():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import speed, playback, vault
    sc = C.scene
    before = sc.render.use_simplify
    assert bpy.ops.ctk.heavy_scene(on=True) == {'FINISHED'} and sc.render.use_simplify and speed.is_heavy(sc)
    if hasattr(sc.render, 'use_texture_cache'):
        assert sc.render.use_texture_cache
    assert bpy.ops.ctk.heavy_scene(on=False) == {'FINISHED'} and sc.render.use_simplify == before and not speed.is_heavy(sc)
    sc.frame_set(1); sc['ctk_bpm'] = 120
    bpy.ops.ctk.jump(amount=1, unit='BEAT')
    assert sc.frame_current == 1 + round(sc.render.fps / 2), sc.frame_current
    if hasattr(sc, 'playback_loop_mode'):
        assert bpy.ops.ctk.loop_mode(mode='BOUNCE') == {'FINISHED'} and sc.playback_loop_mode == 'BOUNCE'
    cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0, -5, 1)
    bpy.ops.mesh.primitive_plane_add(location=(0, -3, 1)); lab = C.active_object
    assert bpy.ops.ctk.pin_to_camera(how='FOLLOW') == {'FINISHED'} and lab.parent == cam
    C.view_layer.update(); w0 = lab.matrix_world.translation.copy()
    assert (w0 - __import__('mathutils').Vector((0, -3, 1))).length < 1e-4, w0
    cam.location.x += 2; C.view_layer.update()
    assert abs(lab.matrix_world.translation.x - 2) < 1e-4
    assert bpy.ops.ctk.pin_to_camera(how='FREE') == {'FINISHED'} and lab.parent is None
    if vault.online_supported():
        bpy.ops.mesh.primitive_cube_add(); o = C.active_object
        assert bpy.ops.ctk.vault_save(kind='OBJECTS', name='Online cube', category='Props', tags='') == {'FINISHED'}
        d = vault.publish_listing()
        found = [f for r, _, fs in os.walk(d) for f in fs if f.endswith('.json') and 'asset' in f]
        assert found, os.listdir(d)
        lib = vault.add_online('https://example.org/vault/')
        assert lib.use_remote_url and lib.remote_url == 'https://example.org/vault/'
        bpy.context.preferences.filepaths.asset_libraries.remove(lib)


@case
def blobs_smoke_soft():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import shapes52 as sh
    sc = C.scene
    def nverts(o):
        e = o.evaluated_get(C.evaluated_depsgraph_get()); return len(e.data.vertices)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(8, 0, 0)); cube = C.active_object
    assert bpy.ops.ctk.soft_toy() == {'FINISHED'}
    assert nverts(cube) > 8
    if not sh.sdf_available():
        print('  (blob/smoke skipped: needs 5.2)')
        return
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0)); a = C.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0.7, 0, 0)); b = C.active_object
    a.select_set(True); b.select_set(True)
    assert bpy.ops.ctk.blob() == {'FINISHED'}
    blob = C.active_object
    assert nverts(blob) > 100 and a.hide_render
    assert bpy.ops.ctk.blob_apply() == {'FINISHED'} and len(blob.modifiers) == 0 and len(blob.data.vertices) > 100
    for k, *_ in sh.SMOKES:
        assert bpy.ops.ctk.toon_smoke(kind=k) == {'FINISHED'}, k
    trail = next(o for o in sc.objects if o.name.startswith('Smoke trail'))
    sc.frame_set(10); n1 = nverts(trail)
    e = trail.evaluated_get(C.evaluated_depsgraph_get()); z1 = max(v.co.z for v in e.data.vertices)
    sc.frame_set(30); e = trail.evaluated_get(C.evaluated_depsgraph_get())
    assert n1 > 50 and abs(max(v.co.z for v in e.data.vertices) - z1) > 1e-3


@case
def speed_trails():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from creator_toolkit.modules import smear52
    if not smear52.available():
        print('  (speed lines skipped: needs 5.2)')
        return
    sc = C.scene
    arm = bpy.data.armatures.new('A'); ob = bpy.data.objects.new('A', arm); sc.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones.new('hand'); eb.head = (0, 0, 0); eb.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='POSE')
    pb = ob.pose.bones['hand']
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler.x = 0; pb.keyframe_insert('rotation_euler', frame=1)
    pb.rotation_euler.x = 2.5; pb.keyframe_insert('rotation_euler', frame=8)
    if hasattr(pb, 'select'):
        pb.select = True
    else:
        arm.bones['hand'].select = True
    assert bpy.ops.ctk.speed_trail() == {'FINISHED'}
    bpy.ops.object.mode_set(mode='OBJECT')
    tr = next(o for o in sc.objects if o.name.startswith('Speed trail'))
    counts = []
    for f in range(1, 16):
        sc.frame_set(f)
        e = tr.evaluated_get(C.evaluated_depsgraph_get())
        counts.append(len(e.data.vertices))
    assert max(counts[2:8]) > 12, counts
    e = tr.evaluated_get(C.evaluated_depsgraph_get())
    zs = [v.co for v in e.data.vertices]
    print('  trail radius range', min(v.length for v in zs), max(v.length for v in zs), 'frames', counts)
    assert all(abs(v.length - 1.0) < 0.2 for v in zs), 'trail is not at the bone tip'
    assert counts[-1] == 0 or min(v.length for v in zs) > 0.9  # trail fades once the hand stops


@case
def ink_and_radial():
    from creator_toolkit.modules import looks52
    if not looks52.ink_available():
        print('  skipped: needs 5.2'); return
    fresh()
    o = cube('Inked')
    m = bpy.data.materials.new('Body'); m.use_nodes = True; o.data.materials.append(m)
    select_only(o)
    assert bpy.ops.ctk.ink_add() == {'FINISHED'}
    assert looks52.has_ink(m)
    out = looks52._output(m.node_tree)
    assert out.inputs['Surface'].links[0].from_node.name == 'CTK ink mix'
    assert bpy.ops.ctk.ink_add() == {'FINISHED'}  # twice = still one ink
    assert sum(1 for n in m.node_tree.nodes if n.get('ctk_ink')) == 7
    assert bpy.ops.ctk.ink_remove() == {'FINISHED'}
    assert not looks52.has_ink(m)
    assert out.inputs['Surface'].links[0].from_node.bl_idname == 'ShaderNodeBsdfPrincipled'
    C.scene.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in C.scene.render.bl_rna.properties['engine'].enum_items] else C.scene.render.engine
    for k, *_ in looks52.PATTERNS:
        assert bpy.ops.ctk.radial_backdrop(pattern=k, spin=0.5 if k == 'SWIRL' else 0.0) == {'FINISHED'}, k
    mats = [m for m in bpy.data.materials if m.get('ctk_radial')]
    assert len(mats) == 5, [m.name for m in mats]
    sw = next(m for m in mats if m['ctk_radial'] == 'SWIRL')
    assert sw.node_tree.animation_data and sw.node_tree.animation_data.drivers



def _eval_mesh(o):
    dg = C.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    vs = [tuple(v.co) for v in me.vertices]
    e.to_mesh_clear()
    return vs


@case
def procedural_text():
    from creator_toolkit.modules import text52, _nodes
    fresh()
    sc = C.scene
    tw = text52.add_text(C, 'TYPEWRITER', 'Hello there')
    m = tw.modifiers[text52.MOD]
    _nodes.set_input(m, 'Start frame', 1); _nodes.set_input(m, 'Duration (frames)', 20)
    sc.frame_set(1); n0 = len(_eval_mesh(tw))
    sc.frame_set(11); n1 = len(_eval_mesh(tw))
    sc.frame_set(30); n2 = len(_eval_mesh(tw))
    assert n0 == 0 < n1 < n2, (n0, n1, n2)
    wv = text52.add_text(C, 'WAVE', 'Wavy')
    sc.frame_set(1); a = _eval_mesh(wv); sc.frame_set(7); b = _eval_mesh(wv)
    assert a and len(a) == len(b) and a != b
    ac = text52.add_text(C, 'ALONG_CURVE', 'Round we go')
    sc.frame_set(1); vs = _eval_mesh(ac)
    assert vs and max(v[1] for v in vs) - min(v[1] for v in vs) > 1.0, 'letters should follow the arc'
    if not text52.new_52():
        print('  (commas and word pop skipped: needs 5.2)')
        return
    ct = text52.add_text(C, 'COUNTER')
    cm = ct.modifiers[text52.MOD]
    _nodes.set_input(cm, 'Duration (frames)', 20)
    ref = text52.add_text(C, 'TYPEWRITER', '10,000 followers')
    rm = ref.modifiers[text52.MOD]; _nodes.set_input(rm, 'Duration (frames)', 1); _nodes.set_input(rm, 'Start frame', -10)
    ref2 = text52.add_text(C, 'TYPEWRITER', '0 followers')
    _nodes.set_input(ref2.modifiers[text52.MOD], 'Duration (frames)', 1); _nodes.set_input(ref2.modifiers[text52.MOD], 'Start frame', -10)
    sc.frame_set(1)
    assert len(_eval_mesh(ct)) == len(_eval_mesh(ref2)), 'counter starts at 0'
    sc.frame_set(40)
    shape = lambda o: sorted((round(v[0], 3), round(v[1], 3)) for v in _eval_mesh(o))
    assert shape(ct) == shape(ref), 'counter should read exactly 10,000 followers'
    _nodes.set_input(cm, 'To', 1234567.0)
    _nodes.set_input(rm, 'Text', '1,234,567 followers')
    ct.update_tag(); ref.update_tag()
    assert shape(ct) == shape(ref), 'counter should read 1,234,567 followers'
    wd = text52.add_text(C, 'WORDS', 'one two three')
    _nodes.set_input(wd.modifiers[text52.MOD], 'Depth', 0.1)
    sc.frame_set(1); v1 = _eval_mesh(wd)
    sc.frame_set(80); v2 = _eval_mesh(wd)
    span = lambda vs: max(v[0] for v in vs) - min(v[0] for v in vs) if vs else 0
    assert span(v1) < span(v2) and len({round(v[2], 3) for v in v2}) >= 2, 'words pop and have depth'
