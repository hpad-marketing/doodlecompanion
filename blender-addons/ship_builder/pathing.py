"""Floor paths that route around furniture.

    g = pathing.Grid.from_scene(scene, radius=0.28)
    pts = g.path((x0, y0), (x1, y1))          -> [Vector, ...] corner points, or [] if no way

The grid is a top-down occupancy map of the set (10 cm cells). Anything that
stands between ankle and head height is an obstacle; low things a droid steps
onto (charge pads, the repair dais, the viewing step, floor paint) are not.
Obstacles are grown by the droid's radius so a path keeps its body clear.
Door leaves never block: walk mode opens doors as a droid reaches them.

Used by the walk test, and by the blocking map to route droid marks.
"""
import heapq
import math
import bpy
from mathutils import Vector

CELL = 0.1
STEP_MAX = 0.15     # tops at or below this are stepped onto, not walked around
HEAD = 1.6          # things wholly above this are overhead


def _is_door_leaf(ob):
    p = ob
    while p is not None:
        if p.get("sb_door"):
            return True
        p = p.parent
    return False


class Grid:
    def __init__(self, lo, hi, cell=CELL):
        self.lo, self.cell = Vector((lo[0], lo[1])), cell
        self.nx = int(math.ceil((hi[0] - lo[0]) / cell)) + 1
        self.ny = int(math.ceil((hi[1] - lo[1]) / cell)) + 1
        self.block = bytearray(self.nx * self.ny)

    @classmethod
    def from_scene(cls, scene=None, radius=0.28, skip=(), step_max=STEP_MAX, head=HEAD):
        """step_max/head: the band that blocks. Standing marks use a lower step (stand on flat floor)
        and a taller head (the tallest droid)."""
        scene = scene or bpy.context.scene
        boxes = []
        for ob in scene.objects:
            if ob.type not in {"MESH", "CURVE"} or ob.hide_render or ob.get("sb_droid") or ob.name in skip:
                continue
            if ob.get("sb_fourth_wall") or ob.get("sb_haze") or ob.get("sb_decal") or ob.name.startswith(("Deck", "SB Zero-G", "Planet")):
                continue
            if _is_door_leaf(ob):
                continue
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            zs = [v.z for v in bb]
            if max(zs) <= step_max or min(zs) >= head:
                continue
            xs, ys = [v.x for v in bb], [v.y for v in bb]
            if max(xs) - min(xs) > 30 or max(ys) - min(ys) > 30:  # sky domes, planets
                continue
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        if not boxes:
            return cls((-1, -1), (1, 1))
        lo = (min(b[0] for b in boxes) - 1, min(b[1] for b in boxes) - 1)
        hi = (max(b[2] for b in boxes) + 1, max(b[3] for b in boxes) + 1)
        g = cls(lo, hi)
        for x0, y0, x1, y1 in boxes:
            g.fill(x0 - radius, y0 - radius, x1 + radius, y1 + radius)
        return g

    def ij(self, p):
        return int(round((p[0] - self.lo.x) / self.cell)), int(round((p[1] - self.lo.y) / self.cell))

    def xy(self, i, j):
        return Vector((self.lo.x + i * self.cell, self.lo.y + j * self.cell, 0.0))

    def inside(self, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny

    def blocked(self, i, j):
        return not self.inside(i, j) or self.block[j * self.nx + i]

    def fill(self, x0, y0, x1, y1):
        i0, j0 = self.ij((x0, y0))
        i1, j1 = self.ij((x1, y1))
        for j in range(max(0, j0), min(self.ny, j1 + 1)):
            row = j * self.nx
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                self.block[row + i] = 1

    def nearest_free(self, p, reach=12):
        i, j = self.ij(p)
        if not self.blocked(i, j):
            return i, j
        best = None
        for r in range(1, reach + 1):
            for di in range(-r, r + 1):
                for dj in (-r, r) if abs(di) != r else range(-r, r + 1):
                    if not self.blocked(i + di, j + dj):
                        d = di * di + dj * dj
                        if best is None or d < best[0]:
                            best = (d, i + di, j + dj)
            if best:
                return best[1], best[2]
        return None

    def _clear(self, a, b):
        """Straight segment between two cells crosses no blocked cell."""
        (i0, j0), (i1, j1) = a, b
        n = max(abs(i1 - i0), abs(j1 - j0)) * 2 + 1
        for k in range(n + 1):
            t = k / n
            if self.blocked(int(round(i0 + (i1 - i0) * t)), int(round(j0 + (j1 - j0) * t))):
                return False
        return True

    def path(self, a, b):
        s, g = self.nearest_free(a), self.nearest_free(b)
        if s is None or g is None:
            return []
        if self._clear(s, g):
            return [self.xy(*g)]
        nbr = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        openq = [(0.0, 0.0, s)]
        came, cost = {s: None}, {s: 0.0}
        while openq:
            _, c, cur = heapq.heappop(openq)
            if cur == g:
                break
            if c > cost.get(cur, 1e18):
                continue
            for di, dj, w in nbr:
                nb = (cur[0] + di, cur[1] + dj)
                if self.blocked(*nb):
                    continue
                if di and dj and (self.blocked(cur[0] + di, cur[1]) or self.blocked(cur[0], cur[1] + dj)):
                    continue
                nc = c + w
                if nc < cost.get(nb, 1e18):
                    cost[nb] = nc
                    came[nb] = cur
                    h = math.hypot(nb[0] - g[0], nb[1] - g[1])
                    heapq.heappush(openq, (nc + h, nc, nb))
        if g not in came:
            return []
        cells = [g]
        while came[cells[-1]] is not None:
            cells.append(came[cells[-1]])
        cells.reverse()
        # string-pull: keep only the corners a straight walk needs
        out, k = [], 0
        while k < len(cells) - 1:
            m = len(cells) - 1
            while m > k + 1 and not self._clear(cells[k], cells[m]):
                m -= 1
            out.append(cells[m])
            k = m
        return [self.xy(*c) for c in out]
