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
