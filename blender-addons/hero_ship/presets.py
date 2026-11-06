"""Flight presets for the hero ship.

    PRESETS                    list of {id, label, frames, needs_stage, about}
    apply(root, preset_id, frame_start=1, camera=True, build_stage=True)

A preset keyframes the root ("Hero Ship": flight path and rig properties), the
"Ship Body" child (secondary motion: bob, shake, squash, stretch) and, when
camera=True, a preset camera. Touchdown keeps the feet planted: the body dips by
exactly the shock-strut travel (gear_compress) on the same frames.
"""
import math
import random
import bmesh
import bpy
from mathutils import Euler, Vector
from . import geo, stage
from .layout import GROUND_Z

FPS = 24
PRESETS = [
    {"id": "idle_drift", "label": "Idle drift", "frames": 240, "needs_stage": "space",
     "about": "Floats in place: slow bob and roll, dish turning, nav lights blinking. Loops."},
    {"id": "cruise", "label": "Cruise", "frames": 240, "needs_stage": "space",
     "about": "Full burn through a dust field, gentle banking, camera swings from side to rear."},
    {"id": "hyperdrive_jump", "label": "Hyperdrive jump", "frames": 180, "needs_stage": "space",
     "about": "Radiators fold, drive charges and flickers, ship stretches and is gone in a flash."},
    {"id": "planet_landing", "label": "Planet landing", "frames": 420, "needs_stage": "planet",
     "about": "Descends to a pad: pods tilt for hover, gear drops, dust kicks up, touchdown squash, ramp lowers."},
]
BY_ID = {p["id"]: p for p in PRESETS}
LANDED_Z = -GROUND_Z


def _body(root):
    for ch in root.children:
        if ch.name.startswith("Ship Body"):
            return ch
    return None


def _clear(ob):
    if ob.animation_data:
        ob.animation_data_clear()


def kp(ob, prop, frames_values, interp="BEZIER"):
    """Keys a custom property: [(frame, value), ...]."""
    for f, v in frames_values:
        ob[prop] = v
        ob.keyframe_insert(f'["{prop}"]', frame=f)
    _interp(ob, f'["{prop}"]', interp, None, [f for f, _ in frames_values])


def kv(ob, path, idx, frames_values, interp="BEZIER"):
    for f, v in frames_values:
        getattr(ob, path)[idx] = v
        ob.keyframe_insert(path, index=idx, frame=f)
    _interp(ob, path, interp, idx, [f for f, _ in frames_values])


def _interp(ob, path, interp, idx=None, frames=None):
    fr = set(int(round(f)) for f in frames) if frames else None
    for fc in _fcurves(ob):
        if fc.data_path == path and (idx is None or fc.array_index == idx):
            for k in fc.keyframe_points:
                if fr is None or int(round(k.co.x)) in fr:
                    k.interpolation = interp


def _fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and not hasattr(act, "layers"):
        return list(act.fcurves)
    try:  # Blender 4.4+/5.x layered actions
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        return list(getattr(act, "fcurves", []))


def _cycle(ob):
    for fc in _fcurves(ob):
        fc.modifiers.new("CYCLES")


def _defaults(root, **over):
    from .parts import PROPS
    for k, (v, lo, hi) in PROPS.items():
        root[k] = over.get(k, v)


def _fx_mat():
    m = bpy.data.materials.get("HS FX Glow")
    if m:
        return m
    from .mats import N, _bsdf
    m = bpy.data.materials.new("HS FX Glow")
    n = N(m)
    a = n.attr("fx", "OBJECT").outputs["Fac"]
    col = n.attr("fx_color", "OBJECT").outputs["Color"]
    lw = n("ShaderNodeLayerWeight", Blend=0.5)
    soft = n.math("POWER", n.math("SUBTRACT", 1.0, lw.outputs["Facing"]), 2.2)
    em = n("ShaderNodeEmission")
    n.set(em.inputs["Color"], col)
    n.set(em.inputs["Strength"], n.math("MULTIPLY", n.math("MULTIPLY", a, soft), 10.0))
    tr = n("ShaderNodeBsdfTransparent")
    ad = n("ShaderNodeAddShader")
    n.set(ad.inputs[0], tr)
    n.set(ad.inputs[1], em)
    n.out(ad)
    return m


