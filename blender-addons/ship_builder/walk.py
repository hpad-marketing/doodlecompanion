"""Walk mode: drive a droid through the ship like a game.

Keyboard                         DualSense
  W A S D / arrows  move           left stick   move (screen relative)
  Shift             run            R2           run
  Tab / Shift+Tab   next/prev cam  R1 / L1      next / prev camera
  1 .. 9            pick camera    Triangle     follow camera on/off
  F                 follow camera  right stick  swing the follow camera
  Q                 auto cut       Square       auto cut on/off
  E                 nearest door   Cross        open/close nearest door
  R                 record on/off  Options      record on/off
  V / Shift+V       window view    D-pad up/down  next / prev window view
  Esc / right click leave          Circle       leave

Doors open by themselves as the droid walks up and close behind it. Auto cut
switches to the master camera of whichever room the droid walks into. While
recording, the droid, every door and every camera cut are keyed onto the
timeline in real time, so a walk becomes an animation.

The Walker class holds all of it without any UI, so it can be scripted and
tested headless: Walker(scene, pawn).tick(dt, Input(...)).
"""
import math
import time

import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

from . import ship as S
from . import pad as Pad

SKIP = ("Fourth Wall", "Haze", "Planet", "Planet Ring", "SB Zero-G", "Door Sweep", "Bulkhead")
WALK, RUN = 1.25, 2.6          # m/s
TURN = 7.0                     # how fast the body turns toward its heading
DOOR_NEAR = 1.9                # doors start opening when the droid is this close
OPEN_T, CLOSE_T = 0.55, 0.8    # seconds for a full open / close


class Input:
    def __init__(self, mx=0.0, my=0.0, run=False, orbit=0.0, fire=()):
        self.mx, self.my, self.run, self.orbit, self.fire = mx, my, run, orbit, set(fire)


def _family(ob):
    out = {ob}
    out.update(ob.children_recursive)
    return out


def _flat(v):
    return Vector((v.x, v.y, 0.0))


STEP = 0.22                    # anything lower than this is stepped onto, not walked around


class World:
    """Static obstacles as one BVH, the walkable ground as another; door leaves
    are handled from their open value."""

    def __init__(self, scene, ignore=(), top=2.0):
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys = [], []
        gverts, gpolys = [], []
        for ob in scene.objects:
            if ob in ignore or ob.type not in {"MESH", "CURVE", "FONT"} or ob.hide_render:
                continue
            if ob.get("sb_haze") or ob.get("sb_fourth_wall") or ob.get("sb_ghost") or ob.get("sb_droid"):
                continue
            if ob.get("sb_door") or (ob.parent is not None and ob.parent.get("sb_door")):
                continue  # leaves: analytic, they move
            if any(ob.name.startswith(s) for s in SKIP):
                continue
            ev = ob.evaluated_get(dg)
            try:
                me = ev.to_mesh()
            except RuntimeError:
                continue
            if me is None:
                continue
            mw = ob.matrix_world
            vs = [mw @ v.co for v in me.vertices]
            if not vs:
                ev.to_mesh_clear()
                continue
            zlo, zhi = min(v.z for v in vs), max(v.z for v in vs)
            pl = [tuple(p.vertices) for p in me.polygons]
            if zlo < STEP + 0.05:  # deck, sills, lane lines, cables: the droid stands on these
                base = len(gverts)
                gverts.extend(vs)
                gpolys.extend([tuple(base + i for i in p) for p in pl])
            if zlo < top and zhi > STEP:  # in the way of the body
                base = len(verts)
                verts.extend(vs)
                polys.extend([tuple(base + i for i in p) for p in pl])
            ev.to_mesh_clear()
        self.bvh = BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None
        self.ground = BVHTree.FromPolygons(gverts, gpolys, epsilon=0.0) if gpolys else None
        self.doors = []
        for ctl in S.door_controls().values():
            side = ctl.get("sb_door_side", "right")
            s = 1 if side == "right" else -1
            # control sits 0.4 in front of the wall; the leaf track is 0.09 in front of it
            wall_x = ctl.matrix_world.translation.x + s * 0.4
            self.doors.append(dict(ctl=ctl, id=ctl["sb_door"], s=s, x=wall_x, track=wall_x - s * 0.09,
                                   yc=ctl.matrix_world.translation.y, half=0.74))

    def ray(self, o, d, dist):
        if self.bvh is None:
            return None
        hit = self.bvh.ray_cast(o, d, dist)
        return hit if hit[0] is not None else None

    def ground_z(self, p, r, z_now):
        """Highest walkable surface under the footprint, at most a step above z_now.
        Uses every upward-facing face within the footprint, so even a thin cable
        or light strip lifts the droid instead of cutting into it."""
        if self.ground is None:
            return 0.0
        c = Vector((p.x, p.y, z_now))
        best = None
        for loc, nrm, _i, _d in self.ground.find_nearest_range(c, math.hypot(r, STEP)):
            if nrm.z < 0.5 or loc.z > z_now + STEP or loc.z < z_now - 1.0:
                continue
            if (Vector((loc.x - p.x, loc.y - p.y))).length > r:
                continue
            if best is None or loc.z > best:
                best = loc.z
        if best is None:  # nothing close: fall to whatever is below
            hit = self.ground.ray_cast(c + Vector((0, 0, STEP)), Vector((0, 0, -1)), STEP + 5.0)
            return hit[0].z if hit[0] is not None else z_now
        return best

    def door_segments(self):
        for d in self.doors:
            o = float(d["ctl"].get("open", 0.0))
            for sd in (-1, 1):  # each leaf spans from the gap edge out to the jamb
                a = d["yc"] + sd * d["half"] * o
                b = d["yc"] + sd * d["half"]
                yield Vector((d["track"], min(a, b), 0)), Vector((d["track"], max(a, b), 0)), d


