"""python3 test_episode_flow.py <tmp dir>: the episode workflow plans, end to end without Blender scenes."""
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ship_builder import episode as E, episode_flow as F
root = sys.argv[1] if len(sys.argv) > 1 else '/tmp/ep_test'
ep = E.Episode.new(root, "The Leak", template="malfunction")
ep.script = """INT. COMMAND CENTRE
COMPUTER: Minor anomaly detected.
HAZARD: (happy) Minor means fine!
RX-07: (worried) It is dripping. [points at the ceiling]
[a drop lands on the console]
DRONE: (alarmed) bweep bweep!
EXT. SHIP
INT. ENGINE ROOM
HAZARD: (annoyed) Who touched the valve?
RX-07: (calm) You did. Yesterday.
DRONE: Hello there
"""
p = ep.parse()
assert [s["room"] for s in p["scenes"]] == ["bridge", "hero_ship", "engine"], p["scenes"]
assert any(f["kind"] == "bible" for f in p["flags"]), "drone speaking words must be flagged"
n = F.voice_lines(ep)
assert n == 7, n
assert F.voice_lines(ep) == 0, "only changed lines re-voice"
ep.script = ep.script.replace("You did. Yesterday.", "You did. Twice.")
ep.parse()
assert F.voice_lines(ep) == 1
F.pick_take(ep, 3, 2)
tm = F.retime(ep)
assert all(b["start"] >= a["end"] for a, b in zip(tm, tm[1:]))
shots = F.coverage(ep)
kinds = [s["kind"] for s in shots]
assert "exterior" in kinds and "master" in kinds and "single" in kinds and "reaction" in kinds and "insert" in kinds, kinds
F.swap_shot(ep, shots[2]["id"], "Over the shoulder")
assert F.coverage(ep)[2]["preset"] == "Over the shoulder"
F.set_emotion(ep, 3, "sleepy")
F.acting_layers(ep)
F.add_event(ep, "shake", 4.0)
tracks, total = F.track_items(ep)
assert [k for k, _ in tracks] == list(E.TRACKS) and all(items for k, items in tracks if k != "sound"), tracks
chips = F.check_chips(ep, {"intersect": []})
assert dict((k, len(v)) for k, _l, v in chips)["voiced"] == 7   # silent guides are not real voices
jobs, eta = F.queue_jobs(ep, root, "/x/ep.blend", "draft")
assert len(jobs) == len(ep.data["shots"]) and eta.endswith("IST")
job = json.load(open(jobs[0], encoding="utf-8"))
assert set(job) >= {"blend", "script", "args", "label", "thread"} and os.path.isfile(job["script"]) and os.path.isfile(job["args"][0])
assert {st for _i, _p, st in F.queue_progress(ep, root, "draft")} == {"queued"}
plan = F.mix_plan(ep)
argv = F.ffmpeg_mix(plan)
assert "-filter_complex" in argv
fr = F.thumbnail_frames(ep)
assert 1 <= len(fr) <= 6
en, miss = F.srt(ep, "en")
assert "Minor means fine!" in en and "bweep" not in en
hi, miss = F.srt(ep, "hi")
assert hi == "" and miss
ep.data["hi_text"] = {"3": "माइनर मतलब ठीक!"}
hi, miss = F.srt(ep, "hi")
assert "माइनर" in hi
sh = F.shorts(ep)
assert sh and F.shorts_ffmpeg("in.mp4", sh[0], "out.mp4")[0] == "ffmpeg"
pub = F.upload_pack(ep)
assert sorted(os.listdir(pub))[:3] == ["captions_en.srt", "captions_hi.srt", "chapters.txt"], os.listdir(pub)
b = F.load_bible(root); b["gags"].append({"name": "The valve", "cues": ["valve"]}); F.save_bible(root, b)
assert F.gag_hits(root, [ep])[0]["episodes"] == [ep.name]
ep.save()
assert E.Episode.load(ep.folder).data["shots"]
print("EPISODE FLOW OK", len(shots), "shots,", round(ep.data["length_s"], 1), "s, eta", eta)
