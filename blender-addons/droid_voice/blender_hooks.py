"""Put voiced lines into a Blender scene. Only this file imports bpy.

    from droid_voice import voice, blender_hooks
    clip = voice.speak("hazard", "Still no plan.")
    blender_hooks.add_line(bpy.context.scene, clip, frame=120, droid_obj=bpy.data.objects["Hazard"])

Each line becomes a sound strip (channel per droid) and keys two custom
properties on the droid's root object, which the light lip sync and the
gestures-from-voice feature read:
    dv_level   0..1 loudness per frame (visor/LED/antenna brightness)
    dv_accent  1 on stressed syllables, else 0
"""
import bpy

CHANNEL_BASE = 2


def _strips(scene):
    se = scene.sequence_editor or scene.sequence_editor_create()
    return se.strips if hasattr(se, "strips") else se.sequences      # Blender 5.x / 4.x


def droid_channel(droid_id):
    order = ["hazard", "drone", "computer", "rx07"]
    return CHANNEL_BASE + (order.index(droid_id) if droid_id in order else 4 + hash(droid_id) % 8)


def add_line(scene, clip, frame, droid_obj=None, channel=None, robot=True, name=None):
    strips = _strips(scene)
    path = clip["robot"] if robot else clip["dry"]
    s = strips.new_sound(name or f"{clip['name']}: {clip['caption'][:40]}", path,
                         channel or droid_channel(clip["droid"]), int(frame))
    s["dv_text"] = clip["text"]
    s["dv_droid"] = clip["droid"]
    s["dv_take"] = clip["take"]
    if droid_obj is not None:
        key_lights(droid_obj, clip, frame, scene.render.fps / scene.render.fps_base)
    return s


def key_lights(obj, clip, frame, scene_fps):
    ls = clip["lipsync"]
    step = ls["fps"] / scene_fps
    level, acc = ls["level"], set(ls["accents"])
    for p in ("dv_level", "dv_accent"):
        if p not in obj:
            obj[p] = 0.0
    n = int(len(level) / step) if step else 0
    for i in range(n + 1):
        src = min(len(level) - 1, int(i * step)) if level else 0
        f = frame + i
        obj["dv_level"] = level[src] if level else 0.0
        obj.keyframe_insert('["dv_level"]', frame=f)
        obj["dv_accent"] = 1.0 if int(i * step) in acc else 0.0
        obj.keyframe_insert('["dv_accent"]', frame=f)
    obj["dv_level"] = 0.0
    obj.keyframe_insert('["dv_level"]', frame=frame + n + 1)


def place_script(scene, voiced, start_frame=1, droid_objects=None):
    """Lay out voice_script() output on the timeline. droid_objects maps
    droid id -> object. Returns the end frame."""
    fps = scene.render.fps / scene.render.fps_base
    droid_objects = droid_objects or {}
    for c in voiced["lines"]:
        add_line(scene, c, start_frame + round(c["start_s"] * fps), droid_objects.get(c["droid"]))
    for a in voiced["actions"]:
        m = scene.timeline_markers.new(a["text"][:60], frame=start_frame + round(a["at_s"] * fps))
        m.select = False
    return start_frame + round(voiced["length_s"] * fps)
