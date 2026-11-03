"""Effects in the air: rain, snow, leaves, petals, wind, confetti, fireworks, speed lines,
dust, smoke, steam and sparkles.

Each effect is ONE object with a geometry-nodes setup that scatters a tiny ink shape
(models fx_*) and moves it from the frame number, so it loops forever, scrubs exactly and
costs a few hundred faces. Two setups cover everything:

  loop   things that keep coming: fall, drift, rise, streak (rain, snow, smoke, wind)
  burst  things that go off once at a frame: confetti, fireworks, dust, sparkles, poof

    fx.add_effect('rain')                         # around Bunny, from frame 1
    fx.add_effect('confetti', frame=48)           # goes off at 48
    fx.set_amount(ob, 0.5)                        # half as much
"""
import math

import bpy
from mathutils import Vector

from . import index, paths, style
from . import gnodes

LOOP, BURST = 'DSL_FX_Loop', 'DSL_FX_Burst'

# piece, setup, settings. loop: count, box, dir, speed (m/frame), travel, sway, spin, scale, grow
# burst: count, radius, gravity, length (frames), up (bias), spin, scale
EFFECTS = {
    'rain': ('fx_drop', 'loop', dict(count=420, box=(7, 5, 0.1), dir=(0.05, 0, -1), speed=0.22, travel=4.5, sway=0, spin=0,
                                     scale=1.0)),
    'downpour': ('fx_drop', 'loop', dict(count=1100, box=(7, 5, 0.1), dir=(0.12, 0, -1), speed=0.3, travel=4.5, sway=0,
                                         spin=0, scale=1.2)),
    'splashes': ('fx_splash', 'loop', dict(count=60, box=(5, 4, 0.0), dir=(0, 0, 0), speed=0.06, travel=1.0, sway=0, spin=0,
                                           scale=1.0, grow=1.0)),
    'snow': ('fx_flake', 'loop', dict(count=320, box=(7, 5, 0.1), dir=(0, 0, -1), speed=0.012, travel=4.5, sway=0.25,
                                      spin=0.05, scale=1.0)),
    'leaves': ('fx_leaf', 'loop', dict(count=45, box=(7, 4, 0.1), dir=(0.35, 0, -1), speed=0.014, travel=4.5, sway=0.35,
                                       spin=0.09, scale=1.4)),
    'petals': ('fx_petal', 'loop', dict(count=70, box=(7, 4, 0.1), dir=(0.25, 0, -1), speed=0.01, travel=4.5, sway=0.3,
                                        spin=0.07, scale=1.2)),
    'wind': ('fx_wind_line', 'loop', dict(count=10, box=(0.1, 3, 2.4), dir=(1, 0, 0), speed=0.12, travel=9, sway=0.04,
                                          spin=0, scale=1.0)),
    'speed_lines': ('fx_speed_line', 'loop', dict(count=22, box=(0.1, 2, 2.2), dir=(-1, 0, 0), speed=0.35, travel=8, sway=0,
                                                  spin=0, scale=1.0)),
    'steam': ('fx_puff', 'loop', dict(count=6, box=(0.03, 0.03, 0.0), dir=(0, 0, 1), speed=0.005, travel=0.3, sway=0.02,
                                      spin=0.01, scale=0.35, grow=1.0)),
    'smoke': ('fx_puff', 'loop', dict(count=14, box=(0.2, 0.2, 0.0), dir=(0.1, 0, 1), speed=0.012, travel=1.6, sway=0.1,
                                      spin=0.01, scale=1.6, grow=1.0)),
    'sparkles': ('fx_sparkle', 'loop', dict(count=24, box=(0.8, 0.5, 0.0), dir=(0, 0, 1), speed=0.006, travel=1.0,
                                            sway=0.05, spin=0.04, scale=1.0, grow=1.0)),
    'confetti': ('fx_confetti', 'burst', dict(count=160, radius=1.3, gravity=1.0, length=48, up=0.8, spin=0.25, scale=1.0)),
    'streamers': ('fx_streamer', 'burst', dict(count=24, radius=1.0, gravity=0.9, length=48, up=0.9, spin=0.1, scale=1.5)),
    'fireworks': ('fx_sparkle', 'burst', dict(count=90, radius=1.1, gravity=0.35, length=40, up=0.0, spin=0.1, scale=1.4)),
    'dust': ('fx_dust', 'burst', dict(count=10, radius=0.35, gravity=-0.08, length=20, up=0.1, spin=0.02, scale=1.0)),
    'poof': ('fx_puff', 'burst', dict(count=16, radius=0.45, gravity=-0.1, length=18, up=0.3, spin=0.03, scale=2.2)),
    'sparkle_burst': ('fx_sparkle', 'burst', dict(count=26, radius=0.45, gravity=0.0, length=22, up=0.3, spin=0.2,
                                                  scale=1.0)),
}
WHERE = {  # default spots, relative to Bunny standing at the origin
    'rain': (0, 0.5, 4.0), 'downpour': (0, 0.5, 4.0), 'snow': (0, 0.5, 4.0), 'leaves': (0, 0.5, 4.0),
    'petals': (0, 0.5, 4.0), 'splashes': (0, 0.3, 0.005), 'wind': (-4.5, 0.6, 0.2), 'speed_lines': (4, 0.8, 0.0),
    'smoke': (0.9, 1.2, 0.0), 'sparkles': (0, 0, 0.4), 'confetti': (0, 0.2, 1.4), 'streamers': (0, 0.2, 1.4),
    'fireworks': (0.6, 6.0, 3.2), 'dust': (0, 0, 0.02), 'poof': (0, 0, 0.45), 'sparkle_burst': (0, -0.1, 0.9),
    'steam': (0, 0, 0),
}


