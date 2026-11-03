"""Light and shadow on the whole scene, and each object's own outline. Runs last, after the looks.

shot['stage'] = {
  'shadows': True,          # the key casts shadows, on everything; a sun when there is no 3-point light
  'halftone': True,         # the shadows print as ink dots
  'lighting': {'preset': 'classic', 'target': 'lead' | 'costar:0' | 'item:2', 'turn': 0, 'height': 1.9,
               'distance': 2.6, 'key': 1.1, 'fill': 0.4, 'back': 0.9, 'keyA': -35, 'fillA': 45, 'backA': 145,
               'keyZ': 1, 'fillZ': 1, 'backZ': 1, 'soft': 0.5, 'shade': 0.32, 'amb': 0.15},   # keyZ: of height
  'inks': {'flowers': 40, '@lead': 100, '@costar0': 80},    # percent of Bunny's line, by set piece or character
}
shot['items'][i]['ink'] = 40                                 # one prop

Flat fills are emission, which no light can touch, so here they become a three-step cel fill: the
light that lands (Diffuse > Shader to RGB) picks the step, and a step is the fill mixed toward ink.
These are the numbers the 3D view's bands use (app/src/lit.js), so the Stage shows the render.
The lamps are the Tri-lighting add-on's when it is installed, else the same three built here.
Nothing here runs unless the shot asks for it: older shots render exactly as before.
"""
import json
import math
import os
from types import SimpleNamespace

import bpy

import materials

BAND_MID, BAND_DARK = 0.55, 0.22
AMBIENT, SHADE = 0.15, 0.32
INK = '#1F1F1D'
# watts for a diffuse white surface facing an area light to read 1.0 at 1 m, measured in EEVEE;
# it falls off as 1 / r^2 like the 3D view's bands, up to a light about 1.5 m across
AREA_WATTS = 10.5


def wanted(shot):
    st = shot.get('stage') or {}
    return bool(st.get('shadows') or st.get('halftone') or st.get('lighting'))


# ---------------------------------------------------------------- each object's outline
def _key_of(ob, shot):
    """percent for this object, or None for Bunny's usual line"""
    st = shot.get('stage') or {}
    inks = st.get('inks') or {}
    it = materials._item_of(ob)
    items = shot.get('items') or []
    if it is not None:
        return items[it].get('ink') if it < len(items) else None
    if ob.get('dsl_prop') in inks:
        return inks[ob['dsl_prop']]
    if materials._rig_of(ob) is None:
        return None
    for c in ob.users_collection:
        if c.name.startswith('Costar '):
            return inks.get('@costar%d' % (int(c.name.split()[1]) - 1))
    return inks.get('@lead')


