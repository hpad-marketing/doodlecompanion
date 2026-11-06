"""Weathered, procedural materials for the hero ship (no image files needed).

Paint layers, bottom to top:
  per-panel tone drift (face attribute 'panel'; seams are -1 and read as dark lines)
  chipped edges showing bare metal (Bevel-node edge mask x noise)
  cavity grime (AO), downward grime and rust streaks (Z-stretched noise)
  soot near exhausts (object property 'soot' + 'soot_y'), dust on up-facing faces
  fine scratches and dents in the bump
Emissive materials read object custom properties (engine, hyper, lights), which
the rig drives from the ship root, so glows animate with the presets.
Works in Cycles (edge wear needs Cycles' Bevel/AO nodes; EEVEE falls back to clean paint).
"""
import bpy

SLOTS = ["HS Paint", "HS Dark Metal", "HS Glow Teal", "HS Accent", "HS Bay", "HS Glass",
         "HS Rubber", "HS Heat Metal", "HS Engine", "HS Nav Red", "HS Nav Green", "HS Light White",
         "HS Primer"]

PALETTE = {
    "paint": (0.60, 0.565, 0.50),      # warm bone-white hull
    "accent": (0.80, 0.50, 0.13),     # mustard livery (brand #E0A64B, weathered)
    "primer": (0.34, 0.38, 0.35),     # replaced panels in grey-green primer
    "dark": (0.035, 0.036, 0.038),    # ink gunmetal (brand #1F1F1D)
    "teal": (0.10, 0.95, 0.80),
}


