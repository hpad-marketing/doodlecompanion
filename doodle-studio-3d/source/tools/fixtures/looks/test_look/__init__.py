"""Test fixture: a minimal look add-on following CONTRACT.md (one working look, one that fails)."""
bl_info = {'name': 'Test look add-on', 'blender': (4, 5, 0), 'category': 'Material'}


def register():
    pass


def unregister():
    pass


def material(look, rgb, params):
    import bpy
    if look == 'broken':
        raise RuntimeError('this look is broken on purpose')
    m = bpy.data.materials.new('test glow')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = tuple(rgb[:3]) + (1.0,)
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    p.inputs['Emission Strength'].default_value = float(params.get('rim', 1.0))
    nt.links.new(lw.outputs['Facing'], p.inputs['Emission Color'])
    return m
