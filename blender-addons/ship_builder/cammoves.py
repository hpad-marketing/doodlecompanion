"""Camera moves: one click keys a move on the scene camera from the playhead.

    MOVES                       key -> (label, seconds, blurb)
    apply(scene, key)           keys the move on scene.camera (its current framing is the start)
    diagram(key, folder)        a small picture of the move (top or side view), written once

Moves start from wherever the camera is now and look at what it looks at now
(the droid nearest the centre of the frame, else a point 3 m ahead), so they
work for any room and any shot.
"""
import math
import os
import struct
import zlib

import bpy
from mathutils import Matrix, Vector

MOVES = {
    "push_in": ("Push in", 3.0, "Dolly towards the subject"),
    "pull_out": ("Pull out", 3.0, "Dolly away, reveal the room"),
    "slow_push": ("Slow push", 6.0, "A creeping push for tension"),
    "orbit_left": ("Orbit left", 4.0, "Circle the subject to the left"),
    "orbit_right": ("Orbit right", 4.0, "Circle the subject to the right"),
    "crane_up": ("Crane up", 4.0, "Rise and look down on the scene"),
    "crane_down": ("Crane down", 4.0, "Sink to the droids' eye line"),
    "truck_left": ("Truck left", 3.0, "Slide sideways, same angle"),
    "truck_right": ("Truck right", 3.0, "Slide sideways, same angle"),
    "pan_left": ("Pan left", 2.5, "Turn the head of the camera"),
    "pan_right": ("Pan right", 2.5, "Turn the head of the camera"),
    "tilt_up": ("Tilt up", 2.5, "Look up from the floor"),
    "dolly_zoom": ("Dolly zoom", 3.0, "The vertigo shot: push in, zoom out"),
    "crash_zoom": ("Crash zoom", 0.4, "Snap zoom onto a face"),
    "whip_pan": ("Whip pan", 0.35, "Blur-fast pan to the next beat"),
    "handheld": ("Handheld", 6.0, "Gentle shake, documentary feel"),
}


def _target(sc, cam):
    fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    eye = cam.matrix_world.translation
    best, bd = None, 1e9
    for o in sc.objects:
        if o.type == "ARMATURE" and (o.get("sb_droid") or o.get("sb_cast")):
            p = o.matrix_world.translation + Vector((0, 0, 0.8))
            v = p - eye
            if v.length < 0.2 or v.dot(fwd) <= 0:
                continue
            off = (v - fwd * v.dot(fwd)).length / v.length
            if off < bd:
                best, bd = p, off
    return best if best is not None and bd < 0.5 else eye + fwd * 3.0


def _look(eye, tgt):
    return (tgt - eye).to_track_quat("-Z", "Y").to_euler()


def _keys(cam, f, loc=None, rot=None, lens=None):
    if loc is not None:
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
    if rot is not None:
        cam.rotation_euler = rot
        cam.keyframe_insert("rotation_euler", frame=f)
    if lens is not None:
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=f)