class N:
    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
        self.t.nodes.clear()
        self.x = -1800
        self.y = 0

    def __call__(self, kind, **kw):
        n = self.t.nodes.new(kind)
        n.location = (self.x, self.y)
        self.y -= 160
        if self.y < -1200:
            self.y = 0
            self.x += 220
        for k, v in kw.items():
            if k.startswith("_"):
                setattr(n, k[1:], v)
            else:
                self.set(n.inputs[k], v)
        return n

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.t.links.new(v.outputs[0], sock)
        else:
            if hasattr(sock, "default_value"):
                if isinstance(v, (tuple, list)) and len(v) == 3 and len(sock.default_value) == 4:
                    v = tuple(v) + (1.0,)
                sock.default_value = v

    def math(self, op, *args, clamp=False):
        n = self("ShaderNodeMath", _operation=op, _use_clamp=bool(clamp))
        for i, a in enumerate(args):
            self.set(n.inputs[i], a)
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self("ShaderNodeMix", _data_type="RGBA", _blend_type=blend)
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def mixf(self, fac, a, b):
        n = self("ShaderNodeMix", _data_type="FLOAT")
        self.set(n.inputs[0], fac)
        self.set(n.inputs[2], a)
        self.set(n.inputs[3], b)
        return n.outputs[0]

    def ramp(self, inp, stops):
        n = self("ShaderNodeValToRGB")
        self.set(n.inputs[0], inp)
        el = n.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], (stops[0][1],) * 3 + (1,)
        el[1].position, el[1].color = stops[1][0], (stops[1][1],) * 3 + (1,)
        return n.outputs[0]

    def noise(self, vec, scale, detail=6.0, rough=0.6, stretch=(1, 1, 1)):
        m = self("ShaderNodeMapping")
        self.set(m.inputs["Vector"], vec)
        m.inputs["Scale"].default_value = stretch
        n = self("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=rough)
        self.set(n.inputs["Vector"], m.outputs[0])
        return n.outputs["Fac"]

    def attr(self, name, kind="GEOMETRY"):
        return self("ShaderNodeAttribute", _attribute_name=name, _attribute_type=kind)

    def out(self, shader):
        o = self("ShaderNodeOutputMaterial")
        self.set(o.inputs["Surface"], shader)


def _bsdf(n, **kw):
    b = n("ShaderNodeBsdfPrincipled")
    for k, v in kw.items():
        n.set(b.inputs[k], v)
    return b


def _get(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    return m


def weathered(name, base, metal=0.0, rough=0.52, wear=1.0, seed=0.0, chips=True, panels=True):
    m = _get(name)
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    obj = n("ShaderNodeVectorMath", _operation="ADD")
    n.set(obj.inputs[0], tc.outputs["Object"])
    obj.inputs[1].default_value = (seed * 13.1, seed * 7.7, seed * 3.3)
    v = obj.outputs[0]
    W = n("ShaderNodeValue")
    W.outputs[0].default_value = wear
    W.label = "Wear"
    col = n("ShaderNodeRGB")
    col.outputs[0].default_value = tuple(base) + (1,)
    color = col.outputs[0]
    rgh = rough
    # per-panel tone drift and dark seams
    if panels:
        pa = n.attr("panel")
        is_seam = n.math("LESS_THAN", pa.outputs["Fac"], -0.5)
        drift = n.math("MULTIPLY_ADD", pa.outputs["Fac"], 0.30, 0.84)
        tone = n("ShaderNodeHueSaturation")
        n.set(tone.inputs["Value"], drift)
        n.set(tone.inputs["Hue"], n.math("MULTIPLY_ADD", pa.outputs["Fac"], 0.025, 0.4875))
        n.set(tone.inputs["Color"], color)
        color = tone.outputs[0]
        color = n.mix(n.math("MULTIPLY", is_seam, 0.85), color, (0.02, 0.018, 0.016), "MULTIPLY")
    # large blotchy discolouration
    blot = n.noise(v, 0.35, 4, 0.55)
    blotm = n.ramp(blot, [(0.35, 0.0), (0.75, 1.0)])
    color = n.mix(n.math("MULTIPLY", blotm, n.math("MULTIPLY", W, 0.38)), color, (0.40, 0.33, 0.24), "MULTIPLY")
    # cavity grime from AO
    ao = n("ShaderNodeAmbientOcclusion", Distance=0.35)
    ao.only_local = True
    cav = n.math("SUBTRACT", 1.0, ao.outputs["AO"])
    cav = n.math("MULTIPLY", n.math("POWER", cav, 0.7), W, clamp=True)
    grime_n = n.noise(v, 3.0, 8, 0.65)
    grime = n.math("MULTIPLY", cav, n.math("MULTIPLY_ADD", grime_n, 0.8, 0.5), clamp=True)
    color = n.mix(n.math("MULTIPLY", grime, 0.85), color, (0.09, 0.075, 0.06), "MIX")
    # streaks: grime and rust running down
    st = n.noise(v, 6.0, 5, 0.5, stretch=(1.0, 1.0, 0.07))
    st2 = n.noise(v, 2.0, 3, 0.5)
    streak = n.math("MULTIPLY", n.ramp(st, [(0.46, 0.0), (0.70, 1.0)]), n.ramp(st2, [(0.38, 0.0), (0.66, 1.0)]))
    streak = n.math("MULTIPLY", streak, n.math("MULTIPLY", W, 0.95), clamp=True)
    color = n.mix(streak, color, (0.16, 0.12, 0.09), "MULTIPLY")
    rs = n.noise(v, 9.0, 6, 0.6, stretch=(1.0, 1.0, 0.05))
    rust = n.math("MULTIPLY", n.ramp(rs, [(0.58, 0.0), (0.76, 1.0)]), n.math("MULTIPLY", W, 0.7), clamp=True)
    color = n.mix(rust, color, (0.30, 0.12, 0.04), "MIX")
    # soot near exhausts (object props soot, soot_y)
    soot_on = n.attr("soot", "OBJECT").outputs["Fac"]
    soot_y = n.attr("soot_y", "OBJECT").outputs["Fac"]
    sep = n("ShaderNodeSeparateXYZ")
    n.set(sep.inputs[0], tc.outputs["Object"])
    dy = n.math("SUBTRACT", sep.outputs["Y"], soot_y)
    soot = n.math("MULTIPLY", n.math("SUBTRACT", 1.0, n.math("MULTIPLY", n.math("ADD", dy, 0.5), 0.4), clamp=True), soot_on)
    soot = n.math("MULTIPLY", soot, n.math("MULTIPLY_ADD", n.noise(v, 1.5, 6, 0.6), 0.9, 0.3), clamp=True)
    color = n.mix(n.math("MULTIPLY", soot, 0.9), color, (0.025, 0.022, 0.02), "MIX")
    # lived-in: underside and lower flanks go darker and oilier
    geo_b = n("ShaderNodeNewGeometry")
    sepb = n("ShaderNodeSeparateXYZ")
    n.set(sepb.inputs[0], geo_b.outputs["Normal"])
    under = n.ramp(n.math("MULTIPLY_ADD", sepb.outputs["Z"], -0.5, 0.5), [(0.45, 0.0), (0.95, 1.0)])
    under = n.math("MULTIPLY", under, n.math("MULTIPLY_ADD", n.noise(v, 1.2, 5, 0.6), 0.7, 0.35), clamp=True)
    color = n.mix(n.math("MULTIPLY", under, n.math("MULTIPLY", W, 0.55)), color, (0.10, 0.085, 0.07), "MIX")
    # hand wear: polished, slightly darker smudges at grab height on the flanks
    smudge = n.ramp(n.noise(v, 2.5, 6, 0.65), [(0.62, 0.0), (0.75, 1.0)])
    color = n.mix(n.math("MULTIPLY", smudge, n.math("MULTIPLY", W, 0.35)), color, (0.55, 0.5, 0.44), "MULTIPLY")
    # dust on top faces
    geo_n = n("ShaderNodeNewGeometry")
    sepn = n("ShaderNodeSeparateXYZ")
    n.set(sepn.inputs[0], geo_n.outputs["Normal"])
    up = n.math("MULTIPLY", n.ramp(sepn.outputs["Z"], [(0.55, 0.0), (0.95, 1.0)]),
                n.math("MULTIPLY", n.noise(v, 4.0, 6, 0.6), n.math("MULTIPLY", W, 0.55)), clamp=True)
    color = n.mix(up, color, (0.55, 0.50, 0.44), "MIX")
    metallic, roughness = metal, rgh
    rough_s = n.math("ADD", n.math("MULTIPLY", grime, 0.25), n.math("MULTIPLY", streak, 0.15))
    roughness = n.math("ADD", rough_s, rgh, clamp=True)
    roughness = n.math("ADD", roughness, n.math("MULTIPLY", up, 0.2), clamp=True)
    if chips:
        bev = n("ShaderNodeBevel", Radius=0.03)
        bev.samples = 6
        dot = n("ShaderNodeVectorMath", _operation="DOT_PRODUCT")
        n.set(dot.inputs[0], bev.outputs[0])
        n.set(dot.inputs[1], geo_n.outputs["Normal"])
        edge = n.math("SUBTRACT", 1.0, dot.outputs["Value"])
        edge = n.math("MULTIPLY", edge, 14.0, clamp=True)
        cn = n.noise(v, 7.0, 10, 0.7)
        chip = n.math("MULTIPLY", edge, n.ramp(cn, [(0.38, 0.0), (0.58, 1.0)]))
        speck = n.ramp(n.noise(v, 22.0, 4, 0.5), [(0.70, 0.0), (0.74, 1.0)])
        chip = n.math("MAXIMUM", chip, n.math("MULTIPLY", speck, 0.8))
        chip = n.math("MULTIPLY", chip, W, clamp=True)
        color = n.mix(chip, color, (0.30, 0.29, 0.28), "MIX")
        metallic = n.mixf(chip, metal, 0.9)
        roughness = n.mixf(chip, roughness, 0.38)
    # bump: fine pitting + scratches + streak relief
    b1 = n.noise(v, 90.0, 4, 0.6)
    scr = n.noise(v, 30.0, 2, 0.5, stretch=(1.0, 40.0, 1.0))
    scr = n.ramp(scr, [(0.70, 0.0), (0.73, 1.0)])
    h = n.math("ADD", n.math("MULTIPLY", b1, 0.5), n.math("MULTIPLY", scr, -0.6))
    bump = n("ShaderNodeBump", Strength=0.08, Distance=0.004)
    n.set(bump.inputs["Height"], h)
    b = _bsdf(n, **{"Base Color": color, "Metallic": metallic, "Roughness": roughness, "Normal": bump.outputs[0]})
    n.out(b)
    m["hs_wear"] = wear
    return m


def emissive(name, color, strength_attr, scale, base=(0.05, 0.05, 0.05), floor=0.0):
    m = _get(name)
    n = N(m)
    a = n.attr(strength_attr, "OBJECT").outputs["Fac"]
    s = n.math("MULTIPLY_ADD", a, scale, floor)
    b = _bsdf(n, **{"Base Color": base, "Roughness": 0.35, "Emission Color": tuple(color) + (1,),
                    "Emission Strength": s})
    n.out(b)
    return m


def glass(name):
    m = _get(name)
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    smudge = n.noise(tc.outputs["Object"], 3.0, 8, 0.7)
    r = n.math("MULTIPLY_ADD", n.math("POWER", smudge, 3.0), 0.35, 0.02)
    b = _bsdf(n, **{"Base Color": (0.01, 0.012, 0.014), "Roughness": r, "Specular IOR Level": 0.8,
                    "Emission Color": (1.0, 0.62, 0.32, 1), "Emission Strength": 0.35, "Coat Weight": 0.6})
    n.out(b)
    return m


def heat_metal(name, wear):
    m = _get(name)
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    lw = n("ShaderNodeLayerWeight", Blend=0.35)
    tint = n("ShaderNodeValToRGB")
    n.set(tint.inputs[0], n.math("ADD", lw.outputs["Facing"], n.math("MULTIPLY", n.noise(tc.outputs["Object"], 1.2), 0.4)))
    el = tint.color_ramp.elements
    el[0].position, el[0].color = 0.15, (0.42, 0.40, 0.38, 1)
    el[1].position, el[1].color = 0.95, (0.22, 0.16, 0.30, 1)
    e = el.new(0.6)
    e.color = (0.55, 0.40, 0.18, 1)
    soot = n.ramp(n.noise(tc.outputs["Object"], 2.5, 6), [(0.45, 0.0), (0.7, 1.0)])
    col = n.mix(n.math("MULTIPLY", soot, 0.7 * wear), tint.outputs[0], (0.03, 0.028, 0.026))
    aniso = n.noise(tc.outputs["Object"], 40.0, 3, 0.5, stretch=(1, 30, 1))
    b = _bsdf(n, **{"Base Color": col, "Metallic": 1.0,
                    "Roughness": n.math("MULTIPLY_ADD", aniso, 0.2, 0.22), "Anisotropic": 0.5})
    n.out(b)
    return m


def plain(name, color, rough, metal=0.0):
    m = _get(name)
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    r = n.math("MULTIPLY_ADD", n.noise(tc.outputs["Object"], 8.0), 0.2, rough - 0.1)
    b = _bsdf(n, **{"Base Color": tuple(color) + (1,), "Roughness": r, "Metallic": metal})
    n.out(b)
    return m


def build_all(wear=1.0, seed=1):
    P = PALETTE
    mats = {
        "HS Paint": weathered("HS Paint", P["paint"], 0.0, 0.5, wear, 0.0),
        "HS Dark Metal": weathered("HS Dark Metal", P["dark"], 0.55, 0.42, wear * 0.8, 1.0, panels=False),
        "HS Glow Teal": emissive("HS Glow Teal", P["teal"], "hyper", 25.0, base=(0.05, 0.25, 0.22), floor=2.5),
        "HS Accent": weathered("HS Accent", P["accent"], 0.0, 0.5, wear, 2.0),
        "HS Bay": weathered("HS Bay", (0.22, 0.22, 0.21), 0.2, 0.55, wear * 0.7, 3.0, chips=False, panels=False),
        "HS Glass": glass("HS Glass"),
        "HS Rubber": plain("HS Rubber", (0.015, 0.015, 0.015), 0.8),
        "HS Heat Metal": heat_metal("HS Heat Metal", wear),
        "HS Engine": emissive("HS Engine", (0.55, 0.85, 1.0), "engine", 60.0, base=(0.02, 0.02, 0.02)),
        "HS Nav Red": emissive("HS Nav Red", (1.0, 0.05, 0.02), "lights", 40.0),
        "HS Nav Green": emissive("HS Nav Green", (0.05, 1.0, 0.25), "lights", 40.0),
        "HS Light White": emissive("HS Light White", (1.0, 0.9, 0.75), "lights", 30.0),
        "HS Primer": weathered("HS Primer", P["primer"], 0.0, 0.6, wear, 4.0),
    }
    return [mats[s] for s in SLOTS]