def _seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    q = a + ab * t
    return (p - q).length, q


class Body:
    """Mass and momentum for walk mode: heavy droids get going slowly, take a step or two
    to stop, turn with inertia and can't corner hard at speed; light ones are nimble.

    Mass comes from the rig's "foley_mass_kg" (the same number the contact sounds use),
    else "sb_mass_kg", else an estimate from the droid's size. Top walking speed is the
    walk cycle's own natural pace (stride / cycle time), so cadence and speed agree.
    """
    REF = 85.0   # kg: the hazard droid, the reference for the scaling below

    def __init__(self, rig, size, gait=None):
        m = None
        for k in ("foley_mass_kg", "sb_mass_kg"):
            if rig is not None and k in rig:
                m = float(rig[k])
                break
        if m is None:  # size estimate: a mostly hollow metal body, about 180 kg per cubic metre of bounding box
            m = max(5.0, 180.0 * max(0.01, size.x * size.y * size.z))
        self.mass = m
        r = self.REF / m
        self.accel = 2.4 * r ** 0.4          # m/s^2 drive: 85 kg -> 2.4, 240 kg -> 1.6, 9 kg drone -> 6
        self.brake = 1.6 * self.accel        # feet bite harder than they push
        self.lateral = 1.3 * self.accel      # how hard it can corner before it must slow
        self.yaw_rate = 4.0 * r ** 0.3       # rad/s top turn speed
        self.yaw_acc = 10.0 * r ** 0.5       # rad/s^2: heavy bodies take time to start and stop turning
        self.max_lean = math.radians(6)
        self.lean_gain = 0.6
        natural = None
        if gait is not None and gait.act is not None:
            fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
            natural = gait.stride / max(1e-3, (gait.f1 - gait.f0) / fps)
        self.walk = natural if natural and 0.2 < natural < 3.0 else WALK
        self.run = min(RUN, self.walk * 1.9)
        self.w = 0.0                         # current yaw rate

    def accelerate(self, v, target, yaw, dt):
        """Move velocity toward the stick target with force limits (no instant starts or stops)."""
        dv = target - v
        if dv.length < 1e-6 or dt <= 0:
            return target.copy()
        # split into along-the-motion (speed up / brake) and sideways (cornering)
        along = v.normalized() if v.length > 0.05 else (target.normalized() if target.length > 1e-6 else Vector((0, 0, 0)))
        a_par = dv.dot(along)
        a_lat = dv - along * a_par
        lim_par = (self.accel if a_par > 0 else self.brake) * dt
        a_par = max(-lim_par, min(lim_par, a_par))
        lat = a_lat.length
        if lat > self.lateral * dt:
            a_lat = a_lat * (self.lateral * dt / lat)
        out = v + along * a_par + a_lat
        if target.length < 1e-6 and out.length < 0.02:
            return Vector((0, 0, 0))
        return out

    def turn(self, dyaw, dt):
        """Yaw change this tick: angular speed builds up and winds down (no snap turns)."""
        # the turn rate we'd want, easing in as we approach the heading
        want = max(-self.yaw_rate, min(self.yaw_rate, dyaw * 6.0))
        dw = want - self.w
        lim = self.yaw_acc * dt
        self.w += max(-lim, min(lim, dw))
        step = self.w * dt
        if abs(step) > abs(dyaw):   # never overshoot the heading
            step, self.w = dyaw, 0.0
        return step


