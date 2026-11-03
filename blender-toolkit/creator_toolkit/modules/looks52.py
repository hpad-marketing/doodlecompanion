"""Crisp ink and radial backdrops (Blender 5.2 shader nodes).

Raycast ink: adds dark contact lines where a surface meets another one (feet on the floor,
arm against body) plus a silhouette line, inside the material itself, so it works in EEVEE and
Cycles with no Freestyle and no extra objects. Removable in one click.

Radial backdrops: sunbursts, petals, mandalas, speed rings and swirls from the Radial Tiling
node, in your palette colours, optionally spinning."""
import bpy
from . import _util

LABEL, ICON, GROUP = 'Ink + radial backdrops', 'SHADING_RENDERED', 'Look'

INK_TAG = 'ctk_ink'


def ink_available():
    return hasattr(bpy.types, 'ShaderNodeRaycast')


def radial_available():
    return hasattr(bpy.types, 'ShaderNodeRadialTiling')


def _output(nt):
    outs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
    act = [n for n in outs if n.is_active_output]
    return (act or outs or [None])[0]


def _tag(node):
    node[INK_TAG] = 1
    node.label = node.label or 'CTK ink'
    return node


# ------------------------------------------------------------------ raycast ink

def add_ink(mat, colour='#1F1F1D', width=0.03, silhouette=0.35):
    """Mix an ink emission over the material wherever a contact ray hits or the surface turns away."""
    if not ink_available():
        raise RuntimeError('Needs Blender 5.2 (Raycast node)')
    mat.use_nodes = True
    nt = mat.node_tree
    remove_ink(mat)
    out = _output(nt)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
    link = next((l for l in nt.links if l.to_socket == out.inputs['Surface']), None)
    src = link.from_socket if link else None
    x, y = out.location
    out.location = (x + 600, y)
    geo = _tag(nt.nodes.new('ShaderNodeNewGeometry'))
    geo.location = (x - 200, y - 300)
    ray = _tag(nt.nodes.new('ShaderNodeRaycast'))
    ray.location = (x, y - 300)
    nt.links.new(geo.outputs['Position'], ray.inputs['Position'])
    nt.links.new(geo.outputs['Normal'], ray.inputs['Direction'])
    ray.inputs['Length'].default_value = width
    ray.name = 'CTK ink contact'
    lw = _tag(nt.nodes.new('ShaderNodeLayerWeight'))
    lw.location = (x, y - 520)
    lw.inputs['Blend'].default_value = 0.5
    step = _tag(nt.nodes.new('ShaderNodeMath'))
    step.operation = 'GREATER_THAN'
    step.inputs[1].default_value = 1.0 - 0.6 * silhouette if silhouette > 0 else 2.0
    step.name = 'CTK ink silhouette'
    step.location = (x + 200, y - 520)
    nt.links.new(lw.outputs['Facing'], step.inputs[0])
    both = _tag(nt.nodes.new('ShaderNodeMath'))
    both.operation = 'MAXIMUM'
    both.location = (x + 200, y - 300)
    nt.links.new(ray.outputs['Is Hit'], both.inputs[0])
    nt.links.new(step.outputs[0], both.inputs[1])
    ink = _tag(nt.nodes.new('ShaderNodeEmission'))
    ink.location = (x + 200, y - 120)
    ink.inputs['Color'].default_value = (*_util.hex_to_linear(colour), 1)
    ink.name = 'CTK ink colour'
    mix = _tag(nt.nodes.new('ShaderNodeMixShader'))
    mix.location = (x + 400, y)
    mix.name = 'CTK ink mix'
    nt.links.new(both.outputs[0], mix.inputs['Fac'])
    if src is not None:
        nt.links.new(src, mix.inputs[1])
    nt.links.new(ink.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mat['ctk_ink_src'] = src.node.name if src is not None else ''
    return mix


def remove_ink(mat):
    nt = mat.node_tree if mat and mat.use_nodes else None
    if nt is None:
        return False
    tagged = [n for n in nt.nodes if n.get(INK_TAG)]
    if not tagged:
        return False
    out = _output(nt)
    srcname = mat.get('ctk_ink_src', '')
    mix = nt.nodes.get('CTK ink mix')
    src = None
    if mix is not None:
        l = next((l for l in nt.links if l.to_socket == mix.inputs[1]), None)
        src = l.from_socket if l else None
    for n in tagged:
        nt.nodes.remove(n)
    if out is not None:
        out.location.x -= 600
        if src is None and srcname and srcname in nt.nodes:
            src = nt.nodes[srcname].outputs[0]
        if src is not None:
            nt.links.new(src, out.inputs['Surface'])
    if 'ctk_ink_src' in mat:
        del mat['ctk_ink_src']
    return True


def has_ink(mat):
    return bool(mat and mat.use_nodes and mat.node_tree.nodes.get('CTK ink mix'))


def _mats(context):
    seen = []
    for o in context.selected_objects:
        for s in getattr(o, 'material_slots', []):
            if s.material and s.material not in seen:
                seen.append(s.material)
    return seen


class CTK_OT_ink_add(bpy.types.Operator):
    """Add crisp contact and silhouette ink inside the selected objects' materials (EEVEE and Cycles)"""
    bl_idname = 'ctk.ink_add'
    bl_label = 'Add ink'
    bl_options = {'REGISTER', 'UNDO'}
    width: bpy.props.FloatProperty(name='Contact width', default=0.03, min=0.001, max=1.0, unit='LENGTH')
    silhouette: bpy.props.FloatProperty(name='Silhouette thickness', default=0.35, min=0.0, max=1.0, subtype='FACTOR')

    @classmethod
    def poll(cls, context):
        return ink_available()

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}]
        for o in objs:
            if not o.material_slots or not any(s.material for s in o.material_slots):
                m = bpy.data.materials.new(o.name + ' ink')
                o.data.materials.append(m)
        mats = {}
        for o in objs:
            dims = sorted(o.dimensions)
            flat = dims[2] > 0 and dims[0] < dims[2] * 0.01  # floors and walls: contact lines only
            for s in o.material_slots:
                if s.material:
                    mats[s.material] = min(mats.get(s.material, 1.0), 0.0 if flat else 1.0)
        for m, k in mats.items():
            add_ink(m, width=self.width, silhouette=self.silhouette * k)
        self.report({'INFO'}, f'Ink on {len(mats)} materials')
        return {'FINISHED'}


