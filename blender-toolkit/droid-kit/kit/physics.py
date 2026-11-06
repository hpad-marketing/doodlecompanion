"""Shared physics model for droids (used by tools/physics_audit.py and tools/balance_fix.py).
Mass per part from its shape and material (settings 'physics' can override):
  painted panels and armour = 4 mm steel shells (solid if thinner); frames, pins, joint hardware and bare metal = steel,
  solid unless thicker than 12 mm walls; polymer parts 6 mm shells; lenses/LEDs/glass solid 2500 kg/m3;
  plus internal equipment (batteries, computer...) as point masses in physics.internal [{name, bone, kg, at}].
Support = sole points of the foot parts within physics.sole_tolerance (4 mm) of the floor."""
import bpy, bmesh, math, re
from mathutils import Vector, Matrix
import kit

G = 9.81
STEEL = 7850
DENS = {'polymer': 1150, 'lens': 2500, 'led': 2500, 'glass': 2500}


def part_mass(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(Matrix.Diagonal(o.matrix_world.to_scale()).to_4x4())
    area = sum(f.calc_area() for f in bm.faces)
    closed = all(e.is_manifold for e in bm.edges) and len(bm.faces) > 3
    vol = abs(bm.calc_volume(signed=True)) if closed else 0.0
    if not closed:
        d = o.dimensions; vol = d.x * d.y * d.z * 0.5
    cen = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts)); bm.free()
    mat = (o.active_material.name.lower() if o.active_material else '')
    rho = next((v for k, v in DENS.items() if k in mat), STEEL)
    wall = 0.006 if rho < 2000 else (0.004 if re.search(r'metal_(?!bare|pin)|tan|teal|navy|yellow|sage|olive|grey', mat) else 0.012)
    return rho * min(vol, area * wall), cen


class Body:
    """every part with a mass, posed with the rig: com(), support(), hull(), margin()"""
    def __init__(self, rig):
        self.rig = rig; self.pbs = rig.pose.bones
        PH = kit.get('physics', {}) or {}
        self.Z0 = kit.get('floor_z', 0.0); self.tol = PH.get('sole_tolerance', 0.004)
        self.parts = []
        for o in bpy.data.objects:
            if o.type != 'MESH' or 'rig_bone' not in o or o.hide_render or o.name.startswith(('WGT', 'dust', 'Dust')): continue
            m, cen = part_mass(o); S = o.matrix_world.to_scale()
            self.parts.append(dict(o=o, bone=o['rig_bone'], m=m, local=Vector((cen.x / S.x, cen.y / S.y, cen.z / S.z)), name=o.name))
        self.internal = PH.get('internal', [])
        for it in self.internal:
            b = rig.data.bones[it['bone']]; M = (rig.matrix_world @ b.matrix_local).inverted()
            self.parts.append(dict(o=None, bone=it['bone'], m=it['kg'], rest_inv=M, at=Vector(it['at']), name=it['name']))
        self.total = sum(p['m'] for p in self.parts)
        self.feet = {S: [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and not o.hide_render
                         and re.search(rf'(foot|toe|heel|sole)[^.]*\.{S}$', o.name)] for S in 'LR'}

    def world_points(self):
        out = []
        for p in self.parts:
            if p['o'] is not None: out.append((p, p['o'].matrix_world @ p['local']))
            else: out.append((p, self.rig.matrix_world @ self.pbs[p['bone']].matrix @ p['rest_inv'] @ p['at']))
        return out

    def com(self, W=None):
        W = W or self.world_points()
        return sum((p['m'] * x for p, x in W), Vector()) / self.total

    def support(self):
        """planted sole points per foot"""
        dg = bpy.context.evaluated_depsgraph_get(); out = {}
        for S, objs in self.feet.items():
            pts = []
            for o in objs:
                e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
                pts += [M @ v.co for v in me.vertices if (M @ v.co).z < self.Z0 + self.tol]
                e.to_mesh_clear()
            if pts: out[S] = pts
        return out


def hull(pts):
    P = sorted({(round(p.x, 4), round(p.y, 4)) for p in pts})
    if len(P) < 3: return P
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def margin(h, x, y):
    """signed distance from a point to the support polygon's edge (+ inside)"""
    if len(h) < 3: return -1.0
    d = 1e9
    for i in range(len(h)):
        (x1, y1), (x2, y2) = h[i], h[(i + 1) % len(h)]
        ex, ey = x2 - x1, y2 - y1; L = math.hypot(ex, ey) or 1e-9
        d = min(d, -((x - x1) * ey - (y - y1) * ex) / L)
    return d


def zmp(c, acc, Z0=0.0):
    """where the ground must push so the body doesn't tip: CoM shifted against its acceleration"""
    k = (c.z - Z0) / (G + acc.z)
    return c.x - k * acc.x, c.y - k * acc.y


def reset_pose(rig):
    """rest pose for control bones, so channels a motion doesn't key don't carry over from the last one"""
    for b in rig.pose.bones:
        if not b.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): b.location = (0, 0, 0); b.rotation_euler = (0, 0, 0)