class Gait:
    """Plays a droid's walk cycle by distance travelled, so the feet never skate, then
    hands the pose to feet.Planter so every sole lands on the real floor.
    The cycle is any action on the rig whose name holds "walk" (in-place cycles;
    root bone translation is ignored so the Walker alone moves the droid)."""

    ROOTS = ("root", "Root", "COG", "torso")

    def __init__(self, scene, rig, speed=None):
        from . import feet as Ft
        from .wear import _fcurves
        self.rig = rig
        acts = [a for a in bpy.data.actions if "walk" in a.name.lower() and
                any(c.data_path.startswith("pose.bones") for c in _fcurves(a))]
        acts.sort(key=lambda a: (("cycle" not in a.name.lower()) + ("run" in a.name.lower()), len(a.name)))
        self.act = acts[0] if acts else None
        self.curves = []
        if self.act:
            for fc in _fcurves(self.act):
                if not fc.data_path.startswith("pose.bones"):
                    continue
                bone = fc.data_path.split('"')[1]
                if bone in self.ROOTS and fc.data_path.endswith("location"):
                    continue
                self.curves.append(fc)
            self.f0, self.f1 = self.act.frame_range
        fps = scene.render.fps / scene.render.fps_base
        self.stride = (speed or WALK) * max(1.0, (self.f1 - self.f0) if self.act else 24) / fps
        if self.act:
            self.stride = self._measure_stride(scene) or self.stride
        self.rest, self.stance = self._rest_phases(scene) if self.act else ([], {})
        self.spine = next((rig.pose.bones[n] for n in ("spine", "torso", "chest", "hips", "body", "Spine", "Torso", "Hips")
                           if n in rig.pose.bones), None)
        self.phase = 0.0
        self.planter = Ft.Planter(rig, scene)

    def _measure_stride(self, scene):
        """Distance the body must travel per cycle so a planted foot doesn't skate:
        the speed a stance foot slides back in the in-place cycle, times the cycle length."""
        ad = self.rig.animation_data or self.rig.animation_data_create()
        keep, keep_f = ad.action, scene.frame_current
        ad.action = self.act
        if hasattr(ad, "action_slot") and getattr(self.act, "slots", None) and len(self.act.slots):
            ad.action_slot = self.act.slots[0]
        side = next((b for b in self.rig.pose.bones if b.name.startswith("IK_foot")), None)
        track = []
        for fr in range(int(self.f0), int(self.f1) + 1):
            scene.frame_set(fr)
            track.append(side.head.copy())
        ad.action = keep
        scene.frame_set(keep_f)
        if not track:
            return None
        zmin = min(p.z for p in track)
        speeds = sorted((b - a).xy.length for a, b in zip(track, track[1:]) if a.z < zmin + 0.005 and b.z < zmin + 0.005)
        if not speeds:
            return None
        return speeds[len(speeds) // 2] * (self.f1 - self.f0)

    def _rest_phases(self, scene, n=48):
        """Phases of the cycle where both feet are down: where a droid may stop."""
        ad = self.rig.animation_data or self.rig.animation_data_create()
        keep, keep_f = ad.action, scene.frame_current
        ad.action = self.act
        if hasattr(ad, "action_slot") and getattr(self.act, "slots", None) and len(self.act.slots):
            ad.action_slot = self.act.slots[0]
        from . import feet as Ft
        feet = [b for b in self.rig.pose.bones if b.name.startswith("IK_foot")]
        soles = [Ft.Foot(self.rig, b.name.rsplit(".", 1)[-1]) for b in feet]
        zs = []
        for i in range(n):
            scene.frame_set(int(round(self.f0 + (self.f1 - self.f0) * i / n)))
            # the lowest point of each sole (a foot rolling onto its toe is still in stance)
            zs.append([min((p.z for p in so.sole_points()), default=b.head.z) if so.parts else b.head.z
                       for b, so in zip(feet, soles)])
        ad.action = keep
        scene.frame_set(keep_f)
        if not feet:
            return [], {}
        lo = [min(z[k] for z in zs) for k in range(len(feet))]
        down = [[z[k] < lo[k] + 0.004 for k in range(len(feet))] for z in zs]
        stance = {b.name.rsplit(".", 1)[-1]: [d[k] for d in down] for k, b in enumerate(feet)}
        return [i / n for i, d in enumerate(down) if all(d)], stance

    def pose(self, dist, moving, lean=0.0):
        if self.act:
            if moving:
                sgn = 1 if dist > 0 else -1
                at_rest = not self.rest or any(min(abs(self.phase - r), 1 - abs(self.phase - r)) < 0.011 for r in self.rest)
                if sgn != getattr(self, "dir", 1) and not at_rest:
                    # a swinging leg can't reverse in the air: finish this step the way it was
                    # going (a short braking step), and walk the other way from both feet down
                    dist = abs(dist) * getattr(self, "dir", 1)
                else:
                    self.dir = sgn
                self.phase = (self.phase + dist / self.stride) % 1.0
            elif self.rest and not any(abs(self.phase - r) < 0.011 for r in self.rest):
                # stopping: finish the step that is under way, so no foot is left hanging
                self.phase = (self.phase + min(0.02, min((r - self.phase) % 1.0 for r in self.rest))) % 1.0
            fr = self.f0 + self.phase * (self.f1 - self.f0)
            for fc in self.curves:
                try:
                    owner = self.rig.path_resolve(fc.data_path.rsplit(".", 1)[0])
                    prop = fc.data_path.rsplit(".", 1)[1]
                    getattr(owner, prop)[fc.array_index] = fc.evaluate(fr)
                except (ValueError, AttributeError, TypeError, IndexError):
                    continue
        if lean and self.spine is not None:
            # tip the upper body about the rig's sideways axis (legs stay on their IK targets)
            pb = self.spine
            bpy.context.view_layer.update()
            side = Vector((1, 0, 0))   # rig-local right; droids face -Y, so +lean tips forward
            M = pb.matrix
            pb.matrix = Matrix.Translation(M.translation) @ Matrix.Rotation(lean, 4, side) @ Matrix.Translation(-M.translation) @ M
        contact = None
        if self.stance:
            n = len(next(iter(self.stance.values())))
            i = int(round(self.phase * n)) % n
            contact = {side: v[i] for side, v in self.stance.items()}
            if not moving and self.rest and any(min(abs(self.phase - r), 1 - abs(self.phase - r)) < 0.011 for r in self.rest):
                # standing still: both feet are down, whatever a sampled cycle frame says
                contact = {side: True for side in contact}
        return self.planter.plant(contact=contact)

    def key(self, frame):
        for pb in self.rig.pose.bones:
            if pb.name in self.ROOTS:
                continue
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=frame)