class CTK_OT_ink_remove(bpy.types.Operator):
    """Take the ink back out of the selected objects' materials"""
    bl_idname = 'ctk.ink_remove'
    bl_label = 'Remove ink'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = sum(1 for m in _mats(context) if remove_ink(m))
        self.report({'INFO'}, f'Ink removed from {n} materials')
        return {'FINISHED'}


# ------------------------------------------------------------------ radial backdrops

PATTERNS = [('SUNBURST', 'Sunburst', 'Alternating rays from the centre', 12),
            ('PETALS', 'Petals', 'A ring of round petals', 8),
            ('MANDALA', 'Mandala', 'Two rings of petals over rays', 12),
            ('RINGS', 'Speed rings', 'Bands that ripple out from the centre', 16),
            ('SWIRL', 'Swirl', 'Rays that twist as they go out', 10)]


def _colours(context, a=None, b=None):
    from . import palette
    kit = palette.kits().get(context.scene.get('ctk_palette', ''), []) or palette.BUILTIN['Doodle ink + mustard']
    c1 = a or kit[0]
    c2 = b or (kit[2] if len(kit) > 2 else '#F2E6CF')
    return c1, c2


def radial_material(name, pattern='SUNBURST', c1='#E0A64B', c2='#F2E6CF', sides=None, spin=0.0):
    if not radial_available():
        raise RuntimeError('Needs Blender 5.2 (Radial Tiling node)')
    sides = sides or next(p[3] for p in PATTERNS if p[0] == pattern)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def math(op, a, b=None, x=0, y=0):
        n = N('ShaderNodeMath')
        n.operation = op
        n.location = (x, y)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    tc = N('ShaderNodeTexCoord')
    tc.location = (-1200, 0)
    rot = N('ShaderNodeVectorRotate')
    rot.rotation_type = 'Z_AXIS'
    rot.location = (-1000, 0)
    rot.name = 'CTK spin'
    L(tc.outputs['Object'], rot.inputs['Vector'])
    if spin:
        d = rot.inputs['Angle'].driver_add('default_value').driver
        d.type = 'SCRIPTED'
        d.expression = 'frame*%.5f' % (spin / 24.0)
    vec = rot.outputs['Vector']
    radius = None
    if pattern in ('SWIRL', 'RINGS'):
        ln = N('ShaderNodeVectorMath')
        ln.operation = 'LENGTH'
        ln.location = (-1000, -250)
        L(rot.outputs['Vector'], ln.inputs[0])
        radius = ln.outputs['Value']
    if pattern == 'SWIRL':
        tw = N('ShaderNodeVectorRotate')
        tw.rotation_type = 'Z_AXIS'
        tw.location = (-800, 0)
        L(rot.outputs['Vector'], tw.inputs['Vector'])
        L(math('MULTIPLY', radius, 0.6, -900, -250), tw.inputs['Angle'])
        vec = tw.outputs['Vector']
    rt = N('ShaderNodeRadialTiling')
    rt.location = (-600, 0)
    L(vec, rt.inputs['Vector'])
    rt.inputs['Sides'].default_value = sides
    rt.inputs['Roundness'].default_value = 0.0
    alt = math('FLOORED_MODULO', rt.outputs['Segment ID'], 2.0, -400, 100)

    def petals(tiling, phase, radius, y0):
        # round blobs in every segment, ring after ring going outwards
        sep = N('ShaderNodeSeparateXYZ')
        sep.location = (-450, y0)
        L(tiling.outputs['Segment Coordinates'], sep.inputs[0])
        ring = 0.25 * sides / 8.0
        yy = math('ADD', math('MULTIPLY', sep.outputs['Y'], ring, -400, y0 - 50), phase, -380, y0 - 50)
        py = math('SUBTRACT', math('FRACT', yy, None, -350, y0 - 50), 0.5, -300, y0 - 50)
        px = math('MULTIPLY', sep.outputs['X'], ring, -400, y0 + 50)
        cxyz = N('ShaderNodeCombineXYZ')
        cxyz.location = (-250, y0)
        L(px, cxyz.inputs['X'])
        L(py, cxyz.inputs['Y'])
        ln_ = N('ShaderNodeVectorMath')
        ln_.operation = 'LENGTH'
        ln_.location = (-200, y0)
        L(cxyz.outputs['Vector'], ln_.inputs[0])
        return math('LESS_THAN', ln_.outputs['Value'], radius, -150, y0)

    if pattern in ('SUNBURST', 'SWIRL'):
        fac = alt
    elif pattern == 'RINGS':
        fac = math('GREATER_THAN', math('FRACT', math('MULTIPLY', radius, sides / 32.0, -600, -250), None, -400, -250), 0.5, -200, -250)
    elif pattern == 'PETALS':
        fac = petals(rt, 0.0, 0.32, -100)
    else:  # MANDALA: big petals, small petals between them, faint rays behind
        half = N('ShaderNodeVectorRotate')
        half.rotation_type = 'Z_AXIS'
        half.location = (-800, -400)
        L(vec, half.inputs['Vector'])
        half.inputs['Angle'].default_value = 3.14159265 / sides
        rt2 = N('ShaderNodeRadialTiling')
        rt2.location = (-600, -400)
        L(half.outputs['Vector'], rt2.inputs['Vector'])
        rt2.inputs['Sides'].default_value = sides
        big = petals(rt, 0.0, 0.32, -100)
        small = petals(rt2, 0.5, 0.16, -400)
        fac = math('MAXIMUM', math('MAXIMUM', big, small, 0, -200), math('MULTIPLY', alt, 0.35, -100, 100), 150, 0)
    mix = N('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.location = (300, 0)
    L(fac, mix.inputs['Factor'])
    mix.inputs['A'].default_value = (*_util.hex_to_linear(c2), 1)
    mix.inputs['B'].default_value = (*_util.hex_to_linear(c1), 1)
    em = N('ShaderNodeEmission')
    em.location = (500, 0)
    L(mix.outputs['Result'], em.inputs['Color'])
    out = N('ShaderNodeOutputMaterial')
    out.location = (700, 0)
    L(em.outputs[0], out.inputs['Surface'])
    m['ctk_radial'] = pattern
    return m


def add_backdrop(context, pattern='SUNBURST', size=20.0, spin=0.0, sides=0):
    c1, c2 = _colours(context)
    mat = radial_material('CTK ' + pattern.title(), pattern, c1, c2, sides or None, spin)
    me = bpy.data.meshes.new('Radial backdrop')
    h = size / 2
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(mat)
    o = bpy.data.objects.new('Radial backdrop', me)
    context.scene.collection.objects.link(o)
    cam = context.scene.camera
    if cam:
        # stand it up behind everything, facing the camera
        o.rotation_euler = cam.matrix_world.to_euler()
        fwd = cam.matrix_world.to_quaternion() @ __import__('mathutils').Vector((0, 0, -1))
        o.location = cam.matrix_world.translation + fwd * 30.0
    else:
        o.rotation_euler = (1.5708, 0, 0)
        o.location = (0, 10, h)
    o.visible_shadow = False
    return o


class CTK_OT_radial(bpy.types.Operator):
    """Add a radial pattern backdrop behind the scene, facing the camera"""
    bl_idname = 'ctk.radial_backdrop'
    bl_label = 'Radial backdrop'
    bl_options = {'REGISTER', 'UNDO'}
    pattern: bpy.props.EnumProperty(name='Pattern', items=[p[:3] for p in PATTERNS])
    sides: bpy.props.IntProperty(name='Count', default=0, min=0, max=64, description='0 = the pattern default')
    spin: bpy.props.FloatProperty(name='Spin (turns/sec)', default=0.0, min=-4, max=4)
    size: bpy.props.FloatProperty(name='Size', default=40.0, min=1, max=1000, unit='LENGTH')

    @classmethod
    def poll(cls, context):
        return radial_available()

    def execute(self, context):
        add_backdrop(context, self.pattern, self.size, self.spin * 6.28318, self.sides)
        return {'FINISHED'}


CLASSES = (CTK_OT_ink_add, CTK_OT_ink_remove, CTK_OT_radial)


def draw(layout, context):
    if not ink_available():
        layout.label(text='Needs Blender 5.2 (Raycast and Radial Tiling nodes)', icon='INFO')
        return
    row = layout.row(align=True)
    row.operator('ctk.ink_add', icon='GREASEPENCIL')
    row.operator('ctk.ink_remove', icon='X')
    o = context.active_object
    m = o.active_material if o else None
    if has_ink(m):
        nt = m.node_tree
        row = layout.row(align=True)
        row.prop(nt.nodes['CTK ink contact'].inputs['Length'], 'default_value', text='Contact')
        row.prop(nt.nodes['CTK ink silhouette'].inputs[1], 'default_value', text='Edge')
        row.prop(nt.nodes['CTK ink colour'].inputs['Color'], 'default_value', text='')
        layout.label(text='Lower Edge = thicker outline', icon='INFO')
    layout.label(text='Radial backdrop', icon='MESH_CIRCLE')
    grid = layout.grid_flow(columns=3, align=True)
    for k, label, *_ in PATTERNS:
        grid.operator('ctk.radial_backdrop', text=label).pattern = k
