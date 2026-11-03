"""Blender powers for Doodle Studio 3D shots (shot['powers'], all opt-in):

  doodles  [{points: [[x, y, z], ...], frame, draw}]   ink strokes drawn in 3D space, drawing on
  autoink  true                                         ink outline on every model that has none
  scatter  [{kind: grass|pebbles|flowers|leaves, center: [x, y], radius, count, seed}]
  crowd    {count, rows, distance, seed, cheer}         doodle silhouettes behind the character
  liquids  [{kind: splash|pour|puddle, frame, at: [x, y, z]}]   toon liquid, no simulation
  fisheye  0..1                                         barrel lens in the compositor
  pano360  true                                         equirectangular 360 video (Cycles)

Every piece is wrapped so a failure logs and the render carries on. Brand colours only.
"""
import math
import random

import bpy
from mathutils import Vector

import look


def _mats():
    return look.materials()


def _ink_px():
    s = bpy.data.objects.get('BUNNY_settings')
    return float(s['ink_px']) if s is not None and 'ink_px' in s else 12.73


def _world_per_px(cam, at):
    # ink_px is measured on a 1920-pixel-long frame, whatever the render size
    if cam.data.type == 'ORTHO':
        return cam.data.ortho_scale / 1920
    if cam.data.type == 'PANO':   # a 360 viewer sees about a normal lens's worth at once
        # and there is no 2D zoom to scale the ink, so strokes use the base weight
        d = max(0.05, (Vector(at) - cam.matrix_world.translation).length)
        return d * 0.7 / 1920 * 12.73 / _ink_px()
    d = (cam.matrix_world.inverted() @ Vector(at)).z * -1
    return 2 * max(0.05, d) * math.tan(cam.data.angle / 2) / 1920


def _near_cam(cam, p):
    c = cam.matrix_world.translation
    return cam.data.type == 'PANO' and Vector((p.x - c.x, p.y - c.y)).length < 0.9


def _link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _show_from(ob, f):
    if f <= 1:
        return
    ob.hide_render = True
    ob.keyframe_insert('hide_render', frame=f - 1)
    ob.hide_render = False
    ob.keyframe_insert('hide_render', frame=f)
    for fc in look_fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'


def look_fcurves(ob):
    import compat
    return compat.fcurves(ob)


# ---------------------------------------------------------------- doodles in 3D (drawn on, screen-true line weight)
def doodles(spec, cam, log):
    n = 0
    for i, d in enumerate(spec or []):
        pts = [Vector(p) for p in d.get('points') or []]
        if len(pts) < 2:
            continue
        f = int(d.get('frame', 0)) + 1
        bpy.context.scene.frame_set(f)
        cu = bpy.data.curves.new(f'DS_doodle{i}', 'CURVE')
        cu.dimensions = '3D'
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for k, p in enumerate(pts):
            sp.points[k].co = (p.x, p.y, p.z, 1.0)
        mid = pts[len(pts) // 2]
        cu.bevel_depth = _ink_px() * _world_per_px(cam, mid) / 2
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        ob = _link(bpy.data.objects.new(f'DS_doodle{i}', cu))
        ob.data.materials.append(_mats()['ink'])
        draw = max(1, int(d.get('draw', 12)))
        cu.bevel_factor_end = 0.0
        cu.keyframe_insert('bevel_factor_end', frame=f)
        cu.bevel_factor_end = 1.0
        cu.keyframe_insert('bevel_factor_end', frame=f + draw)
        _show_from(ob, f)
        n += 1
    log(f'powers: {n} doodles')


# ---------------------------------------------------------------- auto-ink: any model without an outline gets Bunny's
def autoink(cam, log):
    mats, n = _mats(), 0
    for ob in list(bpy.data.objects):
        if ob.type != 'MESH' or ob.name.startswith(('BUNNY_', 'DS_ink')) or ob.hide_render:
            continue
        # library pieces, effects and anything already inked carry a geometry-nodes modifier
        if any(m.type == 'NODES' for m in ob.modifiers):
            continue
        try:
            if not any(ob.data.materials):   # brand colours only: a bare model gets the mustard fill
                ob.data.materials.append(mats['mustard'])
            look.apply_ink(ob, cam, mats, outline=True, seed=n * 0.37)
            n += 1
        except Exception as e:
            log(f'powers: autoink {ob.name}: {e}')
    log(f'powers: auto-ink on {n} models')


# ---------------------------------------------------------------- scatter: one joined mesh, one ink pass
def _piece(bm, kind, rnd, at, s):
    import bmesh
    rot = rnd.uniform(0, math.tau)
    if kind == 'pebbles':
        geom = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.025 * s)
        vs = geom['verts']
        for v in vs:
            v.co.z *= 0.45
    elif kind == 'leaves':
        geom = bmesh.ops.create_circle(bm, cap_ends=True, segments=8, radius=0.03 * s)
        vs = geom['verts']
        for v in vs:
            v.co.y *= 0.45
    elif kind == 'flowers':
        vs = []
        for k in range(5):
            a = k / 5 * math.tau
            g = bmesh.ops.create_circle(bm, cap_ends=True, segments=8, radius=0.018 * s)
            for v in g['verts']:
                v.co += Vector((math.cos(a) * 0.02 * s, math.sin(a) * 0.02 * s, 0.07 * s))
            vs += g['verts']
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=0.004 * s, radius2=0.004 * s, depth=0.07 * s)
        for v in g['verts']:
            v.co.z += 0.035 * s
        vs += g['verts']
    else:  # unused: grass is drawn as ink tufts
        vs = []
        for k in range(3):
            g = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.008 * s, radius2=0.0, depth=0.08 * s)
            lean = (k - 1) * 0.35
            for v in g['verts']:
                z = v.co.z + 0.04 * s
                v.co = Vector((v.co.x + math.sin(lean) * z + (k - 1) * 0.008 * s, v.co.y, z * math.cos(lean)))
            vs += g['verts']
    c, sn = math.cos(rot), math.sin(rot)
    for v in vs:
        x, y = v.co.x, v.co.y
        v.co = Vector((at.x + x * c - y * sn, at.y + x * sn + y * c, at.z + v.co.z))


