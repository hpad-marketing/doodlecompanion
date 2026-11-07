"""Background preview baker for Ship Studio. Run by the "Bake missing previews" button:

    blender -b --factory-startup --python bake_previews.py -- <addon parent> <package> <out> <cats> [kit dir] [DeepInDoodles]

Writes only what is missing in <out>:
  set_<id>.jpg, room_<key>.jpg, cam_<camera>.jpg, mood_<MOOD>.jpg   (Cycles, GPU)
  prop_<id>.jpg                                                     (Cycles, GPU)
  droid_<id>.jpg, motion_<droid>_<action>.jpg + .mp4                (Eevee clips)
"""
import importlib
import json
import os
import sys
import time

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
parent, pkg, OUT, CATS = a[0], a[1], a[2], a[3]
KIT = a[4] if len(a) > 4 else ""
ROOT = a[5] if len(a) > 5 else ""
sys.path.insert(0, parent)
SB = importlib.import_module(pkg)
S = importlib.import_module(pkg + ".ship")
Li = importlib.import_module(pkg + ".lighting")
Pr = importlib.import_module(pkg + ".props")
Cat = importlib.import_module(pkg + ".catalog")
os.makedirs(OUT, exist_ok=True)


def want(cat):
    return CATS == "ALL" or cat in CATS.split(",")


def have(name):
    return any(os.path.isfile(os.path.join(OUT, name + e)) for e in (".jpg", ".png"))