def inks(shot, log):
    n = 0
    for ob in bpy.data.objects:
        for md in ob.modifiers:
            if md.type != 'NODES' or md.name not in materials.INK_MODS or md.node_group is None:
                continue
            pct = _key_of(ob, shot)
            if pct is None or float(pct) == 100:
                continue
            k = max(0.0, float(pct)) / 100
            if k == 0:
                md.show_render = md.show_viewport = False
                n += 1
                continue
            sock = next(s.identifier for s in md.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT' and s.name == 'Ink Fraction')
            for fc in (ob.animation_data.drivers if ob.animation_data else []):
                if fc.data_path == f'modifiers["{md.name}"]["{sock}"]':
                    fc.driver.expression = 'v / 1920 * %.3f' % k
                    n += 1
    if n:
        log(f'lights: {n} outlines set by hand')
    return n


# ---------------------------------------------------------------- cel fills
def _dots(nt, cells):
    """1 inside a screen-space dot grid: the halftone print of the shadow"""
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / max(1, sc.render.resolution_y)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    grid = N.new('ShaderNodeVectorMath')
    grid.operation = 'MULTIPLY'
    grid.inputs[1].default_value = (cells * aspect, cells, 1.0)
    L.new(tc.outputs['Window'], grid.inputs[0])
    frac = N.new('ShaderNodeVectorMath')
    frac.operation = 'FRACTION'
    L.new(grid.outputs[0], frac.inputs[0])
    cen = N.new('ShaderNodeVectorMath')
    cen.operation = 'SUBTRACT'
    cen.inputs[1].default_value = (0.5, 0.5, 0.0)
    L.new(frac.outputs[0], cen.inputs[0])
    flat = N.new('ShaderNodeVectorMath')
    flat.operation = 'MULTIPLY'
    flat.inputs[1].default_value = (1.0, 1.0, 0.0)
    L.new(cen.outputs[0], flat.inputs[0])
    dist = N.new('ShaderNodeVectorMath')
    dist.operation = 'LENGTH'
    L.new(flat.outputs[0], dist.inputs[0])
    dot = N.new('ShaderNodeMath')
    dot.operation = 'LESS_THAN'
    dot.inputs[1].default_value = 0.34
    L.new(dist.outputs['Value'], dot.inputs[0])
    return dot.outputs[0]


def cel(m, shade, cells=0):
    """the flat colour of m, stepped toward ink where less light lands; same material, every slot keeps it"""
    col = tuple(m.diffuse_color)
    nt = m.node_tree
    nt.animation_data_clear()   # the library's toon fill drives its old nodes
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    em = N.new('ShaderNodeEmission')
    L.new(em.outputs[0], out.inputs['Surface'])
    diff = N.new('ShaderNodeBsdfDiffuse')
    diff.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = N.new('ShaderNodeShaderToRGB')
    L.new(diff.outputs[0], s2r.inputs[0])
    bw = N.new('ShaderNodeRGBToBW')
    L.new(s2r.outputs['Color'], bw.inputs[0])

    def under(level, weight):
        a = N.new('ShaderNodeMath')
        a.operation = 'LESS_THAN'
        L.new(bw.outputs[0], a.inputs[0])
        a.inputs[1].default_value = level
        b = N.new('ShaderNodeMath')
        b.operation = 'MULTIPLY'
        L.new(a.outputs[0], b.inputs[0])
        b.inputs[1].default_value = weight
        return b.outputs[0]

    step = N.new('ShaderNodeMath')
    step.operation = 'ADD'
    L.new(under(BAND_MID, 0.45), step.inputs[0])
    L.new(under(BAND_DARK, 0.55), step.inputs[1])
    fac = N.new('ShaderNodeMath')
    fac.operation = 'MULTIPLY'
    L.new(step.outputs[0], fac.inputs[0])
    fac.inputs[1].default_value = shade
    k = fac.outputs[0]
    if cells:
        pr = N.new('ShaderNodeMath')
        pr.operation = 'MULTIPLY'
        L.new(k, pr.inputs[0])
        L.new(_dots(nt, cells), pr.inputs[1])
        k = pr.outputs[0]
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = col
    mix.inputs['B'].default_value = tuple(materials.rgb(INK)) + (1.0,)
    L.new(k, mix.inputs['Factor'])
    L.new(mix.outputs['Result'], em.inputs['Color'])
    m['dsl_cel'] = 1


def _flat(m):
    if m is None or not m.use_nodes or m.get('dsl_cel'):
        return False
    return bool(m.get('dsl_toon') or materials._Painter._flat_emission(m))


def _ink(m):
    return materials._luma(m.diffuse_color) < 0.016


def fills(shade, cells):
    """every flat fill on a character, the set or a prop (lit looks like clay already read the light)"""
    g = materials.classify()
    obs = g['character'] + g['set'] + [o for v in g['props'].values() for o in v]
    done = set()
    for ob in obs:
        for slot in ob.material_slots:
            m = slot.material
            if m is not None and m.name not in done and _flat(m) and not _ink(m):
                done.add(m.name)
                cel(m, shade, cells)
    return len(done)


def ambient(level):
    """everything lit sees this even light; the camera keeps seeing the sky or backdrop as it is"""
    sc = bpy.context.scene
    old = sc.world
    if old is None or not old.use_nodes:
        materials._world({'ambient': '#FFFFFF'}, level)
        return
    w = old.copy()
    w.name = 'DSL lit world'
    nt = w.node_tree
    out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputWorld'), None)
    if out is None or not out.inputs['Surface'].is_linked:
        materials._world({'ambient': '#FFFFFF'}, level)
        return
    was = out.inputs['Surface'].links[0].from_socket
    amb = nt.nodes.new('ShaderNodeBackground')
    amb.inputs['Color'].default_value = (1, 1, 1, 1)
    amb.inputs['Strength'].default_value = level
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(was, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sc.world = w


# ---------------------------------------------------------------- the three lights
def _target(L, shot, arm):
    """an empty at waist height that follows what the light is centred on"""
    sc = bpy.context.scene
    e = bpy.data.objects.new('DSL_LightTarget', None)
    e.empty_display_size = 0.15
    sc.collection.objects.link(e)
    e.location = (0, 0, 0.5)
    kind, _, idx = str(L.get('target') or 'lead').partition(':')
    who = arm
    if kind == 'costar':
        col = bpy.data.collections.get('Costar %d' % (int(idx) + 1))
        who = next((o for o in col.all_objects if o.type == 'ARMATURE'), arm) if col else arm
    elif kind == 'item':
        ob = next((o for o in bpy.data.objects if o.get('ds_item') == int(idx)), None)
        if ob is not None:
            c = e.constraints.new('COPY_LOCATION')
            c.target = ob
            return e
    if who is not None:
        c = e.constraints.new('COPY_LOCATION')
        c.target = who
        if 'head' in who.pose.bones:
            c.subtarget = 'head'
        c.use_z = False
    return e


def _addon_lamps(target, L, log):
    """the Tri-lighting add-on makes the lamps, so they are its TriLamp lights in Blender. Its operator
    wants a window, which a render has not, so its code runs on a stand-in for the window."""
    import addon_utils
    for name in ('bl_ext.blender_org.tri_lighting', 'bl_ext.user_default.tri_lighting'):
        try:
            if addon_utils.enable(name, default_set=False) is not None:
                break
        except Exception:
            pass
    op = getattr(bpy.types, 'OBJECT_OT_trilighting', None)
    if op is None:
        return None
    sc = bpy.context.scene
    was = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = target
    kw = dict(height=5, distance=5, energy=100, contrast=50, leftangle=26, rightangle=45, backangle=235,
              primarytype='AREA', secondarytype='AREA', key_light_shape='SQUARE', secondary_light_shape='SQUARE',
              key_light_size=1, secondary_light_size=1, key_light_size_x=1, key_light_size_y=1, secondary_light_size_x=1, secondary_light_size_y=1,
              shadow_soft_size_key=0, shadow_soft_size_fill=0, spot_size_key=0.785, spot_blend_key=0.15, spot_size_fill=0.785, spot_blend_fill=0.15)
    fake = SimpleNamespace(report=lambda *a: None, **kw)
    ctx = SimpleNamespace(collection=sc.collection, scene=sc, space_data=SimpleNamespace(type='NONE'))
    before = set(bpy.data.objects)
    try:
        r = op.execute(fake, ctx)
    except Exception as e:
        log(f'lights: the Tri-lighting add-on could not run ({e}); building the same lights')
        return None
    finally:
        bpy.context.view_layer.objects.active = was
    new = [o for o in bpy.data.objects if o not in before and o.type == 'LIGHT']
    got = {k: next((o for o in new if o.name.startswith('TriLamp-' + k.title())), None) for k in ('key', 'fill', 'back')}
    if 'FINISHED' not in r or not all(got.values()):
        for o in new:
            bpy.data.objects.remove(o)
        return None
    return got


def _built_lamps(target):
    sc = bpy.context.scene
    got = {}
    for k in ('key', 'fill', 'back'):
        ob = bpy.data.objects.new('TriLamp-' + k.title(), bpy.data.lights.new('TriLamp-' + k.title(), 'AREA'))
        sc.collection.objects.link(ob)
        c = ob.constraints.new('TRACK_TO')
        c.target = target
        c.track_axis, c.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
        got[k] = ob
    return got


def rig(L, shot, arm, shadows, log):
    target = _target(L, shot, arm)
    lamps = _addon_lamps(target, L, log)
    source = 'Tri-lighting add-on' if lamps else 'built in'
    lamps = lamps or _built_lamps(target)
    d, h = float(L.get('distance', 2.6)), float(L.get('height', 1.9))
    size = 0.2 + 0.8 * float(L.get('soft', 0.5))   # a big lamp wraps round a form and the bands go
    for k, ob in lamps.items():
        a = math.radians(float(L.get('turn', 0)) + float(L.get(k + 'A', 0)))
        ob.parent = target
        z = h * float(L.get(k + 'Z', 1)) - 0.5
        ob.location = (d * math.sin(a), -d * math.cos(a), z)
        ob.data.type = 'AREA'
        ob.data.shape = 'SQUARE'
        ob.data.size = size
        ob.data.energy = float(L.get(k, 1.0)) * (d * d + z * z) * AREA_WATTS
        ob.data.color = (1, 1, 1)
        if hasattr(ob.data, 'use_shadow'):
            ob.data.use_shadow = shadows and k == 'key'
    # one light rig: the set's sun and the lit looks' lights step aside
    for name in ('DSL_Sun', 'DSM_Key', 'DSM_Fill'):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.type == 'LIGHT':
            if ob.data.animation_data:
                ob.data.animation_data_clear()
            ob.data.energy = 0.0
    log(f'lights: {L.get("preset") or "3-point"} on {L.get("target") or "lead"} ({source})')
    return {'lamps': {k: o.name for k, o in lamps.items()}, 'source': source}


def sun(st, log):
    from doodle_library import style   # stage.setup has loaded the library
    s = style.ensure_sun()
    if hasattr(s.data, 'use_shadow'):
        s.data.use_shadow = True
    if st.get('time') != 'night' and (st.get('sun') or {}).get('energy') is None:
        s.data.energy = 3.0   # the level the 3D view's sun uses (SUN_ENERGY in lit.js)
    return {'lamps': {'key': s.name}, 'source': 'sun'}


# ---------------------------------------------------------------- entry point
def apply(shot, cam, arm, log, out_dir=None):
    n = inks(shot, log)
    if not wanted(shot):
        return {'inks': n} if n else None
    st = shot.get('stage') or {}
    L = st.get('lighting')
    shadows = bool(st.get('shadows') or st.get('halftone'))
    shade = float((L or {}).get('shade', SHADE))
    made = fills(shade, int(st.get('halftone_cells') or 90) if st.get('halftone') else 0)
    report = rig(L, shot, arm, shadows, log) if L else sun(st, log)
    ambient(float((L or {}).get('amb', AMBIENT)))
    # the room's walls and roof light things, they must not stand between a lamp and the actors
    for ob in bpy.data.objects:
        if ob.get('dsl_shell'):
            ob.visible_shadow = False
    report.update(inks=n, fills=made, shadows=shadows)
    log(f'lights: {made} fills read the light, shadows {"on" if shadows else "off"}')
    if out_dir:
        try:
            json.dump(report, open(os.path.join(out_dir, 'lights.json'), 'w'), indent=1)
        except OSError:
            pass
    return report
