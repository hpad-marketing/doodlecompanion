"""Master Material: one slider shader for plastic, metal, clay, fabric, glass, paper, rubber and toon."""
import bpy
from . import _util
from .. import uxfit

LABEL, ICON, GROUP = 'Master Material', 'MATERIAL', 'Look'
GROUP_NAME = 'CTK Master Surface'

# slider name, default, min, max
SLIDERS = [
    ('Roughness', 0.5, 0, 1), ('Metallic', 0.0, 0, 1), ('Glass', 0.0, 0, 1),
    ('Fabric', 0.0, 0, 1), ('Coat', 0.0, 0, 1), ('Soft Light', 0.0, 0, 1),
    ('Toon', 0.0, 0, 1), ('Bumps', 0.0, 0, 1), ('Bump Size', 20.0, 0.5, 200),
]
BUILTIN = {
    'Plastic': {'Roughness': 0.35, 'Coat': 0.3},
    'Glossy plastic': {'Roughness': 0.12, 'Coat': 0.8},
    'Rubber': {'Roughness': 0.85, 'Bumps': 0.05, 'Bump Size': 120},
    'Metal': {'Roughness': 0.25, 'Metallic': 1.0},
    'Brushed metal': {'Roughness': 0.45, 'Metallic': 1.0, 'Bumps': 0.08, 'Bump Size': 150},
    'Clay': {'Roughness': 0.8, 'Soft Light': 0.15, 'Bumps': 0.25, 'Bump Size': 8},
    'Fabric': {'Roughness': 0.95, 'Fabric': 1.0, 'Bumps': 0.15, 'Bump Size': 90},
    'Glass': {'Roughness': 0.02, 'Glass': 1.0},
    'Frosted glass': {'Roughness': 0.35, 'Glass': 1.0},
    'Paper': {'Roughness': 0.9, 'Bumps': 0.12, 'Bump Size': 40},
    'Ceramic': {'Roughness': 0.1, 'Coat': 1.0},
    'Skin / wax': {'Roughness': 0.5, 'Soft Light': 0.6},
    'Toon': {'Roughness': 1.0, 'Toon': 1.0},
}


def _sock(tree, name, kind, d=None, lo=None, hi=None, io='INPUT'):
    s = tree.interface.new_socket(name=name, in_out=io, socket_type=kind)
    if d is not None and hasattr(s, 'default_value'):
        s.default_value = d
    if lo is not None:
        s.min_value = lo
    if hi is not None:
        s.max_value = hi
    return s


