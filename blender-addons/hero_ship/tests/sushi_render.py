"""GPU render job for Sushi (OptiX). Builds the ship, saves the .blend files,
renders the ship stills, one thumbnail and one preview MP4 per preset, and
writes the manifest.

blender -b --factory-startup --python sushi_render.py -- <repo_root> <blend_dir> [what] [--fast]
what: all | ship | <preset_id>[,<preset_id>]   (default all)
"""
import sys, os, time, math
argv = sys.argv[sys.argv.index("--") + 1:]
REPO, BLEND_DIR = argv[0], argv[1]
WHAT = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "all"
FAST = "--fast" in argv
sys.path.insert(0, os.path.join(REPO, "blender-addons"))
import bpy
from mathutils import Vector


def gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                print("GPU:", kind, [d.name for d in devs])
                return True
        except TypeError:
            continue
    print("GPU: none, CPU render")
    return False


def setup(sc, w, h, spp):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU" if HAS_GPU else "CPU"
    sc.cycles.samples = spp
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def still(sc, path, quality=92):
    s = sc.render.image_settings
    if hasattr(s, "media_type"):
        s.media_type = "IMAGE"
    s.file_format = "JPEG"
    s.quality = quality
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def movie(sc, path):
    s = sc.render.image_settings
    if hasattr(s, "media_type"):
        s.media_type = "VIDEO"
    s.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.ffmpeg.audio_codec = "NONE"
    sc.render.filepath = path
    bpy.ops.render.render(animation=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
HAS_GPU = gpu()
import hero_ship
from hero_ship import presets, manifest, stage
t0 = time.time()
os.makedirs(BLEND_DIR, exist_ok=True)
PREV = os.path.join(REPO, "previews", "hero_ship")
root = hero_ship.build()
sc = bpy.context.scene
print("built %.1fs" % (time.time() - t0))

if WHAT in ("all", "ship"):
    stage.build("space")
    for k in hero_ship.parts.PROPS:
        root[k] = hero_ship.parts.PROPS[k][0]
    root["gear"] = 0.0
    sc.frame_set(30)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND_DIR, "HeroShip.blend"))
    cam = bpy.data.objects.new("HS Still Camera", bpy.data.cameras.new("HS Still Camera"))
    bpy.data.collections[stage.STAGE].objects.link(cam)
    sc.camera = cam
    cam.data.clip_end = 20000
    setup(sc, 1920, 1080, 64 if FAST else 384)
    shots = {"three_quarter": ((40, 36, 12), (0, -1, 0), 38), "rear": ((-30, -44, 10), (0, -3, 0), 38),
             "side": ((52, -2, 2), (0, 0, 0), 38), "underside": ((22, -14, -26), (0, -2, -1), 32),
             "nose": ((11, 36, 2.5), (0, 18, 0), 38)}
    for name, (p, tgt, lens) in shots.items():
        cam.location = p
        cam.data.lens = lens
        cam.rotation_euler = (Vector(tgt) - Vector(p)).to_track_quat("-Z", "Y").to_euler()
        stage.aim_key(cam=cam)
        out = os.path.join(PREV, "ship", f"{name}.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        still(sc, out)
        if name == "three_quarter":
            setup(sc, 640, 360, 64 if FAST else 256)
            still(sc, os.path.join(PREV, "ship", "thumb.jpg"))
            setup(sc, 1920, 1080, 64 if FAST else 384)
    print("ship stills %.0fs" % (time.time() - t0))

HERO = {"idle_drift": 60, "cruise": 100, "hyperdrive_jump": 92, "planet_landing": 300}
ids = [p["id"] for p in presets.PRESETS] if WHAT in ("all",) else ([] if WHAT == "ship" else WHAT.split(","))
for pid in ids:
    t = time.time()
    presets.apply(root, pid, 1)
    d = os.path.join(PREV, pid)
    os.makedirs(d, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND_DIR, f"HeroShip_{pid}.blend"))
    sc.frame_set(HERO[pid])
    setup(sc, 1920, 1080, 64 if FAST else 256)
    still(sc, os.path.join(d, "still.jpg"))
    setup(sc, 640, 360, 64 if FAST else 128)
    still(sc, os.path.join(d, "thumb.jpg"))
    setup(sc, 960, 540, 24 if FAST else 64)
    movie(sc, os.path.join(d, "preview.mp4"))
    print("preset", pid, "%.0fs" % (time.time() - t))

manifest.write(REPO)
print("DONE %.0fs" % (time.time() - t0))