def _piece(name):
    """The tiny ink shape an effect scatters (kept hidden, used as the instance)."""
    ob = bpy.data.objects.get('DSL fx ' + name)
    if ob:
        return ob
    it = {'file': 'packs/packs.blend'}
    with bpy.data.libraries.load(paths.lib_path(it['file']), link=False) as (src, dst):
        dst.objects = ['scenery-' + name]
    ob = dst.objects[0]
    ob.name = 'DSL fx ' + name
    style.remap_materials(ob)
    if 'dsl_crease' not in ob.data.attributes:
        style.compute_creases(ob.data)
    coll = bpy.data.collections.get('Doodle FX pieces')
    if not coll:
        coll = bpy.data.collections.new('Doodle FX pieces')
        bpy.context.scene.collection.children.link(coll)
        coll.hide_render = True
        coll.hide_viewport = True
    coll.objects.link(ob)
    return ob


# ---------------------------------------------------------------- node setups
def _sock(io, name, typ, val=None, inout='INPUT'):
    s = io.new_socket(name, in_out=inout, socket_type=typ)
    if val is not None:
        s.default_value = val
    return s


class _G:
    """Tiny helper to wire math nodes without the boilerplate."""

    def __init__(self, ng):
        self.N, self.L = ng.nodes, ng.links

    def node(self, typ, **kw):
        n = self.N.new(typ)
        for k, v in kw.items():
            gnodes.set_option(n, k, v)
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, c=None):
        n = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        if scale is not None:
            if isinstance(scale, (int, float)):
                n.inputs['Scale'].default_value = scale
            else:
                self.link(scale, n.inputs['Scale'])
        return n.outputs['Value' if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else 'Vector']

    def rand(self, kind, lo, hi, seed):
        n = self.node('FunctionNodeRandomValue', data_type=kind)
        for name, v in (('Min', lo), ('Max', hi)):
            s = gnodes.sock(n.inputs, name)
            if isinstance(v, (int, float, tuple)):
                s.default_value = v
            else:
                self.link(v, s)
        n.inputs['Seed'].default_value = seed
        return gnodes.sock(n.outputs, 'Value')


def _common_io(ng):
    io = ng.interface
    _sock(io, 'Geometry', 'NodeSocketGeometry')
    _sock(io, 'Piece', 'NodeSocketObject')
    _sock(io, 'Count', 'NodeSocketInt', 100)
    _sock(io, 'Frame', 'NodeSocketFloat', 1.0)
    _sock(io, 'Seed', 'NodeSocketInt', 0)
    _sock(io, 'Spin', 'NodeSocketFloat', 0.0)
    _sock(io, 'Scale', 'NodeSocketFloat', 1.0)
    _sock(io, 'Geometry', 'NodeSocketGeometry', inout='OUTPUT')


def _finish(g, gi, go, pos, scale, rot):
    pts = g.node('GeometryNodePoints')
    g.link(gi.outputs['Count'], pts.inputs['Count'])
    g.link(pos, pts.inputs['Position'])
    info = g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    g.link(gi.outputs['Piece'], info.inputs['Object'])
    inst = g.node('GeometryNodeInstanceOnPoints')
    g.link(pts.outputs[0], inst.inputs['Points'])
    g.link(info.outputs['Geometry'], inst.inputs['Instance'])
    g.link(rot, inst.inputs['Rotation'])
    g.link(scale, inst.inputs['Scale'])
    real = g.node('GeometryNodeRealizeInstances')
    g.link(inst.outputs[0], real.inputs[0])
    g.link(real.outputs[0], go.inputs['Geometry'])


