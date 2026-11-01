"""Dress 3D Bunny in a library outfit (what the clothing studio panel runs).

  blender -b Bunny3D_v2.blend --python apply_outfit.py -- OUTFIT_DIR [--save FILE]
  or from Python:  apply_outfit.dress('path/to/outfits/raincoat')   /   apply_outfit.undress()

OUTFIT_DIR holds outfit.blend + outfit.json. Dressing appends the OUTFIT_<id>
collection, binds every garment to BUNNY_rig, re-creates the ink drivers so
outline and ochre strokes stay one ink width, wires the sleeve crease keys to
the elbows, hides the hoodie parts it replaces and turns on the colliders.
Undressing removes the outfit and brings the hoodie back.
"""
import bpy, json, os, sys


# Blender 5.2 keeps Geometry Nodes modifier inputs off ID properties: m['Socket_2'] and m.keys()
# raise there. These read and write them on 4.x-5.1 and 5.2 alike.
def gn_values(m):
    """{socket identifier: value} of a nodes modifier's inputs."""
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    if ins is None:
        return {k: m[k] for k in m.keys() if k.startswith('Socket_') and not k.endswith(('_use_attribute', '_attribute_name'))}
    out = {}
    for it in m.node_group.interface.items_tree:
        s = getattr(ins, it.identifier, None) if getattr(it, 'in_out', None) == 'INPUT' else None
        if s is not None and hasattr(s, 'value'):
            out[it.identifier] = s.value
    return out


def gn_set(m, k, v):
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    if ins is None:
        m[k] = v
    else:
        getattr(ins, k).value = v


def gn_path(m, k):
    """Data path of one input, from the object (for driver_add)."""
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    return f'modifiers["{m.name}"]["{k}"]' if ins is None else f'modifiers["{m.name}"].properties.inputs.{k}.value'

INK_SRC = 'BUNNY_hand.L'


def _vars(d, specs):
    for name, idt, idv, path in specs:
        v = d.variables.new()
        v.name = name
        v.targets[0].id_type = idt
        v.targets[0].id = idv
        v.targets[0].data_path = path


def _copy_ink(ob, src_ob):
    sm = next(m for m in src_ob.modifiers if m.type == 'NODES')
    for m in ob.modifiers:
        if m.type != 'NODES':
            continue
        for k, v in gn_values(sm).items():
            if k != 'Socket_11':
                gn_set(m, k, v)
        key = f'modifiers["{sm.name}"]'
        for fc in (src_ob.animation_data.drivers if src_ob.animation_data else []):
            if not fc.data_path.startswith(key):
                continue
            path = fc.data_path.replace(key, f'modifiers["{m.name}"]')
            try:
                nf = ob.driver_add(path, fc.array_index)
            except TypeError:
                nf = ob.driver_add(path)
            nf.driver.type, nf.driver.expression = fc.driver.type, fc.driver.expression
            for ov in fc.driver.variables:
                v = nf.driver.variables.new()
                v.name, v.type = ov.name, ov.type
                for i, t in enumerate(ov.targets):
                    v.targets[i].id_type = t.id_type
                    v.targets[i].id = t.id
                    v.targets[i].data_path = t.data_path


def _stroke_drivers(mat, cam, settings):
    if not mat or not mat.node_tree:
        return
    for nd in mat.node_tree.nodes:
        if nd.type == 'VALUE' and nd.label == 'ink_half_width':
            d = nd.outputs[0].driver_add('default_value').driver
            d.type = 'SCRIPTED'
            _vars(d, (('ink', 'OBJECT', settings, '["ink_px"]'), ('ortho', 'CAMERA', cam.data, 'ortho_scale')))
            d.expression = 'ink / 1920 * ortho * 0.5'


def _bunch_driver(ob, rig):
    side, rest = ob['ds_bunch_side'], ob['ds_bunch_rest']
    k = ob.data.shape_keys.key_blocks['Bunch']
    d = k.driver_add('value').driver
    d.type = 'SCRIPTED'
    v = d.variables.new()
    v.name, v.type = 'a', 'ROTATION_DIFF'
    v.targets[0].id, v.targets[0].bone_target = rig, f'DEF-upper_arm.{side}'
    v.targets[1].id, v.targets[1].bone_target = rig, f'DEF-forearm.{side}'
    d.expression = f'min(1.0, max(0.0, (a - {rest:.4f}) / 1.2))'