def _grass(i, sc, rnd, cx, cy, r, n, cam, log):
    # grass is drawn, not modelled: short ink tufts at Bunny's line weight, like the 2D doodles
    cu = bpy.data.curves.new(f'DS_scatter{i}', 'CURVE')
    cu.dimensions = '3D'
    made = 0
    for _ in range(n):
        a, d = rnd.uniform(0, math.tau), r * math.sqrt(rnd.random())
        p = Vector((cx + math.cos(a) * d, cy + math.sin(a) * d, 0.0))
        if p.length < 0.35 or _near_cam(cam, p):
            continue
        s = rnd.uniform(0.8, 1.2)
        for k in (-1, 0, 1):
            sp = cu.splines.new('POLY')
            sp.points.add(1)
            lean = k * 0.45 + rnd.uniform(-0.1, 0.1)
            sp.points[0].co = (p.x + k * 0.012 * s, p.y, 0.0, 1.0)
            sp.points[1].co = (p.x + k * 0.012 * s + math.sin(lean) * 0.07 * s, p.y, math.cos(lean) * (0.09 if k == 0 else 0.065) * s, 1.0)
        made += 1
    cu.bevel_depth = _ink_px() * _world_per_px(cam, (cx, cy, 0.0)) / 2
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    ob = _link(bpy.data.objects.new(f'DS_scatter{i}_grass', cu))
    ob.data.materials.append(_mats()['ink'])
    log(f'powers: scatter grass x{made}')


def scatter(spec, cam, log):
    import bmesh
    for i, sc in enumerate(spec or []):
        kind = sc.get('kind', 'grass')
        rnd = random.Random(int(sc.get('seed', 1)))
        cx, cy = (sc.get('center') or [0.0, 0.6])[:2]
        r, n = float(sc.get('radius', 1.0)), min(400, int(sc.get('count', 30)))
        if kind == 'grass':
            _grass(i, sc, rnd, cx, cy, r, n, cam, log)
            continue
        bm = bmesh.new()
        for _ in range(n):
            a, d = rnd.uniform(0, math.tau), r * math.sqrt(rnd.random())
            p = Vector((cx + math.cos(a) * d, cy + math.sin(a) * d, 0.0))
            if p.length < 0.35 or _near_cam(cam, p):   # keep clear of the character's feet (and a 360 camera)
                continue
            _piece(bm, kind, rnd, p, rnd.uniform(0.75, 1.3))
        me = bpy.data.meshes.new(f'DS_scatter{i}')
        bm.to_mesh(me)
        bm.free()
        ob = _link(bpy.data.objects.new(f'DS_scatter{i}_{kind}', me))
        ob.data.materials.append(_mats()['mustard'])
        look.apply_ink(ob, cam, _mats(), outline=True, seed=i * 0.71)
        log(f'powers: scatter {kind} x{n}')


