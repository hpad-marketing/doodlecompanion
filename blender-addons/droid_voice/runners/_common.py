"""Shared bits for engine runners. Runners run in the engine's own Python
env (not Blender's), so they only rely on numpy + the standard library here."""
import json
import sys
import wave

import numpy as np


def load_job():
    with open(sys.argv[1], encoding="utf-8") as f:
        return json.load(f)


def write_wav(path, audio, sr):
    a = np.clip(np.asarray(audio, dtype=np.float64).reshape(-1), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes((a * 32767).astype("<i2").tobytes())


def seed_all(seed):
    if seed is None:
        return
    import random
    random.seed(seed)
    np.random.seed(seed % (2 ** 32))
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass
