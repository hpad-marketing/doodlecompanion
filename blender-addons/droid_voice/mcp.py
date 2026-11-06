"""MCP tool for the add-on's MCP server, so a thread can voice lines on the PC.
Register TOOL and call handle(args). Voicebox also has its own MCP server at
http://127.0.0.1:17493/mcp for plain speak/transcribe."""
from . import cast, engines, voice

TOOL = {
    "name": "droid_voice",
    "description": "Voice droid lines with open-source TTS + robot processing. "
                   "action: status | cast | speak | takes | script | booth.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "cast", "speak", "takes", "script", "booth"]},
            "droid": {"type": "string", "description": "droid id or name (hazard, drone, computer, rx07...)"},
            "text": {"type": "string", "description": "line, or a whole script for action=script"},
            "take": {"type": "integer", "minimum": 0, "maximum": 2},
            "engine": {"type": "string", "description": "force an engine, e.g. kokoro, voicebox:chatterbox_turbo"},
            "dialogue_engine": {"type": "string", "enum": ["dia2"]},
            "wav": {"type": "string", "description": "recording path for action=booth"},
            "fps": {"type": "integer"},
        },
        "required": ["action"],
    },
}


def _slim(c):
    c = dict(c)
    ls = c.pop("lipsync", {})
    c["frames"] = len(ls.get("level", []))
    return c


def handle(a):
    act, fps = a["action"], int(a.get("fps", 24))
    if act == "status":
        return {k: {"ok": ok, "why": why} for k, (ok, why) in engines.status().items()}
    if act == "cast":
        return cast.load()
    if act == "speak":
        return _slim(voice.speak(a["droid"], a["text"], take=int(a.get("take", 0)), engine=a.get("engine"), fps=fps))
    if act == "takes":
        return [_slim(c) for c in voice.takes(a["droid"], a["text"], fps=fps)]
    if act == "script":
        v = voice.voice_script(a["text"], fps=fps, dialogue_engine=a.get("dialogue_engine"))
        v["lines"] = [_slim(c) for c in v["lines"]]
        return v
    if act == "booth":
        return _slim(voice.booth(a["wav"], a["droid"], fps=fps))
    raise ValueError(f"unknown action {act}")