def apply(sc, key, frame=None):
    cam = sc.camera
    if cam is None or cam.type != "CAMERA":
        raise RuntimeError("the scene has no camera: pick one in the Cameras tab first")
    lab, secs, _b = MOVES[key]
    fps = sc.render.fps / sc.render.fps_base
    f0 = sc.frame_current if frame is None else frame
    f1 = f0 + max(2, round(secs * fps))
    cam.rotation_mode = "XYZ"
    eye = cam.matrix_world.translation.copy()
    rot = cam.matrix_world.to_euler()
    lens = cam.data.lens
    tgt = _target(sc, cam)
    to = tgt - eye
    dist = to.length
    side = (cam.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    _keys(cam, f0, eye, rot, lens)
    if key in ("push_in", "pull_out", "slow_push"):
        k = {"push_in": 0.3, "pull_out": -0.4, "slow_push": 0.12}[key]
        _keys(cam, f1, eye + to * k, rot)
    elif key in ("orbit_left", "orbit_right"):
        a = math.radians(30 if key == "orbit_left" else -30)
        rel = Matrix.Rotation(a, 3, "Z") @ (eye - tgt)
        e1 = tgt + rel
        _keys(cam, (f0 + f1) // 2, tgt + Matrix.Rotation(a / 2, 3, "Z") @ (eye - tgt), _look(tgt + Matrix.Rotation(a / 2, 3, "Z") @ (eye - tgt), tgt))
        _keys(cam, f1, e1, _look(e1, tgt))
    elif key in ("crane_up", "crane_down"):
        e1 = eye + Vector((0, 0, 0.9 if key == "crane_up" else -min(0.7, eye.z - 0.6)))
        _keys(cam, f1, e1, _look(e1, tgt))
    elif key in ("truck_left", "truck_right"):
        _keys(cam, f1, eye + side * (-1.0 if key == "truck_left" else 1.0), rot)
    elif key in ("pan_left", "pan_right", "whip_pan"):
        a = math.radians({"pan_left": 25, "pan_right": -25, "whip_pan": 70}[key])
        r1 = (Matrix.Rotation(a, 3, "Z") @ cam.matrix_world.to_3x3()).to_euler("XYZ", rot)
        _keys(cam, f1, None, r1)
    elif key == "tilt_up":
        r1 = (Matrix.Rotation(math.radians(20), 3, side) @ cam.matrix_world.to_3x3()).to_euler("XYZ", rot)
        _keys(cam, f1, None, r1)
    elif key == "dolly_zoom":
        k = 0.35
        _keys(cam, f1, eye + to * k, rot, lens * (1 - k))
    elif key == "crash_zoom":
        _keys(cam, f1, None, _look(eye, tgt), min(200, lens * 2.6))
    elif key == "handheld":
        _keys(cam, f1, eye, rot)
        ad = cam.animation_data
        for fc in (ad.action.fcurves if ad and ad.action and hasattr(ad.action, "fcurves") else []):
            if fc.data_path == "rotation_euler" and not any(m.type == "NOISE" for m in fc.modifiers):
                m = fc.modifiers.new("NOISE")
                m.scale, m.strength = 18.0, 0.012
                m.use_restricted_range, m.frame_start, m.frame_end = True, f0, f1
    _ease(cam, f0, f1, key)
    return lab, f0, f1


def _ease(cam, f0, f1, key):
    for idb in (cam, cam.data):
        ad = idb.animation_data
        act = ad.action if ad else None
        curves = getattr(act, "fcurves", None) if act else None
        if curves is None and act is not None:   # Blender 5 layered actions
            try:
                curves = [fc for lay in act.layers for st in lay.strips for cb in st.channelbags for fc in cb.fcurves]
            except AttributeError:
                curves = []
        for fc in curves or []:
            for kp in fc.keyframe_points:
                if f0 <= kp.co.x <= f1:
                    kp.interpolation = "LINEAR" if key in ("crash_zoom", "whip_pan") else "BEZIER"
                    kp.easing = "AUTO"


# ------------------------------------------------------------------ pictures of the moves
INK, MUST, GREY, BG = (31, 31, 29), (224, 166, 75), (120, 122, 126), (22, 23, 25)


def _png(path, w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


class _Canvas:
    def __init__(self, w=192, h=192):
        self.w, self.h = w, h
        self.px = bytearray(BG * (w * h))

    def dot(self, x, y, r, c):
        for yy in range(int(y - r), int(y + r) + 1):
            for xx in range(int(x - r), int(x + r) + 1):
                if 0 <= xx < self.w and 0 <= yy < self.h and (xx - x) ** 2 + (yy - y) ** 2 <= r * r:
                    i = (yy * self.w + xx) * 3
                    self.px[i:i + 3] = bytes(c)

    def line(self, a, b, r, c, dash=0):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
        for k in range(n + 1):
            if dash and (k // dash) % 2:
                continue
            t = k / n
            self.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, r, c)

    def arrow(self, a, b, c):
        self.line(a, b, 2.2, c)
        d = Vector((b[0] - a[0], b[1] - a[1]))
        if d.length < 1:
            return
        d.normalize()
        n = Vector((-d.y, d.x))
        for s in (1, -1):
            tip = Vector(b) - d * 11 + n * 7 * s
            self.line(b, tuple(tip), 2.2, c)

    def cam(self, p, ang, c, size=13):
        d = Vector((math.cos(ang), math.sin(ang)))
        n = Vector((-d.y, d.x))
        p = Vector(p)
        a, b, t = p - d * size + n * size * 0.7, p - d * size - n * size * 0.7, p + d * size * 0.4
        self.line(tuple(a), tuple(b), 2.0, c)
        self.line(tuple(a), tuple(t), 2.0, c)
        self.line(tuple(b), tuple(t), 2.0, c)
        self.dot(p.x, p.y, 3, c)

    def save(self, path):
        flip = bytearray()
        for y in range(self.h - 1, -1, -1):   # PNG rows top-down; we drew y-up
            flip += self.px[y * self.w * 3:(y + 1) * self.w * 3]
        _png(path, self.w, self.h, flip)


def diagram(key, folder):
    path = os.path.join(folder, f"diagram_move_{key}.png")
    if os.path.isfile(path):
        return path
    os.makedirs(folder, exist_ok=True)
    c = _Canvas()
    T = (96, 140)   # the subject
    c.dot(*T, 9, MUST)
    up = math.radians(90)
    start = (96, 52)
    if key in ("push_in", "slow_push", "dolly_zoom"):
        end = (96, 100 if key != "slow_push" else 74)
        c.cam(start, up, GREY)
        c.arrow((96, 68), (96, end[1] - 14), MUST)
        c.cam(end, up, MUST)
        if key == "dolly_zoom":
            for s in (1, -1):
                c.line(end, (96 + s * 70, 182), 1.4, MUST, dash=4)
    elif key == "pull_out":
        c.cam((96, 100), up, GREY)
        c.arrow((96, 84), (96, 36), MUST)
        c.cam((96, 22), up, MUST)
    elif key in ("orbit_left", "orbit_right"):
        s = 1 if key == "orbit_left" else -1
        pts = []
        for k in range(0, 41):
            a = math.radians(-90 + s * k * 1.5)
            pts.append((T[0] + 88 * math.cos(a), T[1] + 88 * math.sin(a)))
        for a, b in zip(pts, pts[1:]):
            c.line(a, b, 1.6, GREY, dash=3)
        c.cam(pts[0], up, GREY)
        e = pts[-1]
        c.arrow(pts[-12], e, MUST)
        c.cam(e, math.atan2(T[1] - e[1], T[0] - e[0]), MUST)
    elif key in ("truck_left", "truck_right"):
        s = -1 if key == "truck_left" else 1
        c.cam((96, 52), up, GREY)
        c.arrow((96 + s * 16, 52), (96 + s * 64, 52), MUST)
        c.cam((96 + s * 76, 52), up, MUST)
    elif key in ("pan_left", "pan_right", "whip_pan"):
        s = 1 if key == "pan_left" else -1
        a1 = up + s * math.radians(70 if key == "whip_pan" else 30)
        c.cam((96, 52), up, GREY, 18)
        c.cam((96, 52), a1, MUST, 18)
        for k in range(1, 4):
            a = up + s * math.radians((70 if key == "whip_pan" else 30) * k / 4)
            c.dot(96 + 40 * math.cos(a), 52 + 40 * math.sin(a), 2.5, MUST)
    elif key in ("crane_up", "crane_down", "tilt_up"):
        c.line((10, 30), (182, 30), 1.5, GREY)                     # floor, side view
        c.dot(150, 44, 9, MUST)
        if key == "tilt_up":
            c.cam((40, 70), math.radians(-20), GREY, 16)
            c.cam((40, 70), math.radians(20), MUST, 16)
        else:
            lo, hi = (40, 60), (40, 150)
            a, b = (lo, hi) if key == "crane_up" else (hi, lo)
            c.cam(a, math.atan2(44 - a[1], 150 - a[0]), GREY)
            c.arrow((40, a[1] + (12 if key == "crane_up" else -12)), (40, b[1] - (12 if key == "crane_up" else -12)), MUST)
            c.cam(b, math.atan2(44 - b[1], 150 - b[0]), MUST)
    elif key == "crash_zoom":
        c.cam((96, 40), up, MUST)
        for s in (1, -1):
            c.line((96, 48), (96 + s * 50, 182), 1.4, GREY, dash=4)
            c.line((96, 48), (96 + s * 14, 182), 2.0, MUST)
    elif key == "handheld":
        p = (96, 52)
        for k in range(14):
            q = (96 + 18 * math.sin(k * 1.9), 52 + 9 * math.cos(k * 2.7))
            c.line(p, q, 1.4, MUST)
            p = q
        c.cam((96, 52), up, MUST)
    c.save(path)
    return path