class Walker:
    def __init__(self, scene, pawn, radius=None, height=None):
        self.scene, self.pawn = scene, pawn
        fam = _family(pawn)
        lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
        for ob in fam:
            if ob.type in {"MESH", "CURVE", "FONT"}:
                for c in ob.bound_box:
                    w = ob.matrix_world @ Vector(c)
                    lo = Vector(map(min, lo, w))
                    hi = Vector(map(max, hi, w))
        if lo.x > hi.x:
            lo, hi = pawn.location - Vector((0.3, 0.3, 0)), pawn.location + Vector((0.3, 0.3, 1.2))
        # body radius: the farthest any part above step height reaches from the droid's centre line,
        # so a turning box body can't swing a corner into a table rim
        reach = 0.0
        for ob in fam:
            if ob.type in {"MESH", "CURVE", "FONT"}:
                for c in ob.bound_box:
                    w = ob.matrix_world @ Vector(c)
                    if w.z > pawn.location.z + STEP:
                        reach = max(reach, (w.xy - pawn.location.xy).length)
        self.radius = radius or max(0.2, min(0.65, reach + 0.02 if reach else 0.5 * max(hi.x - lo.x, hi.y - lo.y)))
        self.height = height or max(0.4, hi.z - lo.z)
        self.world = World(scene, ignore=fam)
        self.pos = _flat(pawn.location)
        self.z = pawn.location.z
        self.yaw = pawn.rotation_euler.z
        self.vel = Vector()
        self.info = S.info(scene) or {"rooms": [], "cameras": []}
        self.cams = [bpy.data.objects[c["name"]] for c in self.info["cameras"] if c["name"] in bpy.data.objects]
        self.cams = self.cams or [o for o in scene.objects if o.type == "CAMERA"]
        self.follow_cam = self._follow_cam()
        self.follow = False
        self.auto_cut = True
        self.cam_i = self.cams.index(scene.camera) if scene.camera in self.cams else 0
        self.orbit = 0.0
        self.manual = {}            # door id -> forced state from the E / Cross button
        self.recording = False
        self.rec_t0 = self.rec_f0 = 0
        self.last_key = None
        self.t = 0.0
        self.room = self._room_at(self.pos)
        self.events = []
        rig = pawn if pawn.type == "ARMATURE" else next((o for o in fam if o.type == "ARMATURE"), None)
        self.gait = Gait(scene, rig) if rig is not None and any(b.name.startswith("IK_foot") for b in rig.pose.bones) else None
        self.body = Body(rig or pawn, hi - lo, self.gait)
        # a leaning body reaches further: keep the collision radius outside the lean
        self.radius = min(0.75, self.radius + max(0.0, self.height - STEP) * math.sin(self.body.max_lean) * 0.6)
        self.lean = 0.0

    # ------------------------------------------------------------ helpers
    def _follow_cam(self):
        cam = bpy.data.objects.get("SB Follow Cam")
        if cam is None:
            data = bpy.data.cameras.new("SB Follow Cam")
            data.lens = 26
            cam = bpy.data.objects.new("SB Follow Cam", data)
            self.scene.collection.objects.link(cam)
            cam["sb_cam"] = "Follow"
        return cam

    def _heights(self):
        """Probe heights every 4 cm up the body, so thin rims and ledges can't slip between them."""
        top = min(0.95 * self.height, 1.9)
        n = max(2, int((top - STEP) / 0.04))
        return [STEP + 0.02 + (top - STEP - 0.02) * i / n for i in range(n + 1)]

    def _room_at(self, p):
        for r in self.info["rooms"]:
            if abs(p.x - r["x"]) <= r["W"] / 2 and r["y"] <= p.y - 0.0 <= r["y"] + r["D"]:
                return r["name"]
        return None

    # ------------------------------------------------------------ movement
    def _collide(self, p0, p1):
        r, W = self.radius, self.world
        d = p1 - p0
        L = d.length
        if L > 1e-6:  # no tunnelling through thin walls
            dn = d / L
            for h in self._heights():
                hit = W.ray(Vector((p0.x, p0.y, self.z + h)), dn, L + r)
                if hit:
                    L = min(L, max(0.0, hit[3] - r))
            p1 = p0 + dn * L
        for _ in range(4):  # push out of anything closer than the radius
            push = Vector()
            n = 0
            for h in self._heights():
                for k in range(16):
                    a = k * math.tau / 16
                    dv = Vector((math.cos(a), math.sin(a), 0.0))
                    hit = W.ray(Vector((p1.x, p1.y, self.z + h)), dv, r)
                    if hit:
                        push -= dv * (r - hit[3])
                        n += 1
            for a, b, _d in W.door_segments():
                dist, q = _seg_dist(p1, a, b)
                if dist < r:
                    away = _flat(p1 - q)
                    if away.length < 1e-6:
                        away = Vector((-_d["s"], 0, 0))
                    push += away.normalized() * (r - dist) * 4
                    n += 4
            if n == 0:
                break
            p1 = p1 + _flat(push) / max(1, n / 4)
        # a closed door is a wall even if the droid is fast
        for a, b, dd in W.door_segments():
            if (p0.x - dd["track"]) * (p1.x - dd["track"]) < 0 and a.y - r < (p0.y + p1.y) / 2 < b.y + r:
                p1.x = dd["track"] + math.copysign(r, p0.x - dd["track"])
        return p1

    def _view_axes(self):
        cam = self.follow_cam if self.follow else self.scene.camera
        if cam is None:
            return Vector((1, 0, 0)), Vector((0, 1, 0))
        m = cam.matrix_world.to_3x3()
        f = _flat(m @ Vector((0, 0, -1)))
        if f.length < 1e-4:
            f = _flat(m @ Vector((0, 1, 0)))
        f.normalize()
        return Vector((f.y, -f.x, 0)), f

    # ------------------------------------------------------------ doors
    def _doors(self, dt):
        W = self.world
        links = {}
        for a, b in self.info.get("links", []):
            links[a], links[b] = b, a
        want = {}
        for d in W.doors:
            dist = (Vector((d["x"], d["yc"], 0)) - self.pos).length
            inside = abs(self.pos.x - d["x"]) < self.radius + 0.5 and abs(self.pos.y - d["yc"]) < d["half"] + 0.3
            w = 1.0 if (dist < DOOR_NEAR or inside) else 0.0
            if d["id"] in self.manual:
                w = self.manual[d["id"]]
                if inside:
                    w = 1.0
            want[d["id"]] = max(want.get(d["id"], 0.0), w)
            if d["id"] in links:  # both doors of a joint move together
                want[links[d["id"]]] = max(want.get(links[d["id"]], 0.0), w)
        changed = []
        for d in W.doors:
            ctl = d["ctl"]
            cur = float(ctl.get("open", 0.0))
            tgt = want.get(d["id"], 0.0)
            if abs(tgt - cur) < 1e-4:
                continue
            step = dt / (OPEN_T if tgt > cur else CLOSE_T)
            v = min(tgt, cur + step) if tgt > cur else max(tgt, cur - step)
            ctl["open"] = v
            ctl.update_tag()
            changed.append(ctl)
        return changed

    def toggle_nearest_door(self):
        best = min(self.world.doors, key=lambda d: (Vector((d["x"], d["yc"], 0)) - self.pos).length, default=None)
        if best is None:
            return
        cur = float(best["ctl"].get("open", 0.0))
        self.manual[best["id"]] = 0.0 if cur > 0.5 else 1.0

    # ------------------------------------------------------------ cameras
    def set_cam(self, i):
        if not self.cams:
            return
        self.cam_i = i % len(self.cams)
        self.follow = False
        self.scene.camera = self.cams[self.cam_i]
        self._mark_cut()

    def _auto(self):
        room = self._room_at(self.pos)
        if room and room != self.room:
            self.room = room
            if self.auto_cut and not self.follow:
                for i, c in enumerate(self.cams):
                    if c.name.startswith(room + " "):
                        self.cam_i = i
                        self.scene.camera = c
                        self._mark_cut()
                        break

    def _update_follow(self, dt):
        cam = self.follow_cam
        yaw = self.yaw + self.orbit
        back = Matrix.Rotation(yaw, 3, "Z") @ Vector((0.0, 2.6, 0.0))
        eye = Vector((self.pos.x, self.pos.y, self.z + max(1.4, self.height * 1.25)))
        want = eye + back
        hit = self.world.ray(eye, back.normalized(), back.length)
        if hit:
            want = eye + back.normalized() * max(0.4, hit[3] - 0.25)
        k = min(1.0, 6.0 * dt) if self.t > 0 else 1.0
        cam.location = cam.location.lerp(want, k)
        look = Vector((self.pos.x, self.pos.y, self.z + self.height * 0.6)) - cam.location
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        if self.follow:
            self.scene.camera = cam

    # ------------------------------------------------------------ recording
    def _frame(self):
        fps = self.scene.render.fps / self.scene.render.fps_base
        return self.rec_f0 + int(round((self.t - self.rec_t0) * fps))

    def step_view(self, step=1):
        """Change the view outside the windows; keyed on the timeline while recording."""
        from . import views as V
        if self.scene.world is None or self.scene.world.name != V.WORLD:
            V.build(self.scene)
        i = (int(self.scene.get("sb_view", 0)) + step) % len(V.KEYS)
        V.set_view(V.KEYS[i], self.scene, frame=self._frame() if self.recording else None)
        return V.KEYS[i]

    def _mark_cut(self):
        if not self.recording:
            return
        f = self._frame()
        sc = self.scene
        for m in [m for m in sc.timeline_markers if m.frame == f]:
            sc.timeline_markers.remove(m)
        m = sc.timeline_markers.new(f"cut {sc.camera.name}", frame=f)
        m.camera = sc.camera

    def record(self, on=None):
        on = (not self.recording) if on is None else on
        if on and not self.recording:
            self.recording = True
            self.rec_t0, self.rec_f0 = self.t, self.scene.frame_current
            self.last_key = None
            self._mark_cut()
        elif not on and self.recording:
            self.recording = False
            self.scene.frame_end = max(self.scene.frame_end, self._frame())
        return self.recording

    def _key(self, doors):
        f = self._frame()
        if f == self.last_key:
            return
        self.last_key = f
        self.pawn.keyframe_insert("location", frame=f)
        self.pawn.keyframe_insert("rotation_euler", index=2, frame=f)
        if self.gait is not None:
            self.gait.key(f)
        for ctl in {d["ctl"] for d in self.world.doors}:
            if ctl in doors or f == self.rec_f0:
                ctl.keyframe_insert('["open"]', frame=f)
        if self.follow:
            self.follow_cam.keyframe_insert("location", frame=f)
            self.follow_cam.keyframe_insert("rotation_euler", frame=f)
        self.scene.frame_set(f)

    # ------------------------------------------------------------ one tick
    def tick(self, dt, inp):
        self.t += dt
        for f in inp.fire:
            if f == "next_cam":
                self.set_cam(self.cam_i + 1)
            elif f == "prev_cam":
                self.set_cam(self.cam_i - 1)
            elif isinstance(f, tuple) and f[0] == "cam":
                self.set_cam(f[1])
            elif f == "follow":
                self.follow = not self.follow
                if not self.follow:
                    self.scene.camera = self.cams[self.cam_i] if self.cams else None
                self._mark_cut()
            elif f == "auto_cut":
                self.auto_cut = not self.auto_cut
            elif f == "door":
                self.toggle_nearest_door()
            elif f == "record":
                self.record()
            elif f in ("next_view", "prev_view"):
                self.step_view(1 if f == "next_view" else -1)
        right, fwd = self._view_axes()
        stick = Vector((inp.mx, inp.my))
        if stick.length > 1:
            stick.normalize()
        B = self.body
        tgt_v = (right * stick.x + fwd * stick.y) * (B.run if inp.run else B.walk)
        old_v = self.vel.copy()
        self.vel = B.accelerate(self.vel, tgt_v, self.yaw, dt)
        yaw0 = self.yaw
        if self.vel.length > 0.05:  # droids face -Y: heading (dx, dy) -> yaw atan2(dx, -dy)
            goal = math.atan2(self.vel.x, -self.vel.y)
            dyaw = (goal - self.yaw + math.pi) % math.tau - math.pi
            self.yaw += B.turn(dyaw, dt)
        # lean into acceleration and back against braking, like a real mass over its feet
        acc = ((self.vel - old_v) / dt) if dt > 0 else Vector()
        fwd_now = Vector((math.sin(self.yaw), -math.cos(self.yaw), 0.0))  # droids face -Y
        a_fwd = acc.dot(fwd_now)
        target = max(-B.max_lean, min(B.max_lean, math.atan2(a_fwd, 9.81) * B.lean_gain))
        self.lean += (target - self.lean) * min(1.0, 8.0 * dt)
        new = self._collide(self.pos, self.pos + self.vel * dt)
        if dt > 0:
            self.vel = (new - self.pos) / dt if (new - self.pos).length < self.vel.length * dt + 1e-6 else self.vel
        step_len = (new - self.pos).length
        # walking backwards plays the cycle backwards, so a planted foot is never dragged
        if (new - self.pos).dot(fwd_now) < -0.7 * step_len:   # clearly backwards (over 135°), not a turn
            step_len = -step_len
        # turning moves the feet too: a planted foot sits off the turn axis, so the body
        # steps round instead of twisting on its soles (the way a person turns on the spot)
        turn = abs(self.yaw - yaw0) * self.radius * 0.6
        if turn > 1e-6:
            step_len = math.copysign(math.hypot(step_len, turn), step_len if step_len else 1.0)
        self.pos = new
        gz = self.world.ground_z(self.pos, self.radius, self.z - 0.002) + 0.002  # rests on, never in, the floor
        self.z = gz if gz > self.z else self.z + (gz - self.z) * min(1.0, 12.0 * dt)
        self.pawn.location = Vector((self.pos.x, self.pos.y, self.z))
        self.pawn.rotation_euler.z = self.yaw
        if self.gait is not None:
            self.gait.pose(step_len, abs(step_len) > 1e-4, lean=self.lean)  # walk cycle by distance, then plant every sole
        doors = self._doors(dt)
        self.orbit += inp.orbit * 2.5 * dt
        self._update_follow(dt)
        self._auto()
        if self.recording:
            self._key(doors)
        return doors


