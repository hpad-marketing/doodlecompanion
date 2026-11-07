"""python3 test_ep_scene.py <tmp dir>: build an episode's rooms, marks, shot cameras and edit; act, events, check, a still."""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import episode as E, episode_flow as F, ep_scene as X
root = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp/ep_scene'
ep = E.Episode.new(root, "The Leak", template="blank")
ep.script = """INT. COMMAND CENTRE
COMPUTER: Minor anomaly detected.
HAZARD: (happy) Minor means fine!
RX-07: (worried) It is dripping. [points at the ceiling]
EXT. SHIP
INT. ENGINE ROOM
HAZARD: (annoyed) Who touched the valve?
RX-07: (calm) You did.
"""
ep.parse(); F.voice_lines(ep); F.retime(ep); F.coverage(ep)
F.add_event(ep, "red_alert", 3.0); F.add_event(ep, "shake", 9.0)
t = time.time()
rep = X.build(ep)
print("BUILD", rep, round(time.time() - t, 1), "s")
assert set(rep["rooms"]) == {"bridge", "engine"}, rep
assert all(s.get("scene_name") and s.get("camera") for s in ep.data["shots"]), [(s["id"], s.get("scene_name"), s.get("camera")) for s in ep.data["shots"]]
ed = bpy.data.scenes[X.EDIT.format(ep=X.short(ep))]
se = ed.sequence_editor
strips = se.strips if hasattr(se, "strips") else se.sequences
assert len([s for s in strips if s.get("sb_shot")]) == len(ep.data["shots"])
print("ACT", X.apply_acting(ep), "EVENTS", X.apply_events(ep))
res = X.run_check(ep, step=12)
chips = F.check_chips(ep, res)
print("CHECK", [(k, len(v)) for k, _l, v in chips])
for k in ("intersect",):
    assert not res[k], res[k]
os.makedirs(os.path.join(root, "stills"), exist_ok=True)
sid = next(s["id"] for s in ep.data["shots"] if s["kind"] == "single")
sc = bpy.data.scenes[next(s["scene_name"] for s in ep.data["shots"] if s["id"] == sid)]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
p = X.render_still(ep, sid, os.path.join(root, "stills", sid + ".png"), res=(480, 270))
print("STILL", p, os.path.isfile(p))
ep.save()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, "episode_test.blend"))
print("EP SCENE OK")