def _spin_rot(g, gi, seed):
    r0 = g.rand('FLOAT_VECTOR', (0, 0, 0), (6.283, 6.283, 6.283), seed + 7)
    sp = g.math('MULTIPLY', gi.outputs['Spin'], gi.outputs['Frame'])
    rr = g.rand('FLOAT_VECTOR', (0.5, 0.5, 0.5), (1.5, 1.5, 1.5), seed + 8)
    turn = g.vmath('SCALE', rr, scale=sp)
    return g.vmath('ADD', r0, turn)


def loop_group():
    ng = bpy.data.node_groups.get(LOOP)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(LOOP, 'GeometryNodeTree')
    _common_io(ng)
    io = ng.interface
    _sock(io, 'Box', 'NodeSocketVector', (6, 4, 0.1))
    _sock(io, 'Direction', 'NodeSocketVector', (0, 0, -1))
    _sock(io, 'Speed', 'NodeSocketFloat', 0.1)
    _sock(io, 'Travel', 'NodeSocketFloat', 4.0)
    _sock(io, 'Sway', 'NodeSocketFloat', 0.0)
    _sock(io, 'Grow', 'NodeSocketFloat', 0.0)
    g = _G(ng)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    half = g.vmath('SCALE', gi.outputs['Box'], scale=0.5)
    neg = g.vmath('SCALE', gi.outputs['Box'], scale=-0.5)
    base = g.rand('FLOAT_VECTOR', neg, half, 1)
    phase = g.rand('FLOAT', 0.0, 1.0, 2)
    # t = fract(phase + frame * speed / travel): each piece crosses the travel distance, then wraps
    rate = g.math('DIVIDE', gi.outputs['Speed'], gi.outputs['Travel'])
    t = g.math('FRACT', g.math('ADD', phase, g.math('MULTIPLY', gi.outputs['Frame'], rate)))
    along = g.math('MULTIPLY', g.math('SUBTRACT', t, 0.5), gi.outputs['Travel'])
    dirn = g.vmath('NORMALIZE', gi.outputs['Direction'])
    move = g.vmath('SCALE', dirn, scale=along)
    ph2 = g.rand('FLOAT', 0.0, 6.283, 3)
    sw = g.math('MULTIPLY', g.math('SINE', g.math('ADD', ph2, g.math('MULTIPLY', gi.outputs['Frame'], 0.07))),
                gi.outputs['Sway'])
    comb = g.node('ShaderNodeCombineXYZ')
    g.link(sw, comb.inputs['X'])
    pos = g.vmath('ADD', g.vmath('ADD', base, move), comb.outputs[0])
    # Grow: pieces swell as they travel and fade out at the end (smoke, steam, splashes)
    fade = g.math('SUBTRACT', 1.0, g.math('POWER', t, 3.0))
    grown = g.math('MULTIPLY', g.math('ADD', 0.3, t), fade)
    s = g.math('ADD', g.math('MULTIPLY', grown, gi.outputs['Grow']),
               g.math('SUBTRACT', 1.0, gi.outputs['Grow']))
    sr = g.rand('FLOAT', 0.7, 1.3, 4)
    scale = g.math('MULTIPLY', g.math('MULTIPLY', s, sr), gi.outputs['Scale'])
    _finish(g, gi, go, pos, scale, _spin_rot(g, gi, 10))
    return ng