# ================================================================ operator
KEYS_FIRE = {"TAB": "next_cam", "F": "follow", "Q": "auto_cut", "E": "door", "R": "record", "V": "next_view"}
PAD_FIRE = {"RB": "next_cam", "LB": "prev_cam", "Y": "follow", "X": "auto_cut", "A": "door", "START": "record", "B": "exit",
            "UP": "next_view", "DOWN": "prev_view"}
NUM = {"ONE": 0, "TWO": 1, "THREE": 2, "FOUR": 3, "FIVE": 4, "SIX": 5, "SEVEN": 6, "EIGHT": 7, "NINE": 8}


def pick_pawn(ctx):
    ob = ctx.active_object
    if ob is not None and ob.type != "CAMERA":
        while ob.parent is not None and ob.parent.type in {"ARMATURE", "EMPTY", "MESH"} and not ob.parent.get("sb_door"):
            ob = ob.parent
        return ob
    ob = bpy.data.objects.get("SB Stand-in")
    if ob is None:  # a droid-sized stand-in so walk mode works before any droid is loaded
        me = bpy.data.meshes.new("SB Stand-in")
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.28, radius2=0.22, depth=1.1)
        bmesh.ops.translate(bm, vec=(0, 0, 0.55), verts=bm.verts)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("SB Stand-in", me)
        ob["sb_droid"] = 1
        ctx.scene.collection.objects.link(ob)
        info = S.info(ctx.scene)
        if info and info["rooms"]:
            r = info["rooms"][0]
            ob.location = (r["x"], r["y"] + r["D"] * 0.35, 0.0)
    return ob


