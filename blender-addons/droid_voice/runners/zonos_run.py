"""Zonos runner (Apache-2.0, Zyphra/Zonos). Uses the transformer model, which
needs no mamba-ssm, so it runs on Windows. line["emotion"] is an 8-value list
[happiness, sadness, disgust, fear, surprise, anger, other, neutral];
line["ref_wav"] (optional) sets the speaker; speed maps to speaking_rate."""
import torchaudio
from _common import load_job, seed_all, write_wav
from zonos.conditioning import make_cond_dict
from zonos.model import Zonos

job = load_job()
model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device="cuda")
_spk = {}

for line in job["lines"]:
    seed_all(line.get("seed"))
    spk = None
    ref = line.get("ref_wav")
    if ref:
        if ref not in _spk:
            w, sr = torchaudio.load(ref)
            _spk[ref] = model.make_speaker_embedding(w, sr)
        spk = _spk[ref]
    kw = dict(text=line["text"], speaker=spk, language="en-us",
              speaking_rate=15.0 * float(line.get("speed", 1.0)))
    if line.get("emotion"):
        kw["emotion"] = line["emotion"]
    if line.get("pitch_std") is not None:
        kw["pitch_std"] = float(line["pitch_std"])
    codes = model.generate(model.prepare_conditioning(make_cond_dict(**kw)))
    wav = model.autoencoder.decode(codes).cpu()[0].numpy()
    write_wav(line["out"], wav, model.autoencoder.sampling_rate)