def get_group():
    g = bpy.data.node_groups.get(GROUP_NAME)
    if g:
        return g
    g = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
    _sock(g, 'Color', 'NodeSocketColor', (0.8, 0.5, 0.2, 1))
    for n, d, lo, hi in SLIDERS:
        _sock(g, n, 'NodeSocketFloat', d, lo, hi)
    _sock(g, 'Shader', 'NodeSocketShader', io='OUTPUT')
    N, L = g.nodes, g.links
    gi = N.new('NodeGroupInput'); gi.location = (-900, 0)
    go = N.new('NodeGroupOutput'); go.location = (700, 0)
    p = N.new('ShaderNodeBsdfPrincipled'); p.location = (-200, 200)

    def inp(node, *names):
        for n in names:
            if n in node.inputs:
                return node.inputs[n]
        raise KeyError(names)
    L.new(gi.outputs['Color'], inp(p, 'Base Color'))
    L.new(gi.outputs['Roughness'], inp(p, 'Roughness'))
    L.new(gi.outputs['Metallic'], inp(p, 'Metallic'))
    L.new(gi.outputs['Glass'], inp(p, 'Transmission Weight', 'Transmission'))
    L.new(gi.outputs['Fabric'], inp(p, 'Sheen Weight', 'Sheen'))
    L.new(gi.outputs['Coat'], inp(p, 'Coat Weight', 'Clearcoat'))
    L.new(gi.outputs['Soft Light'], inp(p, 'Subsurface Weight', 'Subsurface'))
    # bumps
    tc = N.new('ShaderNodeTexCoord'); tc.location = (-900, -400)
    nz = N.new('ShaderNodeTexNoise'); nz.location = (-700, -400)
    nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    L.new(gi.outputs['Bump Size'], nz.inputs['Scale'])
    bump = N.new('ShaderNodeBump'); bump.location = (-450, -300)
    L.new(gi.outputs['Bumps'], bump.inputs['Strength'])
    L.new(nz.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], inp(p, 'Normal'))
    # toon: diffuse -> shader to rgb -> 3-step ramp x colour (EEVEE); Cycles falls back to soft diffuse
    dif = N.new('ShaderNodeBsdfDiffuse'); dif.location = (-200, -250)
    L.new(gi.outputs['Color'], dif.inputs['Color'])
    s2r = N.new('ShaderNodeShaderToRGB'); s2r.location = (0, -250)
    L.new(dif.outputs['BSDF'], s2r.inputs['Shader'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.location = (180, -250)
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position = 0.0; cr.elements[0].color = (0.35, 0.35, 0.35, 1)
    cr.elements[1].position = 0.5; cr.elements[1].color = (1, 1, 1, 1)
    e = cr.elements.new(0.15); e.color = (0.6, 0.6, 0.6, 1)
    L.new(s2r.outputs['Color'], ramp.inputs['Fac'])
    mul = N.new('ShaderNodeMixRGB'); mul.location = (420, -250)
    mul.blend_type = 'MULTIPLY'; mul.inputs['Fac'].default_value = 1
    L.new(ramp.outputs['Color'], mul.inputs[1]); L.new(gi.outputs['Color'], mul.inputs[2])
    em = N.new('ShaderNodeEmission'); em.location = (560, -250)
    L.new(mul.outputs['Color'], em.inputs['Color'])
    mix = N.new('ShaderNodeMixShader'); mix.location = (560, 50)
    L.new(gi.outputs['Toon'], mix.inputs['Fac'])
    L.new(p.outputs['BSDF'], mix.inputs[1])
    L.new(em.outputs['Emission'], mix.inputs[2])
    L.new(mix.outputs['Shader'], go.inputs['Shader'])
    return g


def make_material(name, color, values):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (300, 0)
    gn = nt.nodes.new('ShaderNodeGroup'); gn.node_tree = get_group(); gn.name = 'CTK'; gn.location = (0, 0)
    gn.width = 220
    nt.links.new(gn.outputs['Shader'], out.inputs['Surface'])
    set_values(m, color, values)
    m['ctk_master'] = True
    return m


def master_node(m):
    if m and m.use_nodes:
        n = m.node_tree.nodes.get('CTK')
        if n and getattr(n, 'node_tree', None) and n.node_tree.name.startswith(GROUP_NAME):
            return n
    return None


def set_values(m, color, values):
    n = master_node(m)
    if color is not None:
        n.inputs['Color'].default_value = (*color[:3], 1)
        m.diffuse_color = (*color[:3], 1)
    for k, d, *_ in SLIDERS:
        n.inputs[k].default_value = values.get(k, d)
    if values.get('Glass', 0) > 0:
        for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED')):
            try:
                setattr(m, attr, val)
            except Exception:
                pass


def presets():
    p = dict(BUILTIN)
    p.update(_util.load_json('material_presets.json', {}))
    return p


def _preset_items(self, context):
    return [(k, k, '') for k in sorted(presets())]


class CTK_OT_material_apply(bpy.types.Operator):
    """Give the selected objects a Master Material preset (keeps each object's colour)"""
    bl_idname = 'ctk.material_apply'
    bl_label = 'Apply material preset'
    bl_options = {'REGISTER', 'UNDO'}
    preset: bpy.props.EnumProperty(name='Preset', items=_preset_items)
    keep_color: bpy.props.BoolProperty(name='Keep each object\'s colour', default=True)
    color: bpy.props.FloatVectorProperty(name='Colour', subtype='COLOR', size=3, default=(0.88, 0.65, 0.29), min=0, max=1)

    def execute(self, context):
        vals = presets()[self.preset]
        obs = _util.selected_meshes(context) or ([context.active_object] if context.active_object else [])
        for o in obs:
            col = self.color
            old = o.active_material
            if self.keep_color and old:
                mn = master_node(old)
                from .style import base_color
                col = mn.inputs['Color'].default_value[:3] if mn else base_color(old)
            if old and master_node(old) and old.users == 1:
                set_values(old, col, vals)
                continue
            m = make_material(f'{self.preset} {o.name}', col, vals)
            if o.material_slots:
                o.material_slots[o.active_material_index].material = m
            else:
                o.data.materials.append(m)
        return {'FINISHED'}


class CTK_OT_material_save_preset(bpy.types.Operator):
    """Save the active Master Material's sliders as your own preset"""
    bl_idname = 'ctk.material_save_preset'
    bl_label = 'Save as preset'
    name: bpy.props.StringProperty(name='Preset name', default='My look')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        m = context.active_object.active_material if context.active_object else None
        n = master_node(m)
        if not n:
            self.report({'WARNING'}, 'Active material is not a Master Material. Use Convert first')
            return {'CANCELLED'}
        mine = _util.load_json('material_presets.json', {})
        mine[self.name] = {k: round(n.inputs[k].default_value, 4) for k, *_ in SLIDERS}
        _util.save_json('material_presets.json', mine)
        self.report({'INFO'}, f'Saved preset {self.name}')
        return {'FINISHED'}


class CTK_OT_material_convert(bpy.types.Operator):
    """Turn existing Principled materials (e.g. your material libraries) into Master Material presets"""
    bl_idname = 'ctk.material_convert'
    bl_label = 'Convert materials to presets'
    scope: bpy.props.EnumProperty(items=[('SELECTED', 'Selected objects', ''), ('FILE', 'Every material in this file', '')])
    replace: bpy.props.BoolProperty(name='Also swap them to Master Materials', default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.scope == 'SELECTED':
            mats = {s.material for o in context.selected_objects for s in getattr(o, 'material_slots', []) if s.material}
        else:
            mats = set(bpy.data.materials)
        mine = _util.load_json('material_presets.json', {})
        n = 0
        for m in mats:
            if not m.use_nodes or master_node(m):
                continue
            p = next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None)
            if not p:
                continue

            def g(*names, d=0.0):
                for nm in names:
                    if nm in p.inputs:
                        return float(p.inputs[nm].default_value)
                return d
            vals = {'Roughness': g('Roughness', d=0.5), 'Metallic': g('Metallic'),
                    'Glass': g('Transmission Weight', 'Transmission'), 'Fabric': g('Sheen Weight', 'Sheen'),
                    'Coat': g('Coat Weight', 'Clearcoat'), 'Soft Light': g('Subsurface Weight', 'Subsurface')}
            mine[m.name] = vals
            n += 1
            if self.replace:
                col = p.inputs['Base Color'].default_value[:3]
                users = [s for o in bpy.data.objects for s in getattr(o, 'material_slots', []) if s.material == m]
                nm = make_material(m.name + ' (master)', col, vals)
                for s in users:
                    s.material = nm
        _util.save_json('material_presets.json', mine)
        self.report({'INFO'}, f'{n} materials saved as presets')
        return {'FINISHED'}


CLASSES = (CTK_OT_material_apply, CTK_OT_material_save_preset, CTK_OT_material_convert)


def draw(layout, context):
    ob = context.active_object
    m = ob.active_material if ob else None
    n = master_node(m)
    layout.operator_menu_enum('ctk.material_apply', 'preset', text='Apply preset', icon='MATERIAL')
    if n:
        col = layout.column(align=True)
        col.prop(n.inputs['Color'], 'default_value', text='Colour')
        for k, *_ in SLIDERS:
            col.prop(n.inputs[k], 'default_value', text=k, slider=k != 'Bump Size')
        layout.operator('ctk.material_save_preset', icon='ADD')
    else:
        uxfit.wrap(layout, context, 'Select an object to see its sliders', icon='INFO')
    layout.operator('ctk.material_convert', icon='FILE_REFRESH')