class SHIP_OT_walk(bpy.types.Operator):
    """Walk a droid through the ship with WASD or a gamepad"""
    bl_idname = "ship.walk"
    bl_label = "Walk mode"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, ctx, event):
        pawn = pick_pawn(ctx)
        self.walker = Walker(ctx.scene, pawn)
        self.keys = set()
        self.fire = set()
        self.prev_b = 0
        self.last = time.perf_counter()
        self._timer = ctx.window_manager.event_timer_add(1 / 60, window=ctx.window)
        ctx.window_manager.modal_handler_add(self)
        self.start = (pawn.location.copy(), pawn.rotation_euler.copy())
        ctx.workspace.status_text_set("Walk: WASD move, Shift run, Tab camera, F follow, Q auto cut, E door, R record, V window view, Esc leave")
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self.finish(ctx)
        if event.value == "PRESS":
            self.keys.add(event.type)
            if event.type in KEYS_FIRE:
                tag = KEYS_FIRE[event.type]
                if tag == "next_cam" and event.shift:
                    tag = "prev_cam"
                if tag == "next_view" and event.shift:
                    tag = "prev_view"
                self.fire.add(tag)
            elif event.type in NUM:
                self.fire.add(("cam", NUM[event.type]))
        elif event.value == "RELEASE":
            self.keys.discard(event.type)
        if event.type != "TIMER":
            return {"RUNNING_MODAL"} if event.type in KEYS_FIRE or event.type in NUM or event.type in {
                "W", "A", "S", "D", "UP_ARROW", "DOWN_ARROW", "LEFT_ARROW", "RIGHT_ARROW", "LEFT_SHIFT", "RIGHT_SHIFT"} else {"PASS_THROUGH"}
        now = time.perf_counter()
        dt, self.last = min(0.1, now - self.last), now
        k = self.keys
        mx = (("D" in k) or ("RIGHT_ARROW" in k)) - (("A" in k) or ("LEFT_ARROW" in k))
        my = (("W" in k) or ("UP_ARROW" in k)) - (("S" in k) or ("DOWN_ARROW" in k))
        run = "LEFT_SHIFT" in k or "RIGHT_SHIFT" in k
        orbit = 0.0
        p = Pad.read_pad()
        if p:
            if abs(p["lx"]) + abs(p["ly"]) > 0:
                mx, my = p["lx"], p["ly"]
            run = run or p["rt"] > 0.4
            orbit = p["rx"]
            b = p["b"]
            for name, tag in PAD_FIRE.items():
                bit = Pad.XB[name]
                if b & bit and not self.prev_b & bit:
                    self.fire.add(tag)
            self.prev_b = b
        if "exit" in self.fire:
            return self.finish(ctx)
        self.walker.tick(dt, Input(mx, my, run, orbit, self.fire))
        self.fire = set()
        for area in ctx.screen.areas:
            if area.type in {"VIEW_3D", "IMAGE_EDITOR", "DOPESHEET_EDITOR"}:
                area.tag_redraw()
        return {"RUNNING_MODAL"}

    def finish(self, ctx):
        self.walker.record(False)
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)
        return {"FINISHED"}


CLASSES = (SHIP_OT_walk,)
