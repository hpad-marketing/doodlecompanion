"""Episode shots on the shared GPU render queue: DeepInDoodles/_queue.

Sushi already runs the droid render queue (queue_runner.ps1, scheduled task
"Droid render queue"): one Blender job at a time from _queue/jobs/*.json in the
form {blend, script, args, label, thread}, OptiX through gpu_prelude.py, then
the job moves to done/ or failed/ with a log in logs/. Episode shots use the
same queue. Each shot gets a spec in _queue/ship/<name>.json, and the job runs
_queue/ship/render_shot.py with that spec.

On a PC without that runner, start() renders the same jobs in a background
Blender from here, so the format never changes.

    submit(root, name, spec)  start(root, blender)  stop()  busy()  state(root, name)
    python queue_runner.py <root> [--once]      (headless fallback runner)
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time

RUN = {"thread": None, "stop": False, "current": None, "done": 0, "failed": 0, "log": ""}
THREAD = "ship-episode"

RENDER_SHOT = r'''"""Ship Studio: render one episode shot from its spec (run by the render queue)."""
import bpy, glob, json, os, sys
spec = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sc = bpy.data.scenes[spec["scene"]]
if bpy.context.window:
    bpy.context.window.scene = sc
cam = bpy.data.objects.get(spec.get("camera") or "")
if cam:
    sc.camera = cam
r = sc.render
names = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
eng = spec["engine"]
if eng not in names:
    eng = next((n for n in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if n in names), names[0])
r.engine = eng
r.resolution_x, r.resolution_y = spec["resolution"]
r.resolution_percentage = 100
if eng == "CYCLES":
    sc.cycles.samples = spec["samples"]
    sc.cycles.device = "GPU"
    sc.cycles.use_denoising = True
sc.frame_start, sc.frame_end = spec["frames"]
if hasattr(r.image_settings, "media_type"):   # Blender 5.x
    r.image_settings.media_type = "VIDEO"
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "HIGH"
r.ffmpeg.audio_codec = "NONE"
out = spec["output"]
os.makedirs(os.path.dirname(out), exist_ok=True)
r.filepath = out[:-4] + "_part_"
r.use_file_extension = True
bpy.ops.render.render(animation=True, scene=sc.name)
parts = sorted(glob.glob(out[:-4] + "_part_*"), key=os.path.getmtime)
if not parts:
    raise SystemExit("render wrote no file")
os.replace(parts[-1], out)
print("SHOT_DONE", out)
'''


def qdir(root):
    return os.path.join(root, "_queue")


def _dirs(root):
    q = qdir(root)
    d = {k: os.path.join(q, k) for k in ("jobs", "running", "done", "failed", "logs", "ship")}
    for p in d.values():
        os.makedirs(p, exist_ok=True)
    return d


def sushi_runner(root):
    """True when the PC's own queue runner (scheduled task) serves this queue."""
    return os.path.isfile(os.path.join(qdir(root), "queue_runner.ps1"))


def submit(root, name, spec):
    """Queue one shot. Writes the spec and the job; returns the job path."""
    d = _dirs(root)
    script = os.path.join(d["ship"], "render_shot.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(RENDER_SHOT)
    sp = os.path.join(d["ship"], name + ".json")
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    for k in ("done", "failed"):   # a re-queue clears the old result
        old = os.path.join(d[k], name + ".json")
        if os.path.isfile(old):
            os.remove(old)
    job = {"blend": spec["blend"], "script": script, "args": [sp], "label": name, "thread": THREAD}
    jp = os.path.join(d["jobs"], name + ".json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    return jp


def state(root, name, output=None):
    """done | rendering | queued | failed | not queued (and the log path when failed)."""
    if output and os.path.isfile(output):
        return "done"
    q = qdir(root)
    for k, s in (("running", "rendering"), ("jobs", "queued"), ("failed", "failed"), ("done", "failed")):
        if os.path.isfile(os.path.join(q, k, name + ".json")):
            return s   # in done/ without the output file means the render wrote nothing
    return "not queued"


# ------------------------------------------------------------------ fallback runner (PCs without the scheduled task)
def _status(root):
    try:
        with open(os.path.join(qdir(root), "ship", "status.json"), "w", encoding="utf-8") as f:
            json.dump({k: RUN[k] for k in ("current", "done", "failed", "log")} | {"time": time.time()}, f)
    except OSError:
        pass


def _prelude(root):
    p = os.path.join(qdir(root), "gpu_prelude.py")
    return p if os.path.isfile(p) else None


def run(root, blender=None, once=False):
    blender = blender or os.environ.get("BLENDER") or "blender"
    d = _dirs(root)
    while not RUN["stop"]:
        todo = []
        for p in sorted(glob.glob(os.path.join(d["jobs"], "*.json")), key=os.path.getmtime):
            try:
                with open(p, encoding="utf-8") as f:
                    j = json.load(f)
            except (OSError, ValueError):
                continue
            if j.get("thread") == THREAD:   # leave other threads' jobs to their own runner
                todo.append((p, j))
        if not todo:
            RUN["log"] = "Queue empty"
            _status(root)
            if once:
                return
            time.sleep(10)
            continue
        p, j = todo[0]
        name = os.path.basename(p)[:-5]
        runp = os.path.join(d["running"], name + ".json")
        os.replace(p, runp)
        RUN["current"] = j.get("label", name)
        RUN["log"] = "Rendering " + RUN["current"]
        _status(root)
        argv = [blender, "-b", j["blend"], "-y", "--python-exit-code", "1"]
        if _prelude(root):
            argv += ["--python", _prelude(root)]
        argv += ["--python", j["script"], "--"] + [str(a) for a in j.get("args", [])]
        t0 = time.time()
        try:
            res = subprocess.run(argv, capture_output=True, text=True)
            code, out = res.returncode, (res.stdout or "")[-20000:] + "\n" + (res.stderr or "")[-20000:]
        except OSError as e:
            code, out = -1, str(e)
        log = os.path.join(d["logs"], name + ".log")
        with open(log, "w", encoding="utf-8") as f:
            f.write(out)
        j.update(exit_code=code, duration_s=round(time.time() - t0, 1), log=log)
        dest = d["done"] if code == 0 else d["failed"]
        with open(os.path.join(dest, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(j, f, indent=1)
        os.remove(runp)
        RUN["done" if code == 0 else "failed"] += 1
        RUN["current"] = None
        _status(root)


def start(root, blender=None):
    """Render the queue. On Sushi the scheduled runner already does; returns 'sushi' then."""
    if sushi_runner(root):
        RUN["log"] = "Sushi's GPU queue renders these"
        return "sushi"
    if RUN["thread"] and RUN["thread"].is_alive():
        return "running"
    RUN["stop"] = False
    RUN["thread"] = threading.Thread(target=run, args=(root, blender), daemon=True)
    RUN["thread"].start()
    return "started"


def stop():
    RUN["stop"] = True


def busy():
    return bool(RUN["thread"] and RUN["thread"].is_alive())


if __name__ == "__main__":
    run(sys.argv[1], once="--once" in sys.argv)
