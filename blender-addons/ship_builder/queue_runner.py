"""Sushi render queue: DeepInDoodles/_queue, one JSON job per shot.

The runner renders jobs one at a time in a background Blender (so you can keep
working), OptiX on the GPU for Final. A job whose output already exists is
skipped, so after a crash or a restart the queue resumes from the last
finished shot. Progress is written to _queue/status.json.

    start(root)  stop()  status()
    python queue_runner.py <root>      (headless, e.g. overnight from a shortcut)
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time

RUN = {"thread": None, "stop": False, "current": None, "done": 0, "failed": 0, "log": ""}

EXPR = r'''
import bpy, json, sys
job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sc = bpy.data.scenes[job["scene"]]
bpy.context.window.scene = sc if bpy.context.window else sc
cam = bpy.data.objects.get(job.get("camera") or "")
if cam: sc.camera = cam
r = sc.render
eng = job["engine"]
names = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
if eng not in names: eng = "BLENDER_EEVEE" if "BLENDER_EEVEE" in names else names[0]
r.engine = eng
r.resolution_x, r.resolution_y = job["resolution"]
r.resolution_percentage = 100
if eng == "CYCLES":
    sc.cycles.samples = job["samples"]
    sc.cycles.device = "GPU"
    try:
        p = bpy.context.preferences.addons["cycles"].preferences
        p.compute_device_type = job.get("device") or "OPTIX"
        p.get_devices()
        for d in p.devices: d.use = True
    except Exception as e: print("gpu:", e)
sc.frame_start, sc.frame_end = job["frames"]
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "HIGH"
r.ffmpeg.audio_codec = "NONE"
r.filepath = job["output"][:-4] + "_"
r.use_file_extension = False
bpy.ops.render.render(animation=True, scene=sc.name)
import os, glob
outs = sorted(glob.glob(job["output"][:-4] + "_*"), key=os.path.getmtime)
if outs: os.replace(outs[-1], job["output"])
'''


def qdir(root):
    return os.path.join(root, "_queue")


def jobs(root):
    out = []
    for p in sorted(glob.glob(os.path.join(qdir(root), "*.json"))):
        if os.path.basename(p) == "status.json":
            continue
        try:
            with open(p, encoding="utf-8") as f:
                j = json.load(f)
            j["_path"] = p
            out.append(j)
        except (OSError, ValueError):
            pass
    return out


def _status(root):
    try:
        with open(os.path.join(qdir(root), "status.json"), "w", encoding="utf-8") as f:
            json.dump({k: RUN[k] for k in ("current", "done", "failed", "log")} | {"time": time.time()}, f)
    except OSError:
        pass


def run(root, blender=None, once=False):
    blender = blender or os.environ.get("BLENDER") or "blender"
    expr_path = os.path.join(qdir(root), "_render_job.py")
    os.makedirs(qdir(root), exist_ok=True)
    with open(expr_path, "w", encoding="utf-8") as f:
        f.write(EXPR)
    while not RUN["stop"]:
        todo = [j for j in jobs(root) if not os.path.isfile(j["output"])]
        if not todo:
            RUN["log"] = "Queue empty"
            _status(root)
            if once:
                return
            time.sleep(10)
            continue
        j = todo[0]
        RUN["current"] = f"{j['episode']} {j['shot']} ({j['mode']})"
        RUN["log"] = "Rendering " + RUN["current"]
        _status(root)
        os.makedirs(os.path.dirname(j["output"]), exist_ok=True)
        try:
            res = subprocess.run([blender, "-b", j["blend"], "--python", expr_path, "--", j["_path"]],
                                 capture_output=True, text=True)
            ok = res.returncode == 0 and os.path.isfile(j["output"])
        except OSError as e:
            ok, res = False, None
            RUN["log"] = str(e)
        if ok:
            RUN["done"] += 1
            os.replace(j["_path"], j["_path"][:-5] + ".done")
        else:
            RUN["failed"] += 1
            os.replace(j["_path"], j["_path"][:-5] + ".failed")
            if res is not None:
                with open(j["_path"][:-5] + ".log", "w", encoding="utf-8") as f:
                    f.write((res.stdout or "")[-20000:] + "\n" + (res.stderr or "")[-20000:])
        RUN["current"] = None
        _status(root)


def start(root, blender=None):
    if RUN["thread"] and RUN["thread"].is_alive():
        return False
    RUN["stop"] = False
    RUN["thread"] = threading.Thread(target=run, args=(root, blender), daemon=True)
    RUN["thread"].start()
    return True


def stop():
    RUN["stop"] = True


def busy():
    return bool(RUN["thread"] and RUN["thread"].is_alive())


if __name__ == "__main__":
    run(sys.argv[1], once="--once" in sys.argv)
