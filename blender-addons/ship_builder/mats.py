"""Procedural, texture-free materials for the ship.

Every material is built from nodes only, so the add-on needs no image files.
Realism comes from: rounded edges (Bevel node), edge wear (Pointiness + noise),
cavity grime (AO), roughness breakup, scratches and fingerprints.
All materials are cached by name; calling a builder twice returns the same one.
"""
import os
import bpy

WEAR = {"amount": 0.5, "grime": 0.5}
# Folder of Poly Haven (CC0) scans: <dir>/<asset>/<asset>_diff_2k.jpg etc.
# When present, real scanned detail is layered over the procedural looks.
SCANS = {"dir": os.environ.get("SB_SCANS", "")}


def scan_path(asset, kind):
    d = SCANS["dir"]
    if not d:
        return None
    p = os.path.join(d, asset, f"{asset}_{kind}_2k.jpg")
    return p if os.path.exists(p) else None


def _img(g, path, vec, colour=True, blend=0.25):
    im = bpy.data.images.get(os.path.basename(path)) or bpy.data.images.load(path, check_existing=True)
    if not colour:
        im.colorspace_settings.name = "Non-Color"
    t = g.node("ShaderNodeTexImage", _projection="BOX", _interpolation="Cubic")
    t.projection_blend = blend
    t.image = im
    g.link(vec, t.inputs["Vector"])
    return t