def _dust_mat():
    m = bpy.data.materials.get("HS FX Dust")
    if m:
        return m
    from .mats import N, _bsdf
    m = bpy.data.materials.new("HS FX Dust")
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    a = n.attr("fx", "OBJECT").outputs["Fac"]
    nz = n.noise(tc.outputs["Object"], 1.2, 8, 0.65)
    g = n("ShaderNodeTexGradient", _gradient_type="SPHERICAL")
    n.set(g.inputs["Vector"], tc.outputs["Object"])
    dens = n.math("MULTIPLY", n.ramp(nz, [(0.35, 0.0), (0.75, 1.0)]), a)
    dens = n.math("MULTIPLY", dens, n.math("POWER", g.outputs["Fac"], 0.6), clamp=True)
    tr = n("ShaderNodeBsdfTransparent")
    d = _bsdf(n, **{"Base Color": (0.55, 0.40, 0.28), "Roughness": 1.0})
    mx = n("ShaderNodeMixShader")
    n.set(mx.inputs[0], dens)
    n.set(mx.inputs[1], tr)
    n.set(mx.inputs[2], d)
    n.out(mx)
    return m


def _fx_obj(c, name, bm, color, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob["fx"] = 0.0
    ob["fx_color"] = list(color) + [1.0]
    ob.visible_shadow = False
    ob["sb_haze"] = 1
    return ob


def _camera(name="HS Preset Camera", lens=35.0):
    c = geo.coll(stage.STAGE)
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        c.objects.link(cam)
    _clear(cam)
    cam.constraints.clear()
    cam.parent = None
    cam.data.lens = lens
    cam.data.clip_start = 0.5
    cam.data.clip_end = 20000
    bpy.context.scene.camera = cam
    return cam


def _look(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def _track(cam, target_ob, head_tail=0.0):
    con = cam.constraints.new("TRACK_TO")
    con.target = target_ob
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    return con


# ---------------------------------------------------------------------------
def idle_drift(root, body, f0, camera):
    n = 240
    _defaults(root, gear=0.0, engine=0.22, radiators=1.0, dish_rpm=4.0, lights=1.0)
    for k in ("gear", "engine", "radiators", "lights", "ramp", "nacelle_tilt", "hyper", "gear_compress"):
        kp(root, k, [(f0, root[k])])
    kp(root, "dish_rpm", [(f0, 4.0)])
    kp(root, "scan_deg", [(f0, -35), (f0 + n // 2, 35), (f0 + n, -35)])
    kv(body, "location", 2, [(f0 + i * n // 4, z) for i, z in enumerate((0.0, 0.35, 0.0, -0.35, 0.0))])
    kv(body, "location", 0, [(f0 + i * n // 2, x) for i, x in enumerate((0.0, 0.15, 0.0))])
    kv(body, "rotation_euler", 1, [(f0 + i * n // 4, math.radians(a)) for i, a in enumerate((0, 1.3, 0, -1.3, 0))])
    kv(body, "rotation_euler", 0, [(f0 + i * n // 2, math.radians(a)) for i, a in enumerate((0.0, 0.7, 0.0))])
    kv(body, "rotation_euler", 2, [(f0 + i * n // 2, math.radians(a)) for i, a in enumerate((0.0, -1.0, 0.0))])
    _cycle(body)
    if camera:
        cam = _camera(lens=32)
        kv(cam, "location", 0, [(f0, 46.0), (f0 + n, 36.0)])
        kv(cam, "location", 1, [(f0, 30.0), (f0 + n, 40.0)])
        kv(cam, "location", 2, [(f0, 10.0), (f0 + n, 7.0)])
        con = _track(cam, root)
        cam.location = (41.0, 35.0, 8.5)
        stage.aim_key(cam=cam)
    return n


def cruise(root, body, f0, camera):
    n = 240
    speed = 3.4  # m per frame (~80 m/s)
    _defaults(root, gear=0.0, engine=1.0, radiators=0.45, dish_rpm=10.0)
    for k in ("gear", "engine", "radiators", "lights", "ramp", "nacelle_tilt", "hyper", "gear_compress", "dish_rpm"):
        kp(root, k, [(f0, root[k])])
    kv(root, "location", 1, [(f0, 0.0), (f0 + n, speed * n)], "LINEAR")
    kv(body, "rotation_euler", 1, [(f0, math.radians(-4)), (f0 + 120, math.radians(5)), (f0 + n, math.radians(-2))])
    kv(body, "rotation_euler", 2, [(f0, math.radians(1.5)), (f0 + 120, math.radians(-1.5)), (f0 + n, math.radians(1))])
    kv(body, "location", 2, [(f0, 0.0), (f0 + 80, 0.6), (f0 + 170, -0.4), (f0 + n, 0.2)])
    # dust field along the path for a sense of speed
    c = geo.coll(stage.STAGE)
    if not bpy.data.objects.get("HS Dust Field"):
        rnd = random.Random(3)
        bm = bmesh.new()
        for i in range(5000):
            p = Vector((rnd.uniform(-160, 160), rnd.uniform(-150, speed * n + 300), rnd.uniform(-90, 90)))
            if abs(p.x) < 14 and abs(p.z) < 9:
                p.x += 30 * (1 if p.x >= 0 else -1)
            r = rnd.uniform(0.03, 0.12)
            res = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=r)
            bmesh.ops.translate(bm, vec=p, verts=res["verts"])
        ob = _fx_obj(c, "HS Dust Field", bm, (0.75, 0.82, 0.9), _fx_mat())
        ob["fx"] = 0.06
    if camera:
        cam = _camera(lens=30)
        fol = bpy.data.objects.get("HS Camera Follow") or geo.empty("HS Camera Follow", c)
        _clear(fol)
        fol.constraints.clear()
        cl = fol.constraints.new("COPY_LOCATION")
        cl.target = root
        cam.parent = fol
        kv(cam, "location", 0, [(f0, -30.0), (f0 + 110, -36.0), (f0 + n, -14.0)])
        kv(cam, "location", 1, [(f0, 34.0), (f0 + 110, -6.0), (f0 + n, -58.0)])
        kv(cam, "location", 2, [(f0, -6.0), (f0 + 110, 4.0), (f0 + n, 10.0)])
        _track(cam, root)
        bpy.context.scene.render.use_motion_blur = True
        cam.location = (-34.0, 0.0, 0.0)
        stage.aim_key(cam=cam, turn=40)
    return n


def hyperdrive_jump(root, body, f0, camera):
    n = 180
    J = f0 + 100  # jump frame
    _defaults(root, gear=0.0)
    for k in ("gear", "lights", "ramp", "nacelle_tilt", "gear_compress", "dish_rpm"):
        kp(root, k, [(f0, root[k])])
    kp(root, "radiators", [(f0 + 8, 1.0), (f0 + 50, 0.0)])
    kp(root, "scan_deg", [(f0, 30.0), (f0 + 40, 0.0)])
    kp(root, "engine", [(f0, 0.25), (f0 + 60, 0.5), (J - 4, 0.8), (J, 1.0)])
    # charge with flicker
    rnd = random.Random(11)
    hy = [(f0, 0.0), (f0 + 30, 0.0)]
    for f in range(f0 + 32, J, 3):
        t = (f - f0 - 30) / (J - f0 - 30)
        hy.append((f, min(1.0, t * t * 1.1 + rnd.uniform(-0.12, 0.12) * t)))
    hy.append((J, 1.0))
    kp(root, "hyper", [(f, max(0.0, v)) for f, v in hy])
    # anticipation pull-back, then the jump
    kv(root, "location", 1, [(f0, 0.0), (J - 10, 0.0), (J - 1, -2.2)])
    kv(root, "location", 1, [(J, 0.0), (J + 2, 40.0), (J + 4, 400.0), (J + 6, 4000.0), (J + 8, 40000.0)], "LINEAR")
    # vibration builds during the charge
    for f in range(f0 + 50, J, 2):
        a = 0.004 * ((f - f0 - 50) / 50.0) ** 2 * 6
        body.location = (rnd.uniform(-a, a), 0.0, rnd.uniform(-a, a))
        body.keyframe_insert("location", frame=f)
    body.location = (0, 0, 0)
    body.keyframe_insert("location", frame=J)
    # stretch forward from the tail (tail at y = -22.4)
    tail = 22.4
    for f, sy in ((J - 1, 0.96), (J, 1.0), (J + 2, 3.0), (J + 4, 8.0)):
        body.scale = (1.0, sy, 1.0)
        body.keyframe_insert("scale", frame=f)
        body.location = (0.0, tail * (sy - 1.0), 0.0)
        body.keyframe_insert("location", index=1, frame=f)
    # flash, streak and shock ring left behind at the jump point
    c = geo.coll(stage.STAGE)
    for nm in ("HS Jump Flash", "HS Jump Streak", "HS Jump Ring"):
        o = bpy.data.objects.get(nm)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    fl = _fx_obj(c, "HS Jump Flash", bm, (0.6, 1.0, 0.95), _fx_mat())
    fl.location = (0, 22.0, 0.6)
    for f, s, a in ((J + 1, 0.01, 0.0), (J + 3, 7.0, 1.2), (J + 6, 11.0, 0.5), (J + 18, 14.0, 0.0)):
        fl.scale = (s, s * 0.6, s)
        fl.keyframe_insert("scale", frame=f)
        kp(fl, "fx", [(f, a)])
    bm = bmesh.new()
    geo.add_cyl(bm, (0, 0, 0), (0, 1, 0), 1.0, segs=24)
    st = _fx_obj(c, "HS Jump Streak", bm, (0.4, 1.0, 0.9), _fx_mat())
    st.location = (0, 18.0, 0.6)
    for f, sx, sy, a in ((J + 1, 0.0, 1.0, 0.0), (J + 2, 1.6, 300.0, 1.5), (J + 6, 0.8, 4000.0, 1.0), (J + 22, 0.02, 4000.0, 0.0)):
        st.scale = (sx, sy, sx)
        st.keyframe_insert("scale", frame=f)
        kp(st, "fx", [(f, a)])
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=96, radius=1.0)
    ring = bmesh.ops.extrude_edge_only(bm, edges=list(bm.edges))
    bmesh.ops.scale(bm, vec=(1.15, 1.15, 1.0), verts=[v for v in ring["geom"] if isinstance(v, bmesh.types.BMVert)])
    rg = _fx_obj(c, "HS Jump Ring", bm, (0.3, 0.9, 1.0), _fx_mat())
    rg.location = (0, 20.0, 0.6)
    rg.rotation_euler = (math.pi / 2, 0, 0)
    for f, s, a in ((J + 2, 0.5, 0.0), (J + 4, 8.0, 1.2), (J + 40, 90.0, 0.0)):
        rg.scale = (s, s, s)
        rg.keyframe_insert("scale", frame=f)
        kp(rg, "fx", [(f, a)])
    if camera:
        cam = _camera(lens=30)
        cam.location = (-24.0, -36.0, 6.0)
        _look(cam, (0, 0, 0))
        # small camera kick at the flash
        for f, dx in ((J + 1, 0.0), (J + 3, 0.35), (J + 5, -0.25), (J + 8, 0.12), (J + 12, 0.0)):
            cam.location.x = -24.0 + dx
            cam.keyframe_insert("location", index=0, frame=f)
        cam.location.x = -24.0
        stage.aim_key(cam=cam, turn=-50)
    return n


def planet_landing(root, body, f0, camera):
    n = 420
    TD = f0 + 290  # touchdown
    _defaults(root, gear=0.0, radiators=1.0, dish_rpm=0.0)
    for k in ("lights", "hyper", "dish_rpm"):
        kp(root, k, [(f0, root[k])])
    path = [(f0, (-70.0, 190.0, 95.0)), (f0 + 90, (-26.0, 72.0, 48.0)), (f0 + 170, (-4.0, 14.0, 24.0)),
            (f0 + 215, (0.0, 0.0, 17.0)), (TD, (0.0, 0.0, LANDED_Z)), (f0 + n, (0.0, 0.0, LANDED_Z))]
    for i in range(3):
        kv(root, "location", i, [(f, p[i]) for f, p in path])
    kv(root, "rotation_euler", 2, [(f0, math.radians(28)), (f0 + 170, math.radians(4)), (f0 + 230, 0.0), (f0 + n, 0.0)])
    kv(root, "rotation_euler", 0, [(f0, math.radians(-6)), (f0 + 150, math.radians(2)), (f0 + 215, 0.0), (f0 + n, 0.0)])
    kv(root, "rotation_euler", 1, [(f0, math.radians(-7)), (f0 + 120, math.radians(4)), (f0 + 210, 0.0), (f0 + n, 0.0)])
    kp(root, "radiators", [(f0, 1.0), (f0 + 30, 0.0), (TD + 40, 0.0), (TD + 100, 1.0)])
    kp(root, "nacelle_tilt", [(f0 + 40, 0.0), (f0 + 130, 1.0), (TD + 45, 1.0), (TD + 95, 0.0)])
    kp(root, "gear", [(f0 + 160, 0.0), (f0 + 240, 1.0)])
    kp(root, "engine", [(f0, 0.75), (f0 + 200, 0.9), (TD, 0.8), (TD + 40, 0.0)])
    kp(root, "scan_deg", [(f0, 0.0), (f0 + 200, 0.0), (f0 + 260, -60.0), (f0 + 330, 60.0), (f0 + 400, 0.0)])
    kp(root, "ramp", [(TD + 70, 0.0), (TD + 125, 1.0)])
    # touchdown squash: body dips exactly as far as the shock struts slide up
    sq = [(TD - 1, 0.0), (TD, 0.0), (TD + 5, 0.16), (TD + 14, 0.03), (TD + 22, 0.0)]
    kp(root, "gear_compress", sq)
    kv(body, "location", 2, [(f, -k) for f, k in sq])
    # dust kicked up by the hover jets and the landing
    c = geo.coll(stage.STAGE)
    for i in range(4):
        nm = f"HS Landing Dust {i}"
        o = bpy.data.objects.get(nm)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=16, radius=1.0)
        d = _fx_obj(c, nm, bm, (0.5, 0.4, 0.3), _dust_mat())
        d.location = (0, 0, 0.6 + i * 0.9)
        for f, s, a in ((f0 + 200, 4.0, 0.0), (f0 + 250, 14.0 + i * 3, 0.35), (TD + 6, 26.0 + i * 5, 0.6),
                        (TD + 90, 40.0 + i * 6, 0.0)):
            d.scale = (s, s, 0.8 + i * 0.5)
            d.keyframe_insert("scale", frame=f)
            kp(d, "fx", [(f, a)])
    if camera:
        cam = _camera(lens=26)
        kv(cam, "location", 0, [(f0, 26.0), (TD, 24.0), (f0 + n, 17.0)])
        kv(cam, "location", 1, [(f0, 26.0), (TD, 22.0), (f0 + n, 14.0)])
        kv(cam, "location", 2, [(f0, 1.7), (TD, 1.8), (f0 + n, 1.6)])
        _track(cam, root)
        cam.location = (24.0, 22.0, 1.8)
        stage.aim_key(cam=cam, turn=60, elev=40)
    return n


FUNCS = {"idle_drift": idle_drift, "cruise": cruise, "hyperdrive_jump": hyperdrive_jump,
         "planet_landing": planet_landing}


def apply(root, preset_id, frame_start=1, camera=True, build_stage=True):
    p = BY_ID[preset_id]
    body = _body(root)
    _clear(root)
    _clear(body)
    root.location = (0, 0, 0)
    root.rotation_euler = (0, 0, 0)
    body.location = (0, 0, 0)
    body.rotation_euler = (0, 0, 0)
    body.scale = (1, 1, 1)
    if build_stage:
        stage.build(p["needs_stage"])
    sc = bpy.context.scene
    sc.render.use_motion_blur = False
    sc.render.fps = FPS
    n = FUNCS[preset_id](root, body, frame_start, camera)
    sc.frame_start = frame_start
    sc.frame_end = frame_start + n - 1
    root["hs_preset"] = preset_id
    return n
