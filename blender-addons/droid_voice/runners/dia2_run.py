"""Dia2 runner (Apache-2.0, nari-labs/dia2). Run inside the dia2 env:
    uv run --project <dia2 repo> python dia2_run.py job.json
A line with "turns" ([{speaker:1|2, text}]) is generated as ONE back-and-forth
and split per turn using Dia2's word timestamps into line["outs"]."""
import re

from _common import load_job, seed_all, write_wav

from dia2 import Dia2, GenerationConfig, SamplingConfig

job = load_job()
dia = Dia2.from_repo("nari-labs/Dia2-2B", device="cuda", dtype="bfloat16")


def words(t):
    return [w for w in re.sub(r"\[S[12]\]|\([^)]*\)", " ", t).split() if w.strip()]


for line in job["lines"]:
    seed_all(line.get("seed"))
    cfg = GenerationConfig(cfg_scale=2.0, audio=SamplingConfig(temperature=0.8, top_k=50), use_cuda_graph=True)
    turns = line.get("turns") or [{"speaker": line.get("speaker", 1), "text": line["text"]}]
    script = " ".join(f"[S{t['speaker']}] {t['text']}" for t in turns)
    res = dia.generate(script, config=cfg)
    wav = res.waveform.detach().float().cpu().numpy().reshape(-1)
    sr = res.sample_rate
    outs = line.get("outs") or [line["out"]]
    if len(turns) == 1:
        write_wav(outs[0], wav, sr)
        continue
    # split at the first word of each turn
    stamps = [t for _, t in res.timestamps]
    cuts, n = [0], 0
    for t in turns[:-1]:
        n += len(words(t["text"]))
        cuts.append(int(stamps[min(n, len(stamps) - 1)] * sr) if stamps else len(wav) * len(cuts) // len(turns))
    cuts.append(len(wav))
    for i, path in enumerate(outs):
        write_wav(path, wav[cuts[i]:cuts[i + 1]], sr)
