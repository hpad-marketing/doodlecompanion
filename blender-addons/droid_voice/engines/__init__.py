"""Speech engines. Each module has:

    ID / LABEL / LICENCE
    available() -> (ok: bool, why: str)
    synth(reqs: list[dict]) -> list[(audio float64 mono, sample_rate)]

A request dict carries: text (tags already converted for this engine), voice,
speed, instruct, seed, exaggeration, ref_wav, speaker (1/2 for dialogue).
"""
from . import kokoro, espeak, voicebox, runner

ENGINES = {
    "kokoro": kokoro,
    "espeak": espeak,
    # Voicebox hosts several engines; they're addressed as voicebox:<engine>.
    "voicebox": voicebox,
    # Heavy GPU engines run in their own env through a runner command.
    "dia2": runner.Runner("dia2", "Dia2 (Nari Labs)", "Apache-2.0", tags="paren"),
    "zonos": runner.Runner("zonos", "Zonos v0.1 (Zyphra)", "Apache-2.0", tags="strip"),
    "orpheus": runner.Runner("orpheus", "Orpheus 3B (Canopy Labs)", "Apache-2.0 + Llama 3.2 terms", tags="angle"),
    "openvoice": runner.Runner("openvoice", "OpenVoice V2 (MyShell)", "MIT", tags="strip"),
}

# Which tag style each engine performs. "strip" engines just drop the tags.
TAG_STYLE = {
    "kokoro": "strip", "espeak": "strip",
    "voicebox:chatterbox_turbo": "square", "voicebox:chatterbox": "strip",
    "voicebox:qwen": "strip", "voicebox:qwen_voice_design": "strip",
    "voicebox:qwen_custom_voice": "strip", "voicebox:kokoro": "strip", "voicebox:luxtts": "strip",
    "dia2": "paren", "zonos": "strip", "orpheus": "angle", "openvoice": "strip",
}


def get(engine_id):
    """'voicebox:chatterbox_turbo' -> (module, 'chatterbox_turbo')."""
    base, _, sub = engine_id.partition(":")
    return ENGINES[base], sub


def status():
    """{engine_id: (ok, why)} for every engine, for the cast panel."""
    out = {}
    for k, m in ENGINES.items():
        try:
            out[k] = m.available()
        except Exception as e:  # never let a status check break the UI
            out[k] = (False, str(e))
    return out
