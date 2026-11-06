"""OpenVoice V2 runner (MIT, myshell-ai/OpenVoice + MeloTTS, MIT).
Speaks the line with MeloTTS, then lays the tone of line["ref_wav"] over it
(record yourself doing a droid voice once). Checkpoints: env OPENVOICE_CKPT
-> folder that holds checkpoints_v2/."""
import os
import tempfile

import torch
from _common import load_job, seed_all
from melo.api import TTS
from openvoice import se_extractor
from openvoice.api import ToneColorConverter

CK = os.path.join(os.environ.get("OPENVOICE_CKPT", "."), "checkpoints_v2")
job = load_job()
conv = ToneColorConverter(os.path.join(CK, "converter", "config.json"), device="cuda")
conv.load_ckpt(os.path.join(CK, "converter", "checkpoint.pth"))
tts = TTS(language="EN", device="cuda")
spk = tts.hps.data.spk2id["EN-US"]
src_se = torch.load(os.path.join(CK, "base_speakers", "ses", "en-us.pth"), map_location="cuda")
_tgt = {}

for line in job["lines"]:
    seed_all(line.get("seed"))
    tmp = tempfile.mktemp(suffix=".wav")
    tts.tts_to_file(line["text"], spk, tmp, speed=float(line.get("speed", 1.0)))
    ref = line.get("ref_wav")
    if not ref:
        os.replace(tmp, line["out"])
        continue
    if ref not in _tgt:
        _tgt[ref], _ = se_extractor.get_se(ref, conv, vad=True)
    conv.convert(audio_src_path=tmp, src_se=src_se, tgt_se=_tgt[ref], output_path=line["out"], message="@MyShell")
    os.remove(tmp)
