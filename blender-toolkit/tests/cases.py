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