def scan(g, asset, scale=1.0):
    """Returns (diffuse, roughness, normal) sockets for a scanned asset, or None."""
    if not scan_path(asset, "diff"):
        return None
    tc = g.node("ShaderNodeTexCoord")
    mp = g.node("ShaderNodeMapping")
    g.link(tc.outputs["Object"], mp.inputs["Vector"])
    mp.inputs["Scale"].default_value = (scale,) * 3
    v = mp.outputs[0]
    d = _img(g, scan_path(asset, "diff"), v)
    r = _img(g, scan_path(asset, "rough"), v, False) if scan_path(asset, "rough") else None
    nrm = None
    if scan_path(asset, "nor_gl"):
        n = _img(g, scan_path(asset, "nor_gl"), v, False)
        nm = g.node("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.8
        g.link(n.outputs["Color"], nm.inputs["Color"])
        nrm = nm.outputs[0]
    return d.outputs["Color"], (r.outputs["Color"] if r else None), nrm


def _get(name):
    m = bpy.data.materials.get(name)
    if m is not None and m.get("sb_built"):
        return m, False
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m["sb_built"] = 1
    m.node_tree.nodes.clear()
    return m, True


class G:
    """Tiny node-graph helper."""

    def __init__(self, mat):
        self.t = mat.node_tree
        self.n = self.t.nodes
        self.x = -1400

    def node(self, kind, **inputs):
        nd = self.n.new(kind)
        nd.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(nd, k[1:], v)
            else:
                self.set(nd, k, v)
        return nd

    def set(self, nd, key, v):
        sock = nd.inputs[key]
        if hasattr(v, "bl_idname") or isinstance(v, bpy.types.NodeSocket):
            out = v if isinstance(v, bpy.types.NodeSocket) else v.outputs[0]
            self.t.links.new(out, sock)
        else:
            sock.default_value = v

    def link(self, a, b):
        self.t.links.new(a, b)

    def math(self, op, a, b=0.0, clamp=False):
        nd = self.node("ShaderNodeMath", _operation=op, _use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.link(v if isinstance(v, bpy.types.NodeSocket) else v.outputs[0], nd.inputs[i])
        return nd.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        nd = self.node("ShaderNodeMix", _data_type="RGBA", _blend_type=blend)
        self._in(nd.inputs[0], fac)
        self._in(nd.inputs[6], a)
        self._in(nd.inputs[7], b)
        return nd.outputs[2]

    def mixf(self, fac, a, b):
        nd = self.node("ShaderNodeMix", _data_type="FLOAT")
        self._in(nd.inputs[0], fac)
        self._in(nd.inputs[2], a)
        self._in(nd.inputs[3], b)
        return nd.outputs[0]

    def _in(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif hasattr(v, "outputs"):
            self.link(v.outputs[0], sock)
        else:
            sock.default_value = v

    def ramp(self, v, a, b):
        nd = self.node("ShaderNodeMapRange")
        self._in(nd.inputs[0], v)
        nd.inputs[1].default_value = a
        nd.inputs[2].default_value = b
        nd.clamp = True
        return nd.outputs[0]

    def noise(self, scale, detail=6.0, rough=0.6, vec=None, dim="3D"):
        nd = self.node("ShaderNodeTexNoise", _noise_dimensions=dim)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        if vec is not None:
            self._in(nd.inputs["Vector"], vec)
        return nd

    def coord(self, scale=(1, 1, 1)):
        tc = self.node("ShaderNodeTexCoord")
        mp = self.node("ShaderNodeMapping")
        self.link(tc.outputs["Object"], mp.inputs["Vector"])
        mp.inputs["Scale"].default_value = scale
        return mp.outputs[0]

    def out(self, shader):
        o = self.node("ShaderNodeOutputMaterial")
        self._in(o.inputs["Surface"], shader)
        return o


def _bevel_normal(g, radius=0.004, bump=None):
    bev = g.node("ShaderNodeBevel", _samples=8)
    bev.inputs["Radius"].default_value = radius
    if bump is not None:
        g.link(bump, bev.inputs["Normal"])
    return bev.outputs[0]


def _bump(g, height, strength=0.2, dist=0.002, normal=None):
    b = g.node("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    g._in(b.inputs["Height"], height)
    if normal is not None:
        g._in(b.inputs["Normal"], normal)
    return b.outputs[0]


def _wear_masks(g, scale=1.0):
    """Returns (edge_wear 0-1, cavity_grime 0-1, smudge 0-1)."""
    geo = g.node("ShaderNodeNewGeometry")
    edge = g.ramp(geo.outputs["Pointiness"], 0.52, 0.6)
    n = g.noise(14 * scale, 8, 0.7)
    edge = g.math("MULTIPLY", edge, g.ramp(n.outputs[0], 0.45 - 0.2 * WEAR["amount"], 0.62))
    ao = g.node("ShaderNodeAmbientOcclusion", _samples=8, _only_local=True)
    ao.inputs["Distance"].default_value = 0.08
    grime = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, ao.outputs["AO"], clamp=True), 1.6 * WEAR["grime"], clamp=True)
    sm = g.noise(2.5 * scale, 4, 0.5)
    smudge = g.ramp(sm.outputs[0], 0.45, 0.75)
    return edge, grime, smudge


def painted_metal(name, color, rough=0.42, bare=(0.55, 0.55, 0.56, 1), scale=1.0):
    """Painted steel with chipped edges, cavity grime, scratches and smudges."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    edge, grime, smudge = _wear_masks(g, scale)
    # fine scratches: stretched noise, thresholded
    sc_vec = g.coord((1, 40, 1))
    scr = g.noise(60 * scale, 2, 0.5, vec=sc_vec)
    scratch = g.ramp(scr.outputs[0], 0.68, 0.72)
    col = g.mix(smudge, color, tuple(c * 0.93 for c in color[:3]) + (1,))
    col = g.mix(g.math("MULTIPLY", scratch, 0.25), col, (0.42, 0.42, 0.42, 1))
    col = g.mix(edge, col, bare)
    col = g.mix(grime, col, (0.05, 0.045, 0.04, 1), "MULTIPLY")
    r = g.mixf(smudge, rough, rough + 0.15)
    r = g.mixf(edge, r, 0.28)
    metal = g.mixf(edge, 0.0, 1.0)
    sc = scan(g, "blue_metal_plate", 0.55 * scale)
    if sc:
        bw = g.node("ShaderNodeRGBToBW")
        g.link(sc[0], bw.inputs[0])
        lum = g.math("MULTIPLY", bw.outputs[0], 3.2)
        col = g.mix(0.55, col, g.mix(1.0, col, lum, "MULTIPLY"))
        if sc[1] is not None:
            r = g.math("ADD", g.math("MULTIPLY", r, 0.6), g.math("MULTIPLY", sc[1], 0.45))
        nrm = _bevel_normal(g, 0.004, sc[2])
    else:
        pn = g.noise(220 * scale, 3, 0.5)
        nrm = _bevel_normal(g, 0.004, _bump(g, pn.outputs[0], 0.015, 0.0005))
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    g._in(bsdf.inputs["Roughness"], r)
    g._in(bsdf.inputs["Metallic"], metal)
    g._in(bsdf.inputs["Normal"], nrm)
    bsdf.inputs["Coat Weight"].default_value = 0.08
    g.out(bsdf)
    return m


def brushed_steel(name="SB Brushed Steel", tint=(0.62, 0.62, 0.63, 1), rough=0.3):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    edge, grime, smudge = _wear_masks(g)
    v = g.coord((1, 1, 60))
    br = g.noise(90, 3, 0.6, vec=v)
    r = g.math("ADD", rough, g.math("MULTIPLY", br.outputs[0], 0.15))
    r = g.mixf(smudge, r, rough + 0.2)
    col = g.mix(grime, tint, (0.08, 0.08, 0.08, 1), "MULTIPLY")
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    bsdf.inputs["Metallic"].default_value = 1.0
    g._in(bsdf.inputs["Roughness"], r)
    bsdf.inputs["Anisotropic"].default_value = 0.5
    g._in(bsdf.inputs["Normal"], _bevel_normal(g, 0.003))
    g.out(bsdf)
    return m


def diamond_plate(name="SB Diamond Plate"):
    """Scanned rusty diamond plate (engine room, cargo, walkways); procedural fallback."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    sc = scan(g, "metal_plate", 0.5)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    if sc:
        g._in(bsdf.inputs["Base Color"], sc[0])
        if sc[1] is not None:
            g._in(bsdf.inputs["Roughness"], sc[1])
        g._in(bsdf.inputs["Normal"], sc[2])
        bsdf.inputs["Metallic"].default_value = 0.7
    else:
        bsdf.inputs["Base Color"].default_value = (0.2, 0.18, 0.15, 1)
        bsdf.inputs["Metallic"].default_value = 0.9
        bsdf.inputs["Roughness"].default_value = 0.5
    g.out(bsdf)
    return m


def deck_plate(name="SB Deck Plate", color=(0.075, 0.078, 0.08, 1), tile=1.0):
    """Floor: 1 m metal deck panels with dirty seams, scuffs and tread wear."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    v = g.coord((1 / tile, 1 / tile, 1 / tile))
    br = g.node("ShaderNodeTexBrick", _offset=0.0)
    g.link(v, br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.006
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 0.5
    seam = g.math("SUBTRACT", 1.0, br.outputs["Fac"])
    # anti-slip studs
    vor = g.node("ShaderNodeTexVoronoi")
    g.link(v, vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = 26
    vor.inputs["Randomness"].default_value = 0.0
    stud = g.ramp(vor.outputs["Distance"], 0.22, 0.16)
    scuff = g.noise(1.4, 8, 0.65, vec=v)
    worn = g.ramp(scuff.outputs[0], 0.5, 0.7)
    dirt = g.noise(5, 10, 0.7, vec=v)
    col = g.mix(g.ramp(dirt.outputs[0], 0.4, 0.8), color, (0.11, 0.1, 0.09, 1))
    col = g.mix(g.math("MULTIPLY", worn, stud), col, (0.4, 0.4, 0.41, 1))
    col = g.mix(seam, col, (0.02, 0.02, 0.02, 1))
    rough = g.mixf(worn, 0.55, 0.32)
    h = g.math("SUBTRACT", g.math("MULTIPLY", stud, 0.6), seam)
    nrm = _bump(g, h, 0.35, 0.003)
    sc = scan(g, "rubber_tiles", 0.5 / tile)
    if sc:
        col = g.mix(g.ramp(dirt.outputs[0], 0.45, 0.85), sc[0], (0.06, 0.055, 0.05, 1))
        col = g.mix(g.math("MULTIPLY", worn, 0.5), col, (0.16, 0.16, 0.17, 1))
        rough = g.math("ADD", g.math("MULTIPLY", sc[1], 0.8), g.math("MULTIPLY", worn, -0.15)) if sc[1] is not None else rough
        nrm = sc[2]
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    bsdf.inputs["Metallic"].default_value = 0.0 if sc else 0.6
    g._in(bsdf.inputs["Roughness"], rough)
    g._in(bsdf.inputs["Normal"], nrm)
    g.out(bsdf)
    return m


def rubber(name="SB Rubber", color=(0.025, 0.025, 0.025, 1), rough=0.75):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    _, grime, smudge = _wear_masks(g)
    col = g.mix(smudge, color, (0.05, 0.048, 0.045, 1))
    n = g.noise(400, 2, 0.5)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    bsdf.inputs["Roughness"].default_value = rough
    g._in(bsdf.inputs["Normal"], _bevel_normal(g, 0.003, _bump(g, n.outputs[0], 0.05, 0.0003)))
    g.out(bsdf)
    return m


def plastic(name, color, rough=0.38):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    edge, grime, smudge = _wear_masks(g)
    col = g.mix(grime, color, (0.1, 0.1, 0.1, 1), "MULTIPLY")
    col = g.mix(g.math("MULTIPLY", edge, 0.5), col, tuple(min(1, c * 1.25) for c in color[:3]) + (1,))
    r = g.mixf(smudge, rough, rough + 0.12)
    n = g.noise(300, 2, 0.5)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    g._in(bsdf.inputs["Roughness"], r)
    g._in(bsdf.inputs["Normal"], _bevel_normal(g, 0.003, _bump(g, n.outputs[0], 0.03, 0.0003)))
    g.out(bsdf)
    return m


def fabric(name, color, sheen=0.6):
    """Woven upholstery: crossed waves for the weave, soft sheen, wear on high points."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    v = g.coord((1, 1, 1))
    w1 = g.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X")
    g.link(v, w1.inputs["Vector"])
    w1.inputs["Scale"].default_value = 180
    w2 = g.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="Y")
    g.link(v, w2.inputs["Vector"])
    w2.inputs["Scale"].default_value = 180
    weave = g.math("MULTIPLY", w1.outputs["Fac"], w2.outputs["Fac"])
    lump = g.noise(3, 4, 0.5, vec=v)
    col = g.mix(g.ramp(lump.outputs[0], 0.35, 0.7), tuple(c * 0.8 for c in color[:3]) + (1,), color)
    edge, grime, smudge = _wear_masks(g)
    col = g.mix(grime, col, (0.2, 0.2, 0.2, 1), "MULTIPLY")
    col = g.mix(g.math("MULTIPLY", edge, 0.6), col, tuple(min(1, c * 1.35) for c in color[:3]) + (1,))
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.4
    g._in(bsdf.inputs["Normal"], _bump(g, weave, 0.35, 0.0006))
    g.out(bsdf)
    return m


def glass(name="SB Glass", tint=(0.9, 0.95, 1.0, 1), rough=0.02):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    sm = g.noise(3, 4, 0.5)
    r = g.mixf(g.ramp(sm.outputs[0], 0.55, 0.75), rough, rough + 0.08)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = tint
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    g._in(bsdf.inputs["Roughness"], r)
    bsdf.inputs["IOR"].default_value = 1.5
    g.out(bsdf)
    return m


def emissive(name, color, strength=8.0):
    """Light panel: emission plus a slightly frosted diffuser look."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1)
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Emission Color"].default_value = color
    bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.name = "SB_Emit"
    g.out(bsdf)
    m["sb_emit"] = 1
    m["sb_color"] = list(color)
    m["sb_strength"] = strength
    return m


def screen(name, color=(0.25, 0.8, 0.9, 1), strength=3.0, kind="ui"):
    """Display glass with a procedural UI: grid, bars, scanlines and pixel mask."""
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    tc = g.node("ShaderNodeTexCoord")
    uv = tc.outputs["UV"]
    # UI: brick cells as widgets, wave as scanlines
    br = g.node("ShaderNodeTexBrick")
    g.link(uv, br.inputs["Vector"])
    br.inputs["Scale"].default_value = 6 if kind == "ui" else 2
    br.inputs["Mortar Size"].default_value = 0.03
    br.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1)
    br.inputs["Color2"].default_value = (0.35, 0.35, 0.35, 1)
    sc = g.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="Y")
    g.link(uv, sc.inputs["Vector"])
    sc.inputs["Scale"].default_value = 220
    lines = g.ramp(sc.outputs["Fac"], 0.0, 0.6)
    bars = g.noise(18, 0, 0.0, vec=uv)
    pattern = g.math("MULTIPLY", br.outputs["Color"], g.ramp(bars.outputs[0], 0.3, 0.6))
    pattern = g.math("ADD", pattern, g.math("MULTIPLY", g.math("SUBTRACT", 1, br.outputs["Fac"]), 1.5))
    lum = g.math("MULTIPLY", pattern, g.mixf(lines, 0.75, 1.0))
    em = g.math("MULTIPLY", lum, strength)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.01, 0.012, 0.015, 1)
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    bsdf.inputs["Emission Color"].default_value = color
    g._in(bsdf.inputs["Emission Strength"], em)
    bsdf.name = "SB_Emit"
    g.out(bsdf)
    m["sb_emit"] = 1
    m["sb_color"] = list(color)
    m["sb_strength"] = strength
    return m


def hazard(name="SB Hazard", a=(0.75, 0.52, 0.05, 1), b=(0.02, 0.02, 0.02, 1)):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    v = g.coord((1, 1, 1))
    wv = g.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="DIAGONAL")
    g.link(v, wv.inputs["Vector"])
    wv.inputs["Scale"].default_value = 3.0
    st = g.ramp(wv.outputs["Fac"], 0.49, 0.51)
    col = g.mix(st, a, b)
    edge, grime, smudge = _wear_masks(g)
    wear = g.noise(9, 10, 0.7, vec=v)
    chips = g.ramp(wear.outputs[0], 0.62, 0.66)
    col = g.mix(chips, col, (0.3, 0.3, 0.3, 1))
    col = g.mix(grime, col, (0.05, 0.05, 0.05, 1), "MULTIPLY")
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    g._in(bsdf.inputs["Base Color"], col)
    g._in(bsdf.inputs["Roughness"], g.mixf(chips, 0.5, 0.35))
    g._in(bsdf.inputs["Normal"], _bevel_normal(g, 0.003))
    g.out(bsdf)
    return m


def liquid(name, color, rough=0.05):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.2
    bsdf.inputs["Coat Weight"].default_value = 1.0
    g.out(bsdf)
    return m


def haze(name="SB Haze", density=0.012, color=(0.8, 0.85, 0.9, 1)):
    m, new = _get(name)
    if not new:
        return m
    g = G(m)
    n = g.noise(1.2, 4, 0.6)
    d = g.math("MULTIPLY", g.ramp(n.outputs[0], 0.3, 0.8), density * 2)
    vol = g.node("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = color
    g._in(vol.inputs["Density"], d)
    vol.inputs["Anisotropy"].default_value = 0.4
    o = g.node("ShaderNodeOutputMaterial")
    g.link(vol.outputs[0], o.inputs["Volume"])
    m["sb_haze"] = density
    return m


def palette():
    """Default ship palette: worn graphite, muted teal, oxide orange, cream."""
    return {
        "hull": painted_metal("SB Paint Graphite", (0.045, 0.047, 0.05, 1), 0.42),
        "panel": painted_metal("SB Paint Slate", (0.085, 0.11, 0.115, 1), 0.38),
        "accent": painted_metal("SB Paint Teal", (0.08, 0.2, 0.21, 1), 0.38),
        "warm": painted_metal("SB Paint Oxide", (0.45, 0.16, 0.06, 1), 0.42),
        "cream": painted_metal("SB Paint Cream", (0.62, 0.57, 0.46, 1), 0.4),
        "steel": brushed_steel(),
        "dark_steel": brushed_steel("SB Dark Steel", (0.25, 0.25, 0.26, 1), 0.35),
        "deck": deck_plate(),
        "rubber": rubber(),
        "plastic": plastic("SB Plastic Black", (0.03, 0.03, 0.032, 1)),
        "plastic_grey": plastic("SB Plastic Grey", (0.3, 0.31, 0.32, 1)),
        "glass": glass(),
        "hazard": hazard(),
    }