def say(*m):
    print("BAKE", *m, flush=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def as_jpeg(sc):
    """Blender 5 keeps a VIDEO media type after a movie render; JPEG is only valid under IMAGE."""
    ims = sc.render.image_settings
    if hasattr(ims, "media_type") and ims.media_type != "IMAGE":
        ims.media_type = "IMAGE"
    ims.file_format = "JPEG"


def still(sc, cam, name, w, h, spp=48):
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.cycles.samples = spp
    as_jpeg(sc)
    sc.render.image_settings.quality = 88
    sc.render.filepath = os.path.join(OUT, name + ".jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    say("wrote", name, round(time.time() - t, 1), "s")


def safe(s):
    return Cat._safe(s)


# ------------------------------------------------------------------ sets, rooms, cameras, moods
if want("SETS") or want("CAMERAS") or want("MOODS"):
    for lid, lay in S.LAYOUTS.items():
        if len(lay["rooms"]) < 2:
            continue
        if have(f"set_{lid}") and not want("CAMERAS") and not want("MOODS"):
            continue
        sc = fresh()
        Li.render_setup(sc, preview=True)
        Li.space_world()
        info = S.build(lid)
        Li.camera_finish(sc)
        if not have(f"set_{lid}"):
            still(sc, bpy.data.objects["Ship Wide"], f"set_{lid}", 960, 540, 64)
        if want("CAMERAS") or CATS == "ALL":
            for c in info["cameras"]:
                n = f"cam_{safe(c['name'])}"
                if not have(n):
                    still(sc, bpy.data.objects[c["name"]], n, 432, 540)
        if want("MOODS") or CATS == "ALL":
            wide = next((bpy.data.objects[c["name"]] for c in info["cameras"] if c["label"] == "Wide master"), None)
            for m in Li.MOODS:
                if wide is not None and not have(f"mood_{m}"):
                    Li.set_mood(m, sc)
                    still(sc, wide, f"mood_{m}", 432, 540)
            Li.set_mood("NORMAL", sc)

if want("ROOMS"):
    rooms = importlib.import_module(pkg + ".rooms")
    for k in rooms.ROOMS:
        if have(f"room_{k}"):
            continue
        sc = fresh()
        Li.render_setup(sc, preview=True)
        Li.space_world()
        info = S.build([k])
        Li.camera_finish(sc)
        cam = next((bpy.data.objects[c["name"]] for c in info["cameras"] if c["label"] != "Ship wide"), None)
        if cam:
            still(sc, cam, f"room_{k}", 432, 540)

# ------------------------------------------------------------------ window views, seen through the lounge window
if want("VIEWS"):
    V = importlib.import_module(pkg + ".views")
    todo = [k for k in V.VIEWS if not have(f"view_{k}")]
    if todo:
        sc = fresh()
        Li.render_setup(sc, preview=True)
        Li.space_world()
        info = S.build(["lounge"])
        Li.camera_finish(sc)
        if not (sc.world and sc.world.name == V.WORLD):
            V.build(sc)
        cam = next((bpy.data.objects[c["name"]] for c in info["cameras"] if c["label"] == "Wide master"), None)
        for k in todo:
            if cam is None:
                break
            V.set_view(k, sc)
            still(sc, cam, f"view_{k}", 432, 540)

# ------------------------------------------------------------------ props on a little stage
if want("PROPS"):
    for pid, (lab, _fn) in Pr.PROPS.items():
        if have(f"prop_{pid}"):
            continue
        sc = fresh()
        Li.render_setup(sc, preview=True)
        Li.space_world(0.4)
        ob = Pr.add(pid, (0, 0, 0))
        bpy.context.view_layer.update()
        fam = [ob] + list(ob.children_recursive)
        pts = [o.matrix_world @ Vector(c) for o in fam if o.type == "MESH" for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        c, size = (lo + hi) / 2, max((hi - lo).length, 0.05)
        floor = bpy.data.meshes.new("Stage")
        floor.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
        fo = bpy.data.objects.new("Stage", floor)
        sc.collection.objects.link(fo)
        fo.data.materials.append(Pr.M.painted_metal("SB Paint Graphite", (0.045, 0.047, 0.05, 1), 0.42))
        for loc, k in (((1.5, -2, 2.5), 6.0), ((-2, -1, 1.5), 1.5), ((0, 2.5, 2), 4.0)):
            L = bpy.data.lights.new("Key", "AREA")
            lo_ = bpy.data.objects.new("Key", L)
            sc.collection.objects.link(lo_)
            lo_.location = c + Vector(loc) * max(size, 0.3)
            dist = (lo_.location - c).length
            L.energy, L.size = k * dist * dist, 0.5 * dist  # same light on the prop whatever its size
            lo_.rotation_euler = (c - lo_.location).to_track_quat("-Z", "Y").to_euler()
        cd = bpy.data.cameras.new("Cam")
        cd.lens = 70
        cam = bpy.data.objects.new("Cam", cd)
        sc.collection.objects.link(cam)
        cam.location = c + Vector((0.9, -1.6, 0.9)).normalized() * size * 3.2
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        still(sc, cam, f"prop_{pid}", 384, 384, 48)

# ------------------------------------------------------------------ droids and their motions
if (want("DROIDS") or want("MOTIONS")) and KIT:
    class P:
        kit_dir, deep_root, thumbs_dir, scans_dir, hero_dir = KIT, ROOT, OUT, "", ""
    for d in Cat.droids(P):
        if not os.path.isfile(d["blend"]):
            say("missing droid file", d["blend"])
            continue
        acts = Cat.motions(d["blend"]) if (want("MOTIONS") or CATS == "ALL") else []
        todo = [x for x in acts if not all(os.path.isfile(os.path.join(OUT, f"motion_{d['id']}_{safe(x)}{e}")) for e in (".mp4", ".jpg"))]
        if have(f"droid_{d['id']}") and not todo:
            continue
        bpy.ops.wm.open_mainfile(filepath=d["blend"])
        sc = bpy.context.scene
        rig = bpy.data.objects.get(d["rig"]) or next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if rig is None:
            continue
        fam = [rig] + list(rig.children_recursive)
        pts = [o.matrix_world @ Vector(c) for o in fam if o.type == "MESH" for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        c, size = (lo + hi) / 2, (hi - lo).length
        cd = bpy.data.cameras.new("SB Thumb Cam")
        cd.lens = 50
        cam = bpy.data.objects.new("SB Thumb Cam", cd)
        sc.collection.objects.link(cam)
        cam.location = c + Vector((0.7, -1.6, 0.35)).normalized() * size * 1.7  # droids face -Y
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        if not have(f"droid_{d['id']}"):
            Li.render_setup(sc, preview=True)
            still(sc, cam, f"droid_{d['id']}", 432, 540, 48)
        # motion clips: Eevee, small, every other frame
        for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try:
                sc.render.engine = eng
                break
            except TypeError:
                continue
        ad = rig.animation_data or rig.animation_data_create()
        for x in todo:
            act = bpy.data.actions.get(x)
            if act is None:
                continue
            ad.action = act
            if hasattr(ad, "action_slot") and getattr(act, "slots", None) and len(act.slots):
                ad.action_slot = act.slots[0]
            f0, f1 = (int(v) for v in act.frame_range)
            sc.frame_start, sc.frame_end, sc.frame_step = f0, max(f0 + 1, f1), 1
            sc.camera = cam
            sc.render.resolution_x = sc.render.resolution_y = 320
            if hasattr(sc.render.image_settings, "media_type"):   # Blender 5.x
                sc.render.image_settings.media_type = "VIDEO"
            sc.render.image_settings.file_format = "FFMPEG"
            sc.render.ffmpeg.format = "MPEG4"
            sc.render.ffmpeg.codec = "H264"
            sc.render.ffmpeg.constant_rate_factor = "MEDIUM"
            n = f"motion_{d['id']}_{safe(x)}"
            sc.render.filepath = os.path.join(OUT, n + "_")
            t = time.time()
            bpy.ops.render.render(animation=True)
            # Blender names movies <path><first>-<last>.mp4: give it the plain name the library looks for
            made = sorted((f for f in os.listdir(OUT) if f.startswith(n + "_") and f.endswith(".mp4")),
                          key=lambda f: os.path.getmtime(os.path.join(OUT, f)))
            if made:
                os.replace(os.path.join(OUT, made[-1]), os.path.join(OUT, n + ".mp4"))
            sc.frame_set((f0 + f1) // 2)
            as_jpeg(sc)
            sc.render.filepath = os.path.join(OUT, n + ".jpg")
            bpy.ops.render.render(write_still=True)
            say("wrote", n, round(time.time() - t, 1), "s")

# ------------------------------------------------------------------ pose presets, one picture per droid and pose
def eevee(sc):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            return
        except TypeError:
            continue


def clip(sc, name, f0, f1, w, h):
    sc.frame_start, sc.frame_end = f0, f1
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    if hasattr(sc.render.image_settings, "media_type"):
        sc.render.image_settings.media_type = "VIDEO"
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "MEDIUM"
    sc.render.filepath = os.path.join(OUT, name + "_")
    bpy.ops.render.render(animation=True)
    made = sorted((f for f in os.listdir(OUT) if f.startswith(name + "_") and f.endswith(".mp4")),
                  key=lambda f: os.path.getmtime(os.path.join(OUT, f)))
    if made:
        os.replace(os.path.join(OUT, made[-1]), os.path.join(OUT, name + ".mp4"))
    if hasattr(sc.render.image_settings, "media_type"):
        sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "JPEG"
    sc.frame_set(f1)
    sc.render.filepath = os.path.join(OUT, name + ".jpg")
    bpy.ops.render.render(write_still=True)


if want("POSES") and KIT:
    PK = importlib.import_module(pkg + ".posekit")

    class PP:
        kit_dir, deep_root, thumbs_dir, scans_dir, hero_dir = KIT, ROOT, OUT, "", ""
    for d in Cat.droids(PP):
        todo = [k for k in PK.POSES if not have(f"pose_{d['id']}_{k}")]
        if not todo or not os.path.isfile(d["blend"]):
            continue
        bpy.ops.wm.open_mainfile(filepath=d["blend"])
        sc = bpy.context.scene
        rig = bpy.data.objects.get(d["rig"]) or next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if rig is None:
            continue
        ad = rig.animation_data
        if ad:
            ad.action = None
        ok = {k for k, _l in PK.poses_for(rig)}
        fam = [rig] + list(rig.children_recursive)
        cd = bpy.data.cameras.new("SB Pose Cam")
        cd.lens = 50
        cam = bpy.data.objects.new("SB Pose Cam", cd)
        sc.collection.objects.link(cam)
        back = Vector((0.35, -1.6, 0.25)).normalized()
        right = Vector((0, 0, 1)).cross(back).normalized()
        up = back.cross(right).normalized()

        def frame_pose():
            """Fit the whole posed droid, hands included, with a small margin on every side."""
            bpy.context.view_layer.update()
            pts = [o.matrix_world @ Vector(c) for o in fam if o.type == "MESH" and o.visible_get() for c in o.bound_box]
            lo = Vector([min(p[i] for p in pts) for i in range(3)])
            hi = Vector([max(p[i] for p in pts) for i in range(3)])
            c = (lo + hi) / 2
            # 320x400: height takes the 36 mm sensor at 50 mm (tan 0.36), width 0.8 of it
            tan_h, tan_w = 0.36 * 0.88, 0.288 * 0.88
            dist = max(max(abs((p - c).dot(up)) / tan_h, abs((p - c).dot(right)) / tan_w) + (p - c).dot(back) for p in pts)
            cam.location = c + back * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        Li.render_setup(sc, preview=True)
        eevee(sc)
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 400, 100
        as_jpeg(sc)
        sc.tool_settings.use_keyframe_insert_auto = False
        for k in todo:
            if k not in ok:
                continue
            PK.apply(rig, k, keyframe=False)
            frame_pose()
            sc.render.filepath = os.path.join(OUT, f"pose_{d['id']}_{k}.jpg")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            say("wrote", f"pose_{d['id']}_{k}", round(time.time() - t, 1), "s")

# ------------------------------------------------------------------ camera moves, played in the lounge
if want("MOVES"):
    CM = importlib.import_module(pkg + ".cammoves")
    todo = [k for k in CM.MOVES if not os.path.isfile(os.path.join(OUT, f"move_{k}.mp4"))]
    if todo:
        sc = fresh()
        Li.render_setup(sc, preview=True)
        Li.space_world()
        info = S.build(["lounge"])
        Li.camera_finish(sc)
        eevee(sc)
        base = next((bpy.data.objects[c["name"]] for c in info["cameras"] if c["label"] != "Ship wide"), None)
        if base is not None:
            for k in todo:
                cam = base.copy()
                cam.data = base.data.copy()
                cam.animation_data_clear()
                sc.collection.objects.link(cam)
                sc.camera = cam
                sc.frame_set(1)
                lab, f0, f1 = CM.apply(sc, k, 1)
                f1 = max(f1, f0 + 12)
                t = time.time()
                clip(sc, f"move_{k}", f0, f1 + 6, 320, 180)
                say("wrote", f"move_{k}", round(time.time() - t, 1), "s")
                bpy.data.objects.remove(cam)

say("DONE")
