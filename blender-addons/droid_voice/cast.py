"""Speaker settings per droid. Each entry is the droid's whole voice, so it
sounds the same in every episode. Defaults below are the speakers approved
on 6 Nov 2026; <home>/cast.json overrides or adds entries.

engines: tried in order, first one available on this PC wins. Kokoro is
always last but one, eSpeak last, so a line always gets voiced.
chain: robotfx chain (crush, chirp, vocoder, beeps, clean) + its dials.
size_m / hollow: body resonance (big hollow shells boom, small ones rattle).
glitch: 0..1 how often stressed words stutter (raise it when damaged).
"""
import copy
import json

from . import config

DEFAULT_CAST = {
    "hazard": {
        "name": "Hazard android", "aliases": ["hazard", "android", "hz"],
        "role": "talker, narrator of the crew",
        "engines": [
            {"engine": "voicebox:qwen_voice_design", "profile": "Droid - Hazard",
             "design": "A dry, weary British narrator in his forties. Deadpan, low-mid pitch, "
                       "measured pace, faintly sarcastic."},
            {"engine": "kokoro", "voice": "bm_george", "speed": 0.95},
            {"engine": "espeak", "voice": "en-gb+m3", "speed": 0.9},
        ],
        "chain": "crush", "dials": {"bits": 6, "hold_sr": 9000, "ring_hz": 38, "ring_mix": 0.45},
        "strength": 1.0, "size_m": 2.1, "hollow": 0.5, "glitch": 0.0,
    },
    "drone": {
        "name": "Hover drone", "aliases": ["drone", "hover drone", "hd"],
        "role": "the eager one",
        "engines": [
            {"engine": "kokoro", "voice": "af_nicole", "speed": 1.0},
            {"engine": "voicebox:chatterbox_turbo", "profile": "Droid - Drone",
             "clone_from": {"engine": "kokoro", "voice": "af_nicole"}},
            {"engine": "espeak", "voice": "en-us+f4", "speed": 1.1},
        ],
        "chain": "chirp", "dials": {"semitones": 3.4, "ring_hz": 520, "ring_mix": 0.3},
        "strength": 1.0, "size_m": 0.6, "hollow": 0.3, "glitch": 0.0,
    },
    "computer": {
        "name": "Ship's computer", "aliases": ["computer", "ship", "ship's computer", "mother"],
        "role": "deadpan ship AI",
        "engines": [
            {"engine": "voicebox:qwen_voice_design", "profile": "Droid - Computer",
             "design": "Calm, flat, polite female ship AI. Even pitch, no emotion, precise diction."},
            {"engine": "kokoro", "voice": "af_kore", "speed": 0.9},
            {"engine": "espeak", "voice": "en-us+f2", "speed": 0.9},
        ],
        "chain": "vocoder", "dials": {"carrier_hz": 98, "dry": 0.15, "room_ms": 18},
        "strength": 1.0, "size_m": 6.0, "hollow": 0.2, "glitch": 0.0,
    },
    "rx07": {
        "name": "RX-07", "aliases": ["rx07", "rx-07", "box mech", "mech"],
        "role": "emotive-only: beeps that follow a real line",
        "engines": [
            {"engine": "kokoro", "voice": "am_michael", "speed": 1.0},
            {"engine": "espeak", "voice": "en-us+m1", "speed": 1.0},
        ],
        "chain": "beeps", "dials": {"base_hz": 330, "wave": "square"},
        "strength": 1.0, "size_m": 1.4, "hollow": 0.4, "glitch": 0.0, "silent": True,
    },
}


def load():
    cast = copy.deepcopy(DEFAULT_CAST)
    f = config.home() / "cast.json"
    if f.exists():
        try:
            for k, v in json.loads(f.read_text(encoding="utf-8")).items():
                cast[k] = {**cast.get(k, {}), **v}
        except ValueError:
            pass
    return cast


def save_entry(droid_id, entry):
    """Register or update a droid's voice (a new droid joins the show here)."""
    f = config.home() / "cast.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    data[droid_id] = entry
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_droid(droid_id, name, size_m, chain="crush", voice="am_echo", silent=False, **extra):
    """One call to give a new droid a voice. Sensible defaults from its size."""
    entry = {"name": name, "aliases": [droid_id, name.lower()], "size_m": size_m,
             "hollow": 0.4, "chain": "beeps" if silent else chain, "dials": {}, "strength": 1.0,
             "glitch": 0.0, "silent": silent,
             "engines": [{"engine": "kokoro", "voice": voice}, {"engine": "espeak", "voice": "en-us"}]}
    entry.update(extra)
    save_entry(droid_id, entry)
    return entry


def find(name_or_id, cast=None):
    cast = cast or load()
    key = name_or_id.strip().lower()
    if key in cast:
        return key, cast[key]
    for k, v in cast.items():
        if key == v.get("name", "").lower() or key in [a.lower() for a in v.get("aliases", [])]:
            return k, v
    raise KeyError(f"No droid called '{name_or_id}' in the cast")
