"""Pictures for the things in an open file that have none yet: every camera and every scene.

The "In this scene" tab asks for them; a timer takes one small Workbench still at a time
(about a quarter second each) and saves it beside the other thumbnails, so the tab fills
in on its own. A camera that has moved since its picture was taken is snapped again.
"""
import os

import bpy

_Q = {"todo": [], "busy": False, "on": False}
W, H = 320, 180


def _safe(s):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def cam_key(ob):
    return f"cam_{_safe(ob.name)}"


def scene_key(sc):
    return f"scene_{_safe(sc.name)}"


def _sig(ob):
    return ";".join(f"{v:.3f}" for row in ob.matrix_world for v in row) + f";{ob.data.lens:.1f}"


def stale(ob, path):
    return path is None or ob.get("sb_snap_sig") != _sig(ob)


def want(kind, scene_name, cam_name, folder):
    job = (kind, scene_name, cam_name, folder)
    if job not in _Q["todo"]:
        _Q["todo"].append(job)
    if not _Q["on"]:
        _Q["on"] = True
        bpy.app.timers.register(_tick, first_interval=0.5)


def _busy(ctx):
    if bpy.app.is_job_running("RENDER") or bpy.app.is_job_running("RENDER_PREVIEW"):
        return True
    return bool(ctx.screen and ctx.screen.is_animation_playing)


def _snap(kind, scene_name, cam_name, folder):
    sc = bpy.data.scenes.get(scene_name)
    cam = bpy.data.objects.get(cam_name) if cam_name else (sc.camera if sc else None)
    if sc is None or cam is None or cam.type != "CAMERA":
        return
    os.makedirs(folder, exist_ok=True)
    name = cam_key(cam) if kind == "cam" else scene_key(sc)
    r, sh = sc.render, sc.display.shading
    keep = dict(engine=r.engine, x=r.resolution_x, y=r.resolution_y, pct=r.resolution_percentage,
                path=r.filepath, fmt=r.image_settings.file_format, cam=sc.camera,
                light=sh.light, color=sh.color_type)
    haze = [o for o in sc.objects if o.get("sb_haze") and not o.hide_render]   # a solid grey box in Workbench
    try:
        for o in haze:
            o.hide_render = True
        r.engine = "BLENDER_WORKBENCH"
        r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
        r.image_settings.file_format = "JPEG"
        r.filepath = os.path.join(folder, name + ".jpg")
        sh.light, sh.color_type = "STUDIO", "MATERIAL"
        sc.camera = cam
        bpy.ops.render.render(write_still=True, scene=sc.name)
        if kind == "cam":
            cam["sb_snap_sig"] = _sig(cam)
    finally:
        r.engine, r.resolution_x, r.resolution_y = keep["engine"], keep["x"], keep["y"]
        r.resolution_percentage, r.filepath = keep["pct"], keep["path"]
        r.image_settings.file_format, sc.camera = keep["fmt"], keep["cam"]
        sh.light, sh.color_type = keep["light"], keep["color"]
        for o in haze:
            o.hide_render = False


def _tick():
    if not _Q["todo"]:
        _Q["on"] = False
        return None
    ctx = bpy.context
    if _busy(ctx):
        return 1.0
    job = _Q["todo"].pop(0)
    try:
        _snap(*job)
    except (RuntimeError, AttributeError, TypeError, OSError) as e:
        print("ship_builder snaps:", job[2] or job[1], e)
    for w in ctx.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()
    return 0.3
