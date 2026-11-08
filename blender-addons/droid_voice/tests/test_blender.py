"""Blender check for blender_hooks (Blender 5.x or pip bpy).
    blender -b --factory-startup --python droid_voice/tests/test_blender.py
    python droid_voice/tests/test_blender.py          (with pip bpy)"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DROID_VOICE_HOME", tempfile.mkdtemp(prefix="dv_bl_"))
import bpy  # noqa: E402
import numpy as np  # noqa: E402

from droid_voice import blender_hooks, lipsync, wavio  # noqa: E402

sr = 24000
t = np.arange(int(1.5 * sr)) / sr
a = 0.4 * np.sin(2 * np.pi * 160 * t) * (np.sin(np.pi * t * 4) > 0)
p = os.path.join(os.environ["DROID_VOICE_HOME"], "line.wav")
wavio.write(p, a, sr)
clip = {"droid": "hazard", "name": "Hazard android", "text": "Test [sigh]", "caption": "Test", "take": 0,
        "dry": p, "robot": p, "duration": 1.5, "lipsync": lipsync.curve(a, sr, 24)}
scene = bpy.context.scene
scene.render.fps = 24
obj = bpy.data.objects.new("Hazard", None)
scene.collection.objects.link(obj)
s = blender_hooks.add_line(scene, clip, 10, droid_obj=obj)
fc = obj.animation_data.action
ok = s.frame_final_start == 10 and s.channel == 2
keys = None
try:
    keys = [f for f in fc.fcurves if f.data_path == '["dv_level"]']
except AttributeError:                       # Blender 5 layered actions
    keys = [f for l in fc.layers for st in l.strips for cb in st.channelbags for f in cb.fcurves
            if f.data_path == '["dv_level"]']
ok = ok and keys and len(keys[0].keyframe_points) >= 36
scene.frame_set(10 + 6)
lvl = obj["dv_level"]
end = blender_hooks.place_script(scene, {"lines": [dict(clip, start_s=0.0), dict(clip, droid="drone", start_s=2.0)],
                                         "actions": [{"at_s": 1.0, "text": "Drone enters"}], "length_s": 3.6},
                                 start_frame=100, droid_objects={"hazard": obj})
ok = ok and end == 100 + round(3.6 * 24) and any(m.name == "Drone enters" for m in scene.timeline_markers)
print("strip", s.frame_final_start, s.channel, "keys", len(keys[0].keyframe_points) if keys else 0,
      "level@16", round(lvl, 3), "end", end)
print("BLENDER HOOKS", "PASS" if ok and lvl > 0 else "FAIL")
sys.exit(0 if ok and lvl > 0 else 1)