# ---------------------------------------------------------------- crowd: ink silhouettes that bob and cheer
def _char_span(cam):
    # the character's screen x range (0..1), so nobody in the crowd stands behind or touches them
    from bpy_extras.object_utils import world_to_camera_view
    sc, xs = bpy.context.scene, []
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.name.startswith('BUNNY_') and not ob.hide_render:
            for c in ob.bound_box:
                xs.append(world_to_camera_view(sc, cam, ob.matrix_world @ Vector(c)).x)
    return (min(xs) - 0.04, max(xs) + 0.04) if xs else (0.38, 0.62)


def crowd(spec, cam, log):
    from bpy_extras.object_utils import world_to_camera_view
    import bmesh
    rnd = random.Random(int(spec.get('seed', 3)))
    count, rows = min(80, int(spec.get('count', 18))), max(1, int(spec.get('rows', 2)))
    dist, cheer = float(spec.get('distance', 2.2)), bool(spec.get('cheer', True))
    sc = bpy.context.scene
    per = math.ceil(count / rows)
    lo, hi = _char_span(cam)
    made = 0
    for r in range(rows):
        y = dist + r * 0.45
        width, slots, row_made = 2.4 + y * 0.9, per + 6, 0
        for k in range(slots):
            if made >= count or row_made >= per:
                break
            x = -width / 2 + (k + 0.5) * width / slots + rnd.uniform(-0.04, 0.04)
            s = rnd.uniform(0.85, 1.15)
            a = world_to_camera_view(sc, cam, Vector((x - 0.17 * s, y, 0.3))).x
            b = world_to_camera_view(sc, cam, Vector((x + 0.17 * s, y, 0.3))).x
            if min(a, b) < hi and max(a, b) > lo:
                continue
            bm = bmesh.new()
            g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.16 * s)
            for v in g['verts']:
                v.co.z = v.co.z * 1.25 + 0.2 * s
            g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.1 * s)
            for v in g['verts']:
                v.co.z += 0.5 * s
            me = bpy.data.meshes.new('DS_crowd')
            bm.to_mesh(me)
            bm.free()
            ob = _link(bpy.data.objects.new(f'DS_crowd{made}', me))
            ob.location = (x, y, 0.0)
            ob.data.materials.append(_mats()['ink'])
            look.apply_ink(ob, cam, _mats(), outline=True, seed=made * 0.13)
            if cheer:
                ph, sp, hop = rnd.uniform(0, math.tau), rnd.uniform(0.18, 0.3), rnd.uniform(0.03, 0.07)
                for f in range(sc.frame_start, sc.frame_end + 1, 3):
                    ob.location.z = max(0.0, math.sin(f * sp + ph)) * hop
                    ob.keyframe_insert('location', index=2, frame=f)
            made += 1
            row_made += 1
    log(f'powers: crowd of {made}')


# ---------------------------------------------------------------- jelly: a decaying squash wobble, volume kept
def jelly(ob, frame, amount=0.22, length=22):
    base = ob.scale.copy()
    for k in range(0, length + 1, 2):
        w = amount * math.exp(-k / (length / 3.2)) * math.cos(k * 0.75)
        z = 1 - w
        ob.scale = (base.x / math.sqrt(z), base.y / math.sqrt(z), base.z * z)
        ob.keyframe_insert('scale', frame=frame + k)
    ob.scale = base
    ob.keyframe_insert('scale', frame=frame + length + 2)


# ---------------------------------------------------------------- toon liquids: droplets on arcs, a puddle that spreads
def _blob(name, r, mat):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = _link(bpy.data.objects.new(name, me))
    ob.data.materials.append(mat)
    return ob