def burst_group():
    ng = bpy.data.node_groups.get(BURST)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(BURST, 'GeometryNodeTree')
    _common_io(ng)
    io = ng.interface
    _sock(io, 'Start', 'NodeSocketFloat', 1.0)
    _sock(io, 'Length', 'NodeSocketFloat', 40.0)
    _sock(io, 'Radius', 'NodeSocketFloat', 1.0)
    _sock(io, 'Gravity', 'NodeSocketFloat', 1.0)
    _sock(io, 'Up', 'NodeSocketFloat', 0.5)
    g = _G(ng)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    d = g.rand('FLOAT_VECTOR', (-1, -0.6, -1), (1, 0.6, 1), 1)
    upv = g.node('ShaderNodeCombineXYZ')
    g.link(gi.outputs['Up'], upv.inputs['Z'])
    dirn = g.vmath('NORMALIZE', g.vmath('ADD', d, upv.outputs[0]))
    t = g.math('DIVIDE', g.math('SUBTRACT', gi.outputs['Frame'], gi.outputs['Start']), gi.outputs['Length'])
    t = g.math('MINIMUM', g.math('MAXIMUM', t, 0.0), 1.0)
    ease = g.math('SUBTRACT', 1.0, g.math('POWER', g.math('SUBTRACT', 1.0, t), 2.0))
    sp = g.rand('FLOAT', 0.5, 1.0, 2)
    out = g.vmath('SCALE', dirn, scale=g.math('MULTIPLY', g.math('MULTIPLY', ease, gi.outputs['Radius']), sp))
    drop = g.node('ShaderNodeCombineXYZ')
    g.link(g.math('MULTIPLY', g.math('MULTIPLY', t, t), g.math('MULTIPLY', gi.outputs['Gravity'], -1.0)), drop.inputs['Z'])
    pos = g.vmath('ADD', out, drop.outputs[0])
    # nothing shows before the start frame; pieces shrink away at the end
    alive = g.math('GREATER_THAN', gi.outputs['Frame'], gi.outputs['Start'])
    s = g.math('MULTIPLY', g.math('SUBTRACT', 1.0, g.math('POWER', t, 4.0)), alive)
    sr = g.rand('FLOAT', 0.7, 1.3, 4)
    scale = g.math('MULTIPLY', g.math('MULTIPLY', s, sr), gi.outputs['Scale'])
    _finish(g, gi, go, pos, scale, _spin_rot(g, gi, 10))
    return ng


# ---------------------------------------------------------------- public
def _ids(mod):
    return {s.name: s.identifier for s in mod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}


def add_effect(kind, frame=None, location=None, parent=None, amount=1.0, cam=None):
    """Add an effect object. `frame` is when a burst goes off (loops run all the time)."""
    if kind not in EFFECTS:
        raise KeyError('No effect "%s". Pick one of: %s' % (kind, ', '.join(EFFECTS)))
    piece, setup, cfg = EFFECTS[kind]
    me = bpy.data.meshes.new('FX ' + kind)
    ob = bpy.data.objects.new('FX ' + kind, me)
    from .assets import target_collection
    target_collection().objects.link(ob)
    ob.location = Vector(location if location is not None else WHERE.get(kind, (0, 0, 0)))
    if parent is not None:
        mw = ob.matrix_world.copy()
        ob.parent = parent
        ob.matrix_world = mw
    mod = ob.modifiers.new('DSL FX', 'NODES')
    mod.node_group = loop_group() if setup == 'loop' else burst_group()
    ids = _ids(mod)
    gnodes.gn_set(mod, ids['Piece'], _piece(piece))
    gnodes.gn_set(mod, ids['Count'], max(1, int(cfg['count'] * amount)))
    gnodes.gn_set(mod, ids['Seed'], hash(kind) % 1000)
    gnodes.gn_set(mod, ids['Spin'], cfg.get('spin', 0.0))
    gnodes.gn_set(mod, ids['Scale'], cfg.get('scale', 1.0))
    if setup == 'loop':
        for k, n in (('box', 'Box'), ('dir', 'Direction')):
            gnodes.gn_set(mod, ids[n], cfg[k])
        for k, n in (('speed', 'Speed'), ('travel', 'Travel'), ('sway', 'Sway'), ('grow', 'Grow')):
            gnodes.gn_set(mod, ids[n], float(cfg.get(k, 0.0)))
    else:
        f = bpy.context.scene.frame_current if frame is None else frame
        gnodes.gn_set(mod, ids['Start'], float(f))
        for k, n in (('length', 'Length'), ('radius', 'Radius'), ('gravity', 'Gravity'), ('up', 'Up')):
            gnodes.gn_set(mod, ids[n], float(cfg[k]))
    fc = gnodes.gn_driver_add(mod, ids['Frame'])
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = 'frame'
    ob['dsl_fx'] = kind
    ob['dsl_fx_base'] = cfg['count']
    style.apply_style(ob, cam or bpy.context.scene.camera, seed=0.5)
    return ob


def set_amount(ob, amount):
    mod = ob.modifiers.get('DSL FX')
    ids = _ids(mod)
    gnodes.gn_set(mod, ids['Count'], max(1, int(ob.get('dsl_fx_base', 100) * amount)))
    ob.update_tag()


def effects():
    return list(EFFECTS)
