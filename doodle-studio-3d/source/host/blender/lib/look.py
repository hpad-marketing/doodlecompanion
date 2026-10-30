"""Doodle look: flat brand fills and a screen-constant ink outline with line boil.

The outline is an inverted hull built in geometry nodes. Its thickness is
computed from the active camera every frame, so the ink stays the same width in
pixels whatever the lens, distance or Bunny scale (one weight per depth layer,
set on the BUNNY_settings object).
"""
import bpy

INK_HEX = '#1F1F1D'
MUSTARD_HEX = '#E0A64B'


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(h, a=1.0):
    h = h.lstrip('#')
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def flat_material(name, hexcol, backface_cull=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = hex_linear(hexcol)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.use_backface_culling = backface_cull
    if hasattr(m, 'use_backface_culling_shadow'):
        m.use_backface_culling_shadow = True
    m.diffuse_color = hex_linear(hexcol)
    return m


def materials():
    return dict(
        mustard=flat_material('DS_mustard', MUSTARD_HEX),
        ink=flat_material('DS_ink', INK_HEX),
        shell=flat_material('DS_ink_outline', INK_HEX, backface_cull=True),
    )


def _sock(ng, name, kind, io='INPUT', default=None, mn=None, mx=None):
    s = ng.interface.new_socket(name, in_out=io, socket_type=kind)
    if default is not None:
        s.default_value = default
    if mn is not None:
        s.min_value = mn
    if mx is not None:
        s.max_value = mx
    return s


class G:
    """Tiny helper to wire node trees readably."""

    def __init__(self, tree):
        self.t = tree
        self.n = tree.nodes
        self.l = tree.links
        self.x = 0

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            if hasattr(nd, k):
                setattr(nd, k, v)
            else:  # Blender 5: some enum properties became menu input sockets
                name = k.replace('_', ' ').title()
                sock = nd.inputs.get(name)
                if sock is None:
                    raise AttributeError(f'{kind} has no {k}')
                sock.default_value = v.replace('_', ' ').title() if isinstance(v, str) else v
        nd.location = (self.x, 0)
        self.x += 180
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def math(self, op, a=None, b=None, c=None):
        nd = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.link(v, nd.inputs[i])
        return nd.outputs[0]

    def vmath(self, op, a=None, b=None, scale=None):
        nd = self.node('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                nd.inputs[i].default_value = v
            else:
                self.link(v, nd.inputs[i])
        if scale is not None:
            if isinstance(scale, (int, float)):
                nd.inputs['Scale'].default_value = scale
            else:
                self.link(scale, nd.inputs['Scale'])
        return nd.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else nd.outputs['Vector']


def pixel_size_group():
    """World size of one 'ink unit' at each point: frame size at that depth."""
    name = 'DS_PixelToWorld'
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    _sock(ng, 'Camera', 'NodeSocketObject')
    _sock(ng, 'Orthographic', 'NodeSocketBool', default=False)
    _sock(ng, 'Ortho Scale', 'NodeSocketFloat', default=1.0)
    _sock(ng, 'Sensor / Focal', 'NodeSocketFloat', default=36 / 50)
    _sock(ng, 'Frame World Size', 'NodeSocketFloat', io='OUTPUT')
    g = G(ng)
    gi = g.node('NodeGroupInput')
    go = g.node('NodeGroupOutput')
    oi = g.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    g.link(gi.outputs['Camera'], oi.inputs['Object'])
    pos = g.node('GeometryNodeInputPosition').outputs[0]
    rv = g.node('FunctionNodeRotateVector')
    rv.inputs['Vector'].default_value = (0, 0, -1)
    g.link(oi.outputs['Rotation'], rv.inputs['Rotation'])
    rel = g.vmath('SUBTRACT', pos, oi.outputs['Location'])
    depth = g.vmath('DOT_PRODUCT', rel, rv.outputs[0])
    depth = g.math('MAXIMUM', depth, 0.01)
    persp = g.math('MULTIPLY', depth, gi.outputs['Sensor / Focal'])
    sw = g.node('GeometryNodeSwitch', input_type='FLOAT')
    g.link(gi.outputs['Orthographic'], sw.inputs['Switch'])
    g.link(persp, sw.inputs['False'])
    g.link(gi.outputs['Ortho Scale'], sw.inputs['True'])
    g.link(sw.outputs[0], go.inputs['Frame World Size'])
    return ng


def ink_group():
    """Fill + inverted-hull outline + stepped line boil."""
    name = 'DS_InkOutline'
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    _sock(ng, 'Geometry', 'NodeSocketGeometry')
    _sock(ng, 'Camera', 'NodeSocketObject')
    _sock(ng, 'Orthographic', 'NodeSocketBool', default=False)
    _sock(ng, 'Ortho Scale', 'NodeSocketFloat', default=1.0)
    _sock(ng, 'Sensor / Focal', 'NodeSocketFloat', default=36 / 50)
    _sock(ng, 'Ink Fraction', 'NodeSocketFloat', default=12.73 / 1920, mn=0.0)
    _sock(ng, 'Outline', 'NodeSocketBool', default=True)
    _sock(ng, 'Fill Inset', 'NodeSocketFloat', default=0.5, mn=0.0, mx=1.0)
    _sock(ng, 'Boil Amount', 'NodeSocketFloat', default=0.0, mn=0.0, mx=1.0)
    _sock(ng, 'Boil Fraction', 'NodeSocketFloat', default=2.5 / 1920, mn=0.0)
    _sock(ng, 'Boil Step', 'NodeSocketInt', default=3, mn=1)
    _sock(ng, 'Seed', 'NodeSocketFloat', default=0.0)
    _sock(ng, 'Outline Material', 'NodeSocketMaterial')
    _sock(ng, 'Depth Bias', 'NodeSocketFloat', default=4.5, mn=0.0)
    _sock(ng, 'Geometry', 'NodeSocketGeometry', io='OUTPUT')
    g = G(ng)
    gi = g.node('NodeGroupInput')
    go = g.node('NodeGroupOutput')
    px = g.node('GeometryNodeGroup')
    px.node_tree = pixel_size_group()
    for k in ('Camera', 'Orthographic', 'Ortho Scale', 'Sensor / Focal'):
        g.link(gi.outputs[k], px.inputs[k])
    frame_w = px.outputs[0]
    ink_w = g.math('MULTIPLY', frame_w, gi.outputs['Ink Fraction'])
    # stepped boil: noise sampled at a time that jumps every N frames
    st = g.node('GeometryNodeInputSceneTime')
    stepped = g.math('FLOOR', g.math('DIVIDE', st.outputs['Frame'], gi.outputs['Boil Step']))
    w = g.math('ADD', g.math('MULTIPLY', stepped, 1.37), gi.outputs['Seed'])
    noise = g.node('ShaderNodeTexNoise', noise_dimensions='4D')
    noise.inputs['Scale'].default_value = 3.0
    noise.inputs['Detail'].default_value = 1.0
    pos = g.node('GeometryNodeInputPosition').outputs[0]
    g.link(pos, noise.inputs['Vector'])
    g.link(w, noise.inputs['W'])
    centred = g.math('SUBTRACT', noise.outputs['Fac'], 0.5)
    boil = g.math('MULTIPLY', g.math('MULTIPLY', centred, 2.0),
                  g.math('MULTIPLY', g.math('MULTIPLY', frame_w, gi.outputs['Boil Fraction']), gi.outputs['Boil Amount']))
    nrm = g.node('GeometryNodeInputNormal').outputs[0]
    # fill: pulled in by half a stroke (SVG strokes are centred on the edge) + boil
    fill_off = g.math('SUBTRACT', boil, g.math('MULTIPLY', g.math('MULTIPLY', ink_w, 0.5), gi.outputs['Fill Inset']))
    sp_fill = g.node('GeometryNodeSetPosition')
    g.link(gi.outputs['Geometry'], sp_fill.inputs['Geometry'])
    g.link(g.vmath('SCALE', nrm, scale=fill_off), sp_fill.inputs['Offset'])
    # shell: outward by the rest of the stroke + the same boil
    shell_off = g.math('ADD', boil, g.math('MULTIPLY', ink_w, g.math('SUBTRACT', 1.0, g.math('MULTIPLY', gi.outputs['Fill Inset'], 0.5))))
    # the shell also sits a few ink widths further from the camera: silhouettes are
    # untouched, but shallow creases (ear folds, the ear roots) stop drawing hard
    # cut lines; a line only appears where one form really overlaps another
    oi = g.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    g.link(gi.outputs['Camera'], oi.inputs['Object'])
    fwd = g.node('FunctionNodeRotateVector')
    fwd.inputs['Vector'].default_value = (0, 0, -1)
    g.link(oi.outputs['Rotation'], fwd.inputs['Rotation'])
    ray = g.node('ShaderNodeVectorMath', operation='NORMALIZE')
    g.link(g.vmath('SUBTRACT', pos, oi.outputs['Location']), ray.inputs[0])
    vdir = g.node('GeometryNodeSwitch', input_type='VECTOR')
    g.link(gi.outputs['Orthographic'], vdir.inputs['Switch'])
    g.link(ray.outputs['Vector'], vdir.inputs['False'])
    g.link(fwd.outputs[0], vdir.inputs['True'])
    away = g.vmath('SCALE', vdir.outputs[0], scale=g.math('MULTIPLY', ink_w, gi.outputs['Depth Bias']))
    sp_shell = g.node('GeometryNodeSetPosition')
    g.link(gi.outputs['Geometry'], sp_shell.inputs['Geometry'])
    g.link(g.vmath('ADD', g.vmath('SCALE', nrm, scale=shell_off), away), sp_shell.inputs['Offset'])
    flip = g.node('GeometryNodeFlipFaces')
    g.link(sp_shell.outputs[0], flip.inputs['Mesh'])
    sm = g.node('GeometryNodeSetMaterial')
    g.link(flip.outputs[0], sm.inputs['Geometry'])
    g.link(gi.outputs['Outline Material'], sm.inputs['Material'])
    sw = g.node('GeometryNodeSwitch', input_type='GEOMETRY')
    g.link(gi.outputs['Outline'], sw.inputs['Switch'])
    g.link(sm.outputs[0], sw.inputs['True'])
    join = g.node('GeometryNodeJoinGeometry')
    g.link(sp_fill.outputs[0], join.inputs[0])
    g.link(sw.outputs[0], join.inputs[0])
    g.link(join.outputs[0], go.inputs['Geometry'])
    return ng


def settings_object(coll=None):
    """Holds the look controls; everything else drives from here."""
    ob = bpy.data.objects.get('BUNNY_settings')
    if ob:
        return ob
    ob = bpy.data.objects.new('BUNNY_settings', None)
    ob.empty_display_type = 'PLAIN_AXES'
    ob.empty_display_size = 0.05
    (coll or bpy.context.scene.collection).objects.link(ob)
    props = {
        'ink_px': (12.73, 0.0, 80.0, 'Ink width in pixels on a 1920-pixel-long frame at camera zoom 1 (Doodle Studio: 11.32 source px = 12.73)'),
        'boil': (0.35, 0.0, 1.0, 'Line boil amount (Doodle Studio STYLE Line boil / 90)'),
        'boil_px': (2.5, 0.0, 20.0, 'Line boil travel in pixels on a 1920-pixel frame'),
        'boil_step': (3, 1, 12, 'Frames each boil drawing is held'),
    }
    for k, (v, mn, mx, desc) in props.items():
        ob[k] = v
        ui = ob.id_properties_ui(k)
        ui.update(min=mn, max=mx, description=desc)
    return ob


def _drive(target_id, path, src_id, src_path, expr=None, id_type='OBJECT', index=-1):
    fc = target_id.driver_add(path, index) if index >= 0 else target_id.driver_add(path)
    d = fc.driver
    v = d.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = id_type
    v.targets[0].id = src_id
    v.targets[0].data_path = src_path
    if expr:
        d.type = 'SCRIPTED'
        d.expression = expr  # kept to the simple-expression subset (no Python needed)
    else:
        d.type = 'AVERAGE'
    return fc


def apply_ink(ob, cam, mats, outline=True, seed=0.0):
    settings = settings_object()
    mod = ob.modifiers.new('DS Ink', 'NODES')
    mod.node_group = ink_group()
    ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}
    mod[ids['Camera']] = cam
    mod[ids['Outline Material']] = mats['shell']
    mod[ids['Outline']] = outline
    mod[ids['Seed']] = seed
    _drive(mod, f'["{ids["Orthographic"]}"]', cam.data, 'type', expr="v == 1", id_type='CAMERA')
    _drive(mod, f'["{ids["Ortho Scale"]}"]', cam.data, 'ortho_scale', id_type='CAMERA')
    fc = mod.driver_add(f'["{ids["Sensor / Focal"]}"]')
    d = fc.driver
    d.type = 'SCRIPTED'
    for nm, path in (('s', 'sensor_width'), ('f', 'lens')):
        v = d.variables.new()
        v.name = nm
        v.targets[0].id_type = 'CAMERA'
        v.targets[0].id = cam.data
        v.targets[0].data_path = path
    d.expression = 's / f'
    _drive(mod, f'["{ids["Ink Fraction"]}"]', settings, '["ink_px"]', expr='v / 1920')
    _drive(mod, f'["{ids["Boil Amount"]}"]', settings, '["boil"]')
    _drive(mod, f'["{ids["Boil Fraction"]}"]', settings, '["boil_px"]', expr='v / 1920')
    _drive(mod, f'["{ids["Boil Step"]}"]', settings, '["boil_step"]')
    return mod
