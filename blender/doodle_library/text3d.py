"""Editable 3D text in Bunny's ink: type it in the Doodle panel (or the modifier), it rebuilds live.

A text object is a mesh with the DSL_Text geometry-nodes modifier first and DSL Ink after it.
Type '|' (or a real line break from a script) to start a new line.
"""
import bpy

from . import style

GROUP = 'DSL_Text'
MOD = 'DSL Text'
STYLES = {  # depth (m), wobble (deg), size (m)
    'flat': (0.008, 0.0, 0.18),
    'chunky': (0.05, 0.0, 0.2),
    'wobbly': (0.03, 7.0, 0.2),
}


def text_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    io = ng.interface
    io.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = io.new_socket('Text', in_out='INPUT', socket_type='NodeSocketString')
    s.default_value = 'Hello'
    for name, val in (('Size', 0.2), ('Depth', 0.03), ('Wobble', 0.0), ('Line Spacing', 1.0),
                      ('Letter Spacing', 1.0)):
        s = io.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value = val
    s = io.new_socket('Seed', in_out='INPUT', socket_type='NodeSocketInt')
    s = io.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    io.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, Lk = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    rep = N.new('FunctionNodeReplaceString')
    Lk.new(gi.outputs['Text'], rep.inputs['String'])
    rep.inputs['Find'].default_value = '|'
    rep.inputs['Replace'].default_value = '\n'
    s2c = N.new('GeometryNodeStringToCurves')
    s2c.align_x = 'CENTER'
    s2c.align_y = 'MIDDLE'
    Lk.new(rep.outputs[0], s2c.inputs['String'])
    Lk.new(gi.outputs['Size'], s2c.inputs['Size'])
    Lk.new(gi.outputs['Line Spacing'], s2c.inputs['Line Spacing'])
    Lk.new(gi.outputs['Letter Spacing'], s2c.inputs['Character Spacing'])
    # wobble: each letter turns a little, like hand lettering
    rnd = N.new('FunctionNodeRandomValue')
    rnd.data_type = 'FLOAT'
    Lk.new(gi.outputs['Seed'], rnd.inputs['Seed'])
    neg = N.new('ShaderNodeMath')
    neg.operation = 'MULTIPLY'
    neg.inputs[1].default_value = -1.0
    Lk.new(gi.outputs['Wobble'], neg.inputs[0])
    Lk.new(neg.outputs[0], rnd.inputs[2])   # Min (float)
    Lk.new(gi.outputs['Wobble'], rnd.inputs[3])  # Max (float)
    rad = N.new('ShaderNodeMath')
    rad.operation = 'RADIANS'
    Lk.new(rnd.outputs[1], rad.inputs[0])
    comb = N.new('ShaderNodeCombineXYZ')
    Lk.new(rad.outputs[0], comb.inputs['Z'])
    rot = N.new('GeometryNodeRotateInstances')
    Lk.new(s2c.outputs['Curve Instances'], rot.inputs['Instances'])
    Lk.new(comb.outputs[0], rot.inputs['Rotation'])
    real = N.new('GeometryNodeRealizeInstances')
    Lk.new(rot.outputs[0], real.inputs[0])
    fill = N.new('GeometryNodeFillCurve')
    fill.mode = 'NGONS'
    Lk.new(real.outputs[0], fill.inputs['Curve'])
    ext = N.new('GeometryNodeExtrudeMesh')
    ext.mode = 'FACES'
    Lk.new(fill.outputs[0], ext.inputs['Mesh'])
    Lk.new(gi.outputs['Depth'], ext.inputs['Offset Scale'])
    # crease lines on the letter outlines (same rule as every other library mesh)
    ang = N.new('GeometryNodeInputMeshEdgeAngle')
    gt = N.new('FunctionNodeCompare')
    gt.data_type = 'FLOAT'
    gt.operation = 'GREATER_THAN'
    Lk.new(ang.outputs['Unsigned Angle'], gt.inputs[0])
    gt.inputs[1].default_value = 0.56
    store = N.new('GeometryNodeStoreNamedAttribute')
    store.data_type = 'BOOLEAN'
    store.domain = 'EDGE'
    store.inputs['Name'].default_value = 'dsl_crease'
    Lk.new(ext.outputs['Mesh'], store.inputs['Geometry'])
    Lk.new(gt.outputs[0], store.inputs['Value'])
    tr = N.new('GeometryNodeTransform')
    tr.inputs['Rotation'].default_value = (1.5708, 0, 0)  # stand up, reading toward -y (camera)
    Lk.new(store.outputs[0], tr.inputs['Geometry'])
    mat = N.new('GeometryNodeSetMaterial')
    Lk.new(tr.outputs[0], mat.inputs['Geometry'])
    Lk.new(gi.outputs['Material'], mat.inputs['Material'])
    sm = N.new('GeometryNodeSetShadeSmooth')
    sm.inputs['Shade Smooth'].default_value = False
    Lk.new(mat.outputs[0], sm.inputs['Geometry'])
    Lk.new(sm.outputs[0], go.inputs['Geometry'])
    for i, n in enumerate(N):
        n.location = (i * 180, 0)
    return ng


def _ids(mod):
    return {s.name: s.identifier for s in mod.node_group.interface.items_tree
            if getattr(s, 'in_out', None) == 'INPUT'}


def add_text(text='Hello', kind='chunky', location=None, fill='mustard', name=None, font=None):
    """New editable 3D text object. Returns the object."""
    depth, wobble, size = STYLES.get(kind, STYLES['chunky'])
    me = bpy.data.meshes.new(name or 'Text')
    ob = bpy.data.objects.new(name or 'Text', me)
    from .assets import target_collection
    target_collection().objects.link(ob)
    if location is not None:
        ob.location = location
    mats = style.materials()
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = text_group()
    ids = _ids(mod)
    mod[ids['Text']] = text
    mod[ids['Size']] = size
    mod[ids['Depth']] = depth
    mod[ids['Wobble']] = wobble
    mod[ids['Seed']] = hash(text) % 1000
    mod[ids['Material']] = mats.get(fill) or mats.get('mustard')
    if font:
        set_font(ob, font)
    me.materials.append(mats.get(fill) or mats.get('mustard'))
    ob['dsl_text'] = True
    ob['dsl_place'] = 'free'
    style.apply_style(ob, bpy.context.scene.camera, seed=0.3)
    return ob


def text_modifier(ob):
    return ob.modifiers.get(MOD) if ob else None


def get_text(ob):
    mod = text_modifier(ob)
    return mod[_ids(mod)['Text']] if mod else None


def set_text(ob, text):
    mod = text_modifier(ob)
    if not mod:
        raise RuntimeError('%s is not a Doodle text object.' % ob.name)
    mod[_ids(mod)['Text']] = text
    ob.update_tag()
    return ob


def set_font(ob, font_path_or_name):
    """Fonts live on the String to Curves node; each text object gets its own group copy when
    its font differs from the default."""
    mod = text_modifier(ob)
    f = bpy.data.fonts.get(font_path_or_name)
    if not f:
        f = bpy.data.fonts.load(font_path_or_name, check_existing=True)
    if mod.node_group.users > 1 or mod.node_group.name == GROUP:
        mod.node_group = mod.node_group.copy()
        mod.node_group.name = GROUP + ' ' + f.name
    for n in mod.node_group.nodes:
        if n.bl_idname == 'GeometryNodeStringToCurves':
            n.font = f
    return f