def liquids(spec, cam, log):
    mats = _mats()
    for i, lq in enumerate(spec or []):
        kind, f0 = lq.get('kind', 'splash'), int(lq.get('frame', 0)) + 1
        at = Vector(lq.get('at') or (0.35, -0.2, 0.0))
        rnd = random.Random(i + 11)
        if kind in ('splash', 'pour'):
            n = 12 if kind == 'splash' else 16
            for k in range(n):
                ob = _blob(f'DS_drop{i}_{k}', rnd.uniform(0.012, 0.022), mats['mustard'])
                look.apply_ink(ob, cam, mats, outline=True, seed=k * 0.3)
                start = f0 + (0 if kind == 'splash' else k * 2)
                if kind == 'splash':
                    a = rnd.uniform(0, math.tau)
                    v = Vector((math.cos(a) * rnd.uniform(0.4, 0.9), math.sin(a) * rnd.uniform(0.4, 0.9), rnd.uniform(1.2, 2.0)))
                    p0 = at.copy()
                else:
                    v = Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0.0))
                    p0 = at + Vector((0, 0, 0.45))
                life = 20
                for t in range(life + 1):
                    s = t / 24.0
                    p = p0 + v * s + Vector((0, 0, -4.9 * s * s))
                    if p.z < 0:
                        p.z = 0
                    ob.location = p
                    ob.keyframe_insert('location', frame=start + t)
                    sc = 1.0 if t < life - 4 else max(0.0, (life - t) / 4)
                    ob.scale = (sc, sc, sc * (0.4 if p.z == 0 else 1.0))
                    ob.keyframe_insert('scale', frame=start + t)
                _show_from(ob, start)
        # every liquid leaves a puddle that spreads with an ease
        pud = _blob(f'DS_puddle{i}', 0.2, mats['mustard'])
        pud.location = (at.x, at.y, 0.003)
        look.apply_ink(pud, cam, mats, outline=True, seed=i * 0.9)
        start = f0 + (6 if kind != 'puddle' else 0)
        for t, s in ((0, 0.05), (8, 0.8), (16, 1.0)):
            pud.scale = (s * 1.2, s, 0.03)
            pud.keyframe_insert('scale', frame=start + t)
        _show_from(pud, start)
        log(f'powers: {kind} liquid at frame {f0}')


# ---------------------------------------------------------------- fisheye: a barrel lens in the compositor
def fisheye(amount, log):
    sc = bpy.context.scene
    amount = max(0.0, min(1.0, float(amount)))
    if hasattr(sc, 'compositing_node_group'):   # 5.x: a compositor node group
        ng = bpy.data.node_groups.new('DS Fisheye', 'CompositorNodeTree')
        ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new('CompositorNodeRLayers')
        ld = ng.nodes.new('CompositorNodeLensdist')
        out = ng.nodes.new('NodeGroupOutput')
        sc.compositing_node_group = ng
    else:
        sc.use_nodes = True
        ng = sc.node_tree
        ng.nodes.clear()
        rl = ng.nodes.new('CompositorNodeRLayers')
        ld = ng.nodes.new('CompositorNodeLensdist')
        out = ng.nodes.new('CompositorNodeComposite')
    dist = ld.inputs.get('Distortion') or ld.inputs.get('Distort')
    if dist is not None:
        dist.default_value = 0.35 * amount
    else:
        ld.inputs[1].default_value = 0.35 * amount
    for k in ('use_fit', 'use_projector'):
        if hasattr(ld, k):
            setattr(ld, k, k == 'use_fit')
    if 'Fit' in ld.inputs:
        ld.inputs['Fit'].default_value = True
    ng.links.new(rl.outputs['Image'], ld.inputs['Image'])
    ng.links.new(ld.outputs['Image'], out.inputs[0])
    log(f'powers: fisheye {amount:.2f}')


# ---------------------------------------------------------------- 360 video: equirectangular in Cycles
def pano360(cam, log, width=3840):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'   # the RTX card when Blender's preferences have one; Cycles falls back to the CPU
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    cam.data.type = 'PANO'
    if hasattr(cam.data, 'panorama_type'):
        cam.data.panorama_type = 'EQUIRECTANGULAR'
    else:
        cam.data.cycles.panorama_type = 'EQUIRECTANGULAR'
    width = int(width) if width not in (True, 1) else 3840
    sc.render.resolution_x, sc.render.resolution_y = width, width // 2
    # a 360 camera stands level, a short step in front of the character at eye height, looking at them;
    # the viewer turns their head, so the camera itself never tilts or rolls
    cam.animation_data_clear()
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    cam.rotation_mode = 'XYZ'
    cam.location = (0.0, -1.4, 0.45)
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)
    bpy.context.view_layer.update()
    log(f'powers: 360 video, equirectangular {width}x{width // 2}')


def apply(shot, cam, log):
    pw = shot.get('powers') or {}
    steps = [('pano360', lambda: pano360(cam, log, pw['pano360'])), ('doodles', lambda: doodles(pw['doodles'], cam, log)), ('scatter', lambda: scatter(pw['scatter'], cam, log)),
             ('crowd', lambda: crowd(pw['crowd'], cam, log)), ('liquids', lambda: liquids(pw['liquids'], cam, log)),
             ('autoink', lambda: autoink(cam, log)), ('fisheye', lambda: fisheye(pw['fisheye'], log))]
    for key, fn in steps:
        if pw.get(key):
            try:
                fn()
            except Exception as e:
                log(f'powers: {key} skipped: {e}')