def _refit_accessories():
    try:
        import apply_accessory
    except ImportError:
        return
    apply_accessory.refit()


def undress(refit=True):
    _undress()
    if refit:
        _refit_accessories()


def _undress():
    cc = bpy.data.collections.get('OUTFIT_colliders')
    if cc:
        bpy.data.collections.remove(cc)
    for c in [c for c in bpy.data.collections if c.name.startswith('OUTFIT_') and c.name != 'OUTFIT_colliders']:
        for ob in list(c.objects):
            bpy.data.objects.remove(ob)
        bpy.data.collections.remove(c)
    for ob in bpy.data.objects:
        if ob.get('ds_hidden_by_outfit'):
            ob.hide_render = ob.hide_viewport = False
            for m in ob.modifiers:
                if m.type == 'CLOTH':
                    m.show_viewport = m.show_render = True
            del ob['ds_hidden_by_outfit']


def dress(outfit_dir):
    man = json.load(open(os.path.join(outfit_dir, 'outfit.json')))
    _undress()
    with bpy.data.libraries.load(os.path.join(outfit_dir, 'outfit.blend'), link=False) as (src, dst):
        dst.collections = [man['collection']]
    coll = dst.collections[0]
    parent = bpy.data.collections.get('Bunny') or bpy.context.scene.collection
    parent.children.link(coll)
    rig = bpy.data.objects['BUNNY_rig']
    cam = bpy.context.scene.camera
    settings = bpy.data.objects['BUNNY_settings']
    ink_src = bpy.data.objects[INK_SRC]
    for ob in coll.objects:
        ob.parent = rig
        for m in ob.modifiers:
            if m.type == 'ARMATURE':
                m.object = rig
        _copy_ink(ob, ink_src)
        for ms in ob.material_slots:
            _stroke_drivers(ms.material, cam, settings)
        if 'ds_bunch_side' in ob.keys():
            _bunch_driver(ob, rig)
    cc = bpy.data.collections.get('OUTFIT_colliders') or bpy.data.collections.new('OUTFIT_colliders')
    if cc.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(cc)
    cc.hide_render = True
    for n in man.get('cloth_colliders', []) + man.get('cloth_collide_with_garment', []):
        ob = bpy.data.objects.get(n)
        if ob and ob.name not in cc.objects:
            cc.objects.link(ob)
    for ob in coll.objects:
        for m in ob.modifiers:
            if m.type == 'CLOTH':
                m.collision_settings.collection = cc
    for n in man['hides']:
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        ob['ds_hidden_by_outfit'] = True
        ob.hide_render = True
        # The rig's arm-vs-head solver and rule check read the cuffs and forearm sleeves (and colliders
        # push cloth), and Blender stops evaluating viewport-hidden objects, so those stay evaluated:
        # hidden from renders only. Everything else is hidden in the viewport too.
        keep = any(m.type == 'COLLISION' for m in ob.modifiers) or n.split('_', 1)[1].startswith(('cuff', 'sleeve_fore', 'sleeve_up'))
        ob.hide_viewport = not keep
        for m in ob.modifiers:
            if m.type == 'CLOTH':
                m.show_viewport = m.show_render = False
    for n in man['colliders']:
        ob = bpy.data.objects.get(n)
        if ob and not any(m.type == 'COLLISION' for m in ob.modifiers):
            md = ob.modifiers.new('Collision', 'COLLISION')
            names = [m.name for m in ob.modifiers]
            if 'Armature' in names:
                with bpy.context.temp_override(object=ob, active_object=ob):
                    bpy.ops.object.modifier_move_to_index(modifier=md.name, index=names.index('Armature') + 1)
            ob.collision.thickness_outer = 0.004
            ob.collision.cloth_friction = 5
    for n in man.get('parts', {}).get('shells', []):
        if n in bpy.data.objects:
            bpy.data.objects[n]['ds_top'] = True  # neck accessories sit on this
    _refit_accessories()
    return coll


if __name__ == '__main__' and '--' in sys.argv:
    a = sys.argv[sys.argv.index('--') + 1:]
    dress(a[0])
    if '--save' in a:
        bpy.ops.wm.save_as_mainfile(filepath=a[a.index('--save') + 1], copy=True)
        print('DRESSED', a[a.index('--save') + 1])
