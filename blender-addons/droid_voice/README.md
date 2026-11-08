# Droid Voice

This package handles the voices in the droid sitcom. Open-source text-to-speech turns each line into speech, and robot processing then changes the sound but keeps the cadence. It's a plain Python package with no UI of its own. Ship Studio builds the cast panel, Voice Booth and Script to Scene on top of it.

Everything here was approved on the voice picker on 6 Nov 2026 (all 22 cards): https://claude.ai/artifact/Gizt4CiBRzjywiC1BPNMDZ

## Engines

| Engine | id | Licence | Runs on | What it brings |
|---|---|---|---|---|
| Kokoro 82M (built in) | `kokoro` | Apache-2.0 (kokoro-onnx MIT) | CPU, inside Blender | It always works and has 50+ preset voices. It's the fallback for every droid. |
| Voicebox hub | `voicebox:<engine>` | MIT app | GPU (CUDA) | Local REST API plus MCP, and designed or cloned voice profiles |
| ↳ Chatterbox Turbo | `voicebox:chatterbox_turbo` | MIT (inaudible watermark) | GPU | Performs `[laugh] [sigh] [cough]` |
| ↳ Qwen3-TTS Voice Design | `voicebox:qwen_voice_design` | Apache-2.0 | GPU | Builds a voice from a sentence, and takes delivery notes as `instruct` |
| Dia2 | `dia2` | Apache-2.0 | GPU (runner) | Two-droid back-and-forth in one pass |
| Zonos v0.1 | `zonos` | Apache-2.0 | GPU (runner) | Emotion vector, rate and pitch dials |
| Orpheus 3B | `orpheus` | Apache-2.0 + Llama 3.2 terms | GPU (runner) | Emotional tags. The model is gated, so you log in to HF once. |
| OpenVoice V2 | `openvoice` | MIT (+ MeloTTS MIT) | GPU (runner) | Copies the tone of a clip you record onto each line |
| eSpeak NG | `espeak` | GPL-3, run as a separate program | CPU | The classic formant robot |

These were left out because their licences are non-commercial or research-only: XTTS-v2, F5-TTS, Fish Audio S2, VibeVoice, IndexTTS-2.5, Spark-TTS, ChatTTS, OmniVoice, Breeze TTS 2 and Voxtral TTS. Piper is out too, because its engine is GPL-3 and every voice has its own licence.

Each heavy engine lives in its own Python env under `_voice\engines\<id>`, so its dependencies never touch Blender. The add-on writes a `job.json`, runs that engine's runner once per batch so the model loads only once, and then reads the WAVs back. See `engines/runner.py` for the contract.

## Robot chains (`robotfx.py`, numpy only)

- `crush`: bit-crush, a slow ring mod, a radio band and a metal echo (the talker)
- `chirp`: a pitch-up that keeps duration, plus a ring mod and a tin echo (the eager one)
- `vocoder`: a channel vocoder at one fixed pitch (the deadpan ship computer)
- `beeps`: cadence beeps. The line is spoken silently, and its pitch and loudness drive chirps on a scale, so emotive-only droids still "say" a real line.
- plus on any chain: `glitch` makes stressed syllables stutter or drop out, and `size_m`/`hollow` add the ring of the droid's own shell

## Cast (`cast.py`)

| Droid | First choice | Fallback | Chain | Size |
|---|---|---|---|---|
| Hazard android (talker) | Qwen3 Voice Design, "dry, weary British narrator" | Kokoro `bm_george` | crush | 2.1 m |
| Hover drone (eager) | Kokoro `af_nicole` | Chatterbox Turbo, cloned from that voice | chirp | 0.6 m |
| Ship's computer (deadpan) | Qwen3 Voice Design, "calm, flat, polite ship AI" | Kokoro `af_kore` | vocoder 98 Hz | 6 m |
| RX-07 (beeps only) | Kokoro `am_michael`, spoken silently | eSpeak | beeps 330 Hz | 1.4 m |

`cast.register_droid("loader", "Tread loader", 2.6)` gives a new droid a voice. Overrides go in `_voice\cast.json`.

## API

```python
from droid_voice import voice, blender_hooks
clip = voice.speak("hazard", "Still no plan. [sigh]", take=0)    # cached; takes 0..2
voice.takes("drone", "A button!")                                  # 3 deliveries
v = voice.voice_script(script_text, dialogue_engine="dia2")        # NAME: line / [action] / (beat)
blender_hooks.place_script(scene, v, start_frame=1, droid_objects={"hazard": obj})
voice.booth(r"C:\...\my_take.wav", "computer")                    # your recording, same droid sound
voice.speak("computer", "Guide line", clean=True)                  # dry guide track to record over
```

`blender_hooks.add_line` puts each line on its own sound strip, with one channel per droid. It also keys `dv_level` (0 to 1 loudness) and `dv_accent` (stressed syllables) on the droid's root object. The light lip sync and gestures-from-voice read those two values.

The MCP tool `droid_voice` (`mcp.py`) supports `status`, `cast`, `speak`, `takes`, `script` and `booth`. Voicebox also has its own MCP server at `http://127.0.0.1:17493/mcp`.

## Install (Sushi)

```powershell
powershell -ExecutionPolicy Bypass -File blender-addons\droid_voice\install\install_sushi.ps1
python blender-addons\droid_voice\install\check_sushi.py   # voices a line per engine, writes _voice\check_report.json
```

The home folder is `Documents\DeepInDoodles\_voice`. You can override it with `DROID_VOICE_HOME`. The RTX 5080 needs the CUDA 12.8 PyTorch wheels, and the installer uses them.

## Tests

- `python droid_voice/tests/test_voice.py`: chains, script parsing, Kokoro voicing for every droid, takes, cache, the booth, and a fake Voicebox server (designed profiles, cloned sample upload, tag passing). It also covers fake runners (the Zonos line, a Dia2 exchange split per turn), MCP, and new droid registration.
- `python droid_voice/tests/test_blender.py`: run it with pip bpy or `blender -b --python`. It checks sound strips, light keys and timeline markers.
