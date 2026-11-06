"""Heavy GPU engines (Dia2, Zonos, Orpheus, OpenVoice) each live in their own
Python env so their dependencies never clash with Blender or each other.

settings.json "runners": {"dia2": {"cmd": ["C:/.../python.exe", "C:/.../dia2_run.py"]}}
The add-on writes job.json, runs  cmd + [job.json]  once per batch (the model
loads once), and reads the WAVs back. job.json:
  {"engine": "dia2", "lines": [{"text", "out", "voice", "seed", "speed",
   "instruct", "exaggeration", "ref_wav", "speaker", "emotion"}]}
The runner writes each "out" WAV and exits 0. See runners/*.py.
"""
import json
import os
import subprocess
import tempfile

from .. import config, wavio


class Runner:
    def __init__(self, id_, label, licence, tags="strip"):
        self.ID, self.LABEL, self.LICENCE, self.TAGS = id_, label, licence, tags

    def _cmd(self):
        r = config.settings()["runners"].get(self.ID)
        return list(r["cmd"]) if r and r.get("cmd") else None

    def available(self):
        cmd = self._cmd()
        if not cmd:
            return False, f"{self.LABEL} isn't installed on this PC"
        if not os.path.exists(cmd[0]):
            return False, f"runner Python missing: {cmd[0]}"
        return True, "ready (GPU)"

    def synth(self, reqs):
        cmd = self._cmd()
        if not cmd:
            raise RuntimeError(f"{self.LABEL} isn't installed on this PC")
        work = tempfile.mkdtemp(prefix=f"dv_{self.ID}_")
        lines = []
        for i, r in enumerate(reqs):
            d = {k: v for k, v in r.items() if k != "text"}
            d.update(text=r["text"], out=os.path.join(work, f"{i:03d}.wav"))
            lines.append(d)
        job = os.path.join(work, "job.json")
        with open(job, "w", encoding="utf-8") as f:
            json.dump({"engine": self.ID, "lines": lines}, f)
        p = subprocess.run(cmd + [job], capture_output=True, text=True,
                           timeout=config.settings()["timeout_s"])
        if p.returncode != 0:
            raise RuntimeError(f"{self.LABEL} failed: {(p.stderr or p.stdout)[-600:]}")
        return [wavio.read(l["out"]) for l in lines]
