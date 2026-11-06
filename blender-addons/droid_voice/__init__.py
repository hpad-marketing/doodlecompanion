"""Droid Voice: open-source TTS + robot voice processing for the droid sitcom.

Plain package (no UI, no bl_info): Ship Studio imports it and builds the
cast panel / Voice Booth / Script to Scene UI on top.

    from droid_voice import voice, cast, engines
    voice.speak("hazard", "Still no plan. [sigh]")         -> Clip (wav paths + lipsync)
    voice.takes("drone", "A button!")                        -> 3 takes
    voice.voice_script(text, dialogue_engine="dia2")         -> timed lines
    voice.booth("my_take.wav", "computer")                  -> your recording, robotised
    engines.status()                                         -> what works on this PC

See README.md for engines, licences and install.
"""
__version__ = "1.0.0"

from . import cast, config, engines, lipsync, robotfx, script, voice  # noqa: F401
