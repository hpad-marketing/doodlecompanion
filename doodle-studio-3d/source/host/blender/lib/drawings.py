"""Scene drawings for Doodle Studio 3D (shot['drawings'], made by app/src/drawings.js).

A scene drawing is an imported SVG (or lines drawn by hand) standing in the 3D world on a
camera-facing plane, so the character can be in front of it or behind it. The screen layer
is not drawn here: the editor lays it over the joined video as PNGs.

  drawings [{id, strokes: [[[x, y], ...]] 0..1 box y down, aspect, rot,
             world: {at: [x, y, z], r: [..], u: [..], h}, frame, build, until,
             noise 0..1, boil frames, colour ink|mustard}]

Each stroke is an ink curve one Bunny line wide (screen-true where it is placed). It draws on
stroke after stroke over `build` frames and boils like a hand-drawn line: three wobbled shape
keys, one every `boil` frames, cycling. Brand colours only, no fills.
"""
import math
import random

import bpy
from mathutils import Vector

import compat
import powers

BOIL_PX_1920 = 4.0
WAVE_PX_1920 = 140.0


def _local(d):
    a = math.radians(float(d.get('rot', 0) or 0))
    c, s, k = math.cos(a), math.sin(a), float(d.get('aspect', 1) or 1)
    out = []
    for st in d.get('strokes') or []:
        pts = []
        for x, y in st:
            lx, ly = (x - 0.5) * k, 0.5 - y
            pts.append((lx * c - ly * s, lx * s + ly * c))
        if len(pts) > 1:
            out.append(_densify(pts))
    return out


def _densify(pts, step=0.01):
    """In-between points on long straight runs: the tube keeps its width at sharp corners
    and the boil bends straight lines, as in the editor."""
    out = [pts[0]]
    for j in range(1, len(pts)):
        (ax, ay), (bx, by) = pts[j - 1], pts[j]
        n = min(200, int(math.hypot(bx - ax, by - ay) / step))
        for k in range(1, n + 1):
            out.append((ax + (bx - ax) * k / (n + 1), ay + (by - ay) * k / (n + 1)))
        out.append(pts[j])
    return out


def _length(pts):
    return sum((Vector(pts[i]) - Vector(pts[i - 1])).length for i in range(1, len(pts)))


def _constant(idb):
    for fc in compat.fcurves(idb):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'


def _wobble(pts, amp, wave, rnd):
    """Smooth low-frequency wobble along the line (same idea as the editor's boil)."""
    f1, f2 = 3 + rnd.random() * 3, 2 + rnd.random() * 3
    p1, p2 = rnd.random() * 6.283, rnd.random() * 6.283
    ox, oy = (rnd.random() - 0.5) * 0.6, (rnd.random() - 0.5) * 0.6
    out, acc = [], 0.0
    for j, p in enumerate(pts):
        if j:
            acc += (Vector(p) - Vector(pts[j - 1])).length
        u = acc / max(1e-9, wave)
        out.append((amp * (math.sin(u * f1 + p1) * 0.7 + ox), amp * (math.cos(u * f2 + p2) * 0.7 + oy)))
    return out


def one(i, d, cam, mats, log):
    w = d.get('world') or {}
    at, r, u, h = Vector(w['at']), Vector(w['r']).normalized(), Vector(w['u']).normalized(), float(w['h'])
    f0 = int(d.get('frame', 0)) + 1
    sc = bpy.context.scene
    sc.frame_set(f0)
    wpp = powers._world_per_px(cam, at)
    radius = powers._ink_px() * wpp / 2
    strokes = [[(at + r * (x * h) + u * (y * h)) for x, y in st] for st in _local(d)]
    local = [[(x * h, y * h) for x, y in st] for st in _local(d)]
    lens = [_length([tuple(p) for p in st]) for st in strokes]
    total = sum(lens) or 1.0
    build = max(0, int(d.get('build', 18)))
    until = d.get('until')
    noise = max(0.0, min(1.0, float(d.get('noise', 0.5) or 0)))
    boil = max(1, int(d.get('boil', 2)))
    amp, wave = noise * BOIL_PX_1920 * wpp, WAVE_PX_1920 * wpp
    rnd = random.Random(str(d.get('id', i)))
    mat = mats['mustard'] if d.get('colour') == 'mustard' else mats['ink']
    done = 0.0
    for k, pts in enumerate(strokes):
        name = f'DS_drawing{i}_{k}'
        cu = bpy.data.curves.new(name, 'CURVE')
        cu.dimensions = '3D'
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for j, p in enumerate(pts):
            sp.points[j].co = (p.x, p.y, p.z, 1.0)
        cu.bevel_depth = radius
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        try:
            cu.bevel_factor_mapping_end = 'SPLINE'   # draw on at even speed along the line
        except (AttributeError, TypeError):
            pass
        ob = powers._link(bpy.data.objects.new(name, cu))
        ob.data.materials.append(mat)
        # draw on: this stroke's share of the build, in order
        a = f0 + build * done / total
        b = f0 + build * (done + lens[k]) / total
        done += lens[k]
        start = int(math.floor(a))
        if build > 0:
            cu.bevel_factor_end = 0.0
            cu.keyframe_insert('bevel_factor_end', frame=a)
            cu.bevel_factor_end = 1.0
            cu.keyframe_insert('bevel_factor_end', frame=max(a + 0.01, b))
            for fc in compat.fcurves(cu):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        # hidden before it starts and after `until`
        ob.hide_render = start > 1
        ob.keyframe_insert('hide_render', frame=1)
        if start > 1:
            ob.hide_render = False
            ob.keyframe_insert('hide_render', frame=start)
        if until is not None:
            ob.hide_render = True
            ob.keyframe_insert('hide_render', frame=int(until) + 1)
        _constant(ob)
        # boil: three wobbled copies of the line, one every `boil` frames, round and round
        if amp > 0:
            ob.shape_key_add(name='Basis', from_mix=False)
            keys = []
            for v in range(3):
                kb = ob.shape_key_add(name=f'boil{v}', from_mix=False)
                off = _wobble(local[k], amp, wave, rnd)
                for j, (ox, oy) in enumerate(off):
                    q = pts[j] + r * ox + u * oy
                    kb.data[j].co = q
                keys.append(kb)
            for v, kb in enumerate(keys):
                for c in range(4):   # the 4th key closes the loop, so the cycle is 3 boils long
                    kb.value = 1.0 if c % 3 == v else 0.0
                    kb.keyframe_insert('value', frame=f0 + c * boil)
            for fc in compat.fcurves(ob.data.shape_keys):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
                if not any(m.type == 'CYCLES' for m in fc.modifiers):
                    fc.modifiers.new('CYCLES')
    return len(strokes)


def apply(shot, cam, log):
    spec = shot.get('drawings') or []
    if not spec:
        return
    mats = powers._mats()
    n = 0
    for i, d in enumerate(spec):
        try:
            n += one(i, d, cam, mats, log)
        except Exception as e:   # one bad drawing never stops the render
            log(f'drawings: drawing {i} skipped: {e}')
    bpy.context.scene.frame_set(1)
    log(f'drawings: {len(spec)} drawings, {n} strokes')
