"""Tiny modelling kit for doodle scenery: primitives -> one mesh, one group per part.

Coordinates in metres, z up, the front of a piece faces -y (toward the camera).
Rounded shapes use bevels whose steps stay under the crease angle, so they read
as soft forms with just a silhouette; hard edges (90°) get a line.
"""
import math

import bpy
import bmesh
from mathutils import Matrix, Vector


class Piece:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.grp = self.bm.faces.layers.int.new('dsl_group')
        self.g = 0
        self.mat_index = {'m': 0, 'i': 1}
        self.meta = {}  # extras the builder stores on the object (text spot, screen face, place mode)

    def __setitem__(self, k, v):
        self.meta[k] = v

    def __getitem__(self, k):
        return self.meta[k]

    def _add(self, bm2, mat='m', M=None):
        if M is not None:
            bmesh.ops.transform(bm2, matrix=M, verts=bm2.verts)
        me = bpy.data.meshes.new('tmp')
        bm2.to_mesh(me)
        bm2.free()
        n0 = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.bm.faces.ensure_lookup_table()
        grp = self.bm.faces.layers.int.get('dsl_group')
        for f in self.bm.faces[n0:]:
            f[grp] = self.g
            f.material_index = self.mat_index[mat]
        self.g += 1
        return self

    # ---------------------------------------------------------- primitives
    def box(self, w, d, h, x=0, y=0, z=0, mat='m', bevel=0.0, seg=4, rz=0.0, rx=0.0, ry=0.0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(w, d, h), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, w / 2.05, d / 2.05, h / 2.05),
                            segments=seg, affect='EDGES', profile=0.5)
        return self._add(bm, mat, self._M(x, y, z, rx, ry, rz))

    def cyl(self, r, h, x=0, y=0, z=0, mat='m', r2=None, seg=28, rx=0.0, ry=0.0, rz=0.0, caps=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r,
                              radius2=r if r2 is None else r2, depth=h)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
        return self._add(bm, mat, self._M(x, y, z, rx, ry, rz))

    def sphere(self, r, x=0, y=0, z=0, mat='m', sx=1, sy=1, sz=1, seg=24):
        bm = bmesh.new()
        # icospheres: no poles, so the silhouette and the outline stay even all round
        bmesh.ops.create_icosphere(bm, subdivisions=3 if seg >= 16 else 2, radius=r)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
        return self._add(bm, mat, Matrix.Translation((x, y, z)))

    def torus(self, R, r, x=0, y=0, z=0, mat='m', rx=0.0, ry=0.0, rz=0.0, seg=32, seg2=10):
        bm = bmesh.new()
        verts = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring = []
            for j in range(seg2):
                b = 2 * math.pi * j / seg2
                ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
            verts.append(ring)
        for i in range(seg):
            for j in range(seg2):
                bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % seg2], verts[i][(j + 1) % seg2]))
        return self._add(bm, mat, self._M(x, y, z, rx, ry, rz))

    def tube(self, path, r, mat='m', seg=10):
        """Round rod through 3D points (lamp arms, cart frames, handles)."""
        bm = bmesh.new()
        rings = []
        pts = [Vector(p) for p in path]
        for i, p in enumerate(pts):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
            u = d.cross(up).normalized()
            v = d.cross(u).normalized()
            rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / seg) + v * math.sin(2 * math.pi * k / seg)) * r)
                          for k in range(seg)])
        for a, b in zip(rings, rings[1:]):
            for k in range(seg):
                bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        return self._add(bm, mat)

    def prism(self, outline, depth, y=0, mat='m', x=0, z=0, rz=0.0):
        """Extrude a 2D outline drawn in the x-z plane (front view) by `depth` along y."""
        bm = bmesh.new()
        front = [bm.verts.new((px, -depth / 2, pz)) for px, pz in outline]
        back = [bm.verts.new((px, depth / 2, pz)) for px, pz in outline]
        bm.faces.new(front)
        bm.faces.new(list(reversed(back)))
        n = len(outline)
        for i in range(n):
            bm.faces.new((front[i], back[i], back[(i + 1) % n], front[(i + 1) % n]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._add(bm, mat, self._M(x, y, z, 0, 0, rz))

    def lathe(self, profile, x=0, y=0, z=0, mat='m', seg=32):
        """Spin a (r, z) profile around the vertical axis."""
        bm = bmesh.new()
        rings = []
        for r, pz in profile:
            if r < 1e-6:
                rings.append([bm.verts.new((0, 0, pz))])
            else:
                rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), pz))
                              for k in range(seg)])
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                for k in range(seg):
                    bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
            elif len(b) == 1:
                for k in range(seg):
                    bm.faces.new((a[(k + 1) % seg], a[k], b[0]))
            else:
                for k in range(seg):
                    bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._add(bm, mat, Matrix.Translation((x, y, z)))

    @staticmethod
    def _M(x, y, z, rx, ry, rz):
        return Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rz), 4, 'Z') @ \
            Matrix.Rotation(math.radians(ry), 4, 'Y') @ Matrix.Rotation(math.radians(rx), 4, 'X')

    # ---------------------------------------------------------- result
    def build(self, mats, height=None, base='bottom'):
        bm = self.bm
        if height:
            zs = [v.co.z for v in bm.verts]
            lo, hi = min(zs), max(zs)
            s = height / max(hi - lo, 1e-6)
            bmesh.ops.scale(bm, vec=(s, s, s), verts=bm.verts)
        else:
            s = 1.0
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mats['DSL_mustard'])
        me.materials.append(mats['DS_ink'])
        ob = bpy.data.objects.new(self.name, me)
        ob['dsl_scale'] = s
        return ob
