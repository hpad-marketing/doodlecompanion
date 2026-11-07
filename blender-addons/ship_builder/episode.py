"""Episodes: the data spine of the Ship Studio episode workflow (approved 2026-11-06).

An episode is one folder:

    DeepInDoodles/ShipSitcom/Ep03_The_Leak/
        Ep03_The_Leak.mp4            the final, at the top
        episode.json                 script, beats, stations, notes
        work/shots  work/voices  work/stills  work/audio  work/publish

Droids, rooms and the hero ship are linked from their libraries, never copied.

This module has no UI and no Blender dependency, so every station (and the tests)
can use it:
    ep = Episode.new(root, "The Leak", template="malfunction")
    ep.script = "INT. OIL LOUNGE\\nRX-07: (worried) Is that oil? [points at the floor]"
    ep.parse()   -> scenes, lines, rooms, runtime, flags
    ep.save()
"""
import json
import os
import re
import time

STATIONS = ("write", "voice", "stage", "perform", "check", "render", "publish")
STATION_LABEL = {"write": "Write", "voice": "Voice", "stage": "Stage", "perform": "Perform", "check": "Check",
                 "render": "Render", "publish": "Publish"}
TRACKS = ("beats", "shots", "voices", "acting", "sound", "events")   # the same six in every station

# ------------------------------------------------------------------ cast
# key: (display name, colour, aliases, voice style, bible)
CAST = {
    "RX07": {"name": "RX-07", "color": (0.88, 0.65, 0.29), "aliases": ("RX-07", "RX07", "RX"),
             "voice": "cadence beeps", "wants": "to be useful", "fears": "being replaced",
             "speaks": "short, over-polite sentences", "words": True},
    "HAZARD": {"name": "Hazard", "color": (0.95, 0.78, 0.1), "aliases": ("HAZARD", "HAZ"),
               "voice": "bit-crushed talker", "wants": "to be in charge", "fears": "silence",
               "speaks": "loud, overconfident, wrong", "words": True},
    "DRONE": {"name": "Drone", "color": (0.35, 0.75, 1.0), "aliases": ("DRONE", "HOVER", "HOVER DRONE"),
              "voice": "chirps", "wants": "attention", "fears": "the dark",
              "speaks": "beeps and chirps only, never words", "words": False},
    "COMPUTER": {"name": "Ship computer", "color": (0.6, 0.62, 0.66), "aliases": ("COMPUTER", "SHIP", "SHIP COMPUTER"),
                 "voice": "deadpan vocoder", "wants": "nothing", "fears": "nothing",
                 "speaks": "deadpan announcements", "words": True, "body": False},   # a voice from the walls
}
BEEPS = re.compile(r"^[\s\W]*((beep|boop|bip|bweep|chirp|whirr|brrt|trill|meep|wee+|oo+)[\s\W]*)+$", re.I)

# ------------------------------------------------------------------ rooms from scene headings (W4)
HEADINGS = (
    (("OIL LOUNGE", "LOUNGE", "CREW LOUNGE"), "lounge"),
    (("COMMAND CENTRE", "COMMAND CENTER", "BRIDGE", "COCKPIT"), "bridge"),
    (("CORRIDOR", "HALLWAY", "PASSAGE"), "corridor"),
    (("CHARGING", "CHARGING STATIONS", "BEDROOM"), "charging"),
    (("REPAIR BAY", "REPAIR", "MED BAY", "MEDBAY", "INFIRMARY"), "repair"),
    (("OBSERVATION",), "observation"),
    (("ENGINE",), "engine"),
    (("CARGO",), "cargo"),
    (("AIRLOCK",), "airlock"),
    (("WORKSHOP", "FABRICATOR"), "workshop"),
    (("REST POD", "PODS", "BUNKS"), "rest"),
    (("JUNK", "RECYCLER"), "junk"),
    (("GARDEN", "PLANT ROOM", "HYDROPONICS"), "plants"),
)
EXTERIOR = "hero_ship"   # EXT. SHIP: a hero ship establishing shot (slot until the hero ship lands)

# ------------------------------------------------------------------ templates (W5)
BEAT_COLORS = {"Cold open": (0.55, 0.55, 0.6), "A plot": (0.88, 0.65, 0.29), "B plot": (0.35, 0.75, 1.0),
               "Fix": (0.4, 0.85, 0.5), "Tag": (0.85, 0.4, 0.55)}
TEMPLATES = {
    "malfunction": {"label": "Ship malfunction", "runtime": 300, "rooms": ["bridge", "corridor", "repair"],
                    "beats": [("Cold open", 0.1), ("A plot", 0.45), ("B plot", 0.2), ("Fix", 0.17), ("Tag", 0.08)],
                    "script": "INT. COMMAND CENTRE\nCOMPUTER: Minor anomaly detected.\nHAZARD: (happy) Minor means fine.\n"},
    "planet": {"label": "Strange planet", "runtime": 360, "rooms": ["bridge", "observation", "airlock"],
               "beats": [("Cold open", 0.1), ("A plot", 0.45), ("B plot", 0.2), ("Fix", 0.17), ("Tag", 0.08)],
               "script": "EXT. SHIP\nINT. OBSERVATION DECK\nRX-07: (calm) It is very... round.\n"},
    "rivalry": {"label": "Droid rivalry", "runtime": 300, "rooms": ["lounge", "charging", "corridor"],
                "beats": [("Cold open", 0.1), ("A plot", 0.4), ("B plot", 0.25), ("Fix", 0.17), ("Tag", 0.08)],
                "script": "INT. CHARGING STATIONS\nHAZARD: (annoyed) That is MY bay.\nRX-07: (calm) It has a number on it.\n"},
    "bottle": {"label": "Bottle episode", "runtime": 240, "rooms": ["lounge"],
               "beats": [("Cold open", 0.12), ("A plot", 0.6), ("Fix", 0.2), ("Tag", 0.08)],
               "script": "INT. OIL LOUNGE\nDRONE: (sleepy) bweep.\n"},
    "blank": {"label": "Blank", "runtime": 300, "rooms": [], "beats": [("Cold open", 0.1), ("A plot", 0.5), ("Fix", 0.3), ("Tag", 0.1)],
              "script": ""},
}

EMOTIONS = ("calm", "worried", "alarmed", "happy", "annoyed", "sleepy")
WPS = 2.6          # spoken words per second, for the runtime estimate
LAUGH = 0.9        # default laugh pause after a punchline (V4)
ACTION_S = 1.6     # an [action] or a plain action line
SCENE_S = 2.0      # an establishing beat per scene


def slug(title):
    s = re.sub(r"[^A-Za-z0-9]+", "_", title.strip()).strip("_")
    return s[:40] or "Untitled"


def cast_key(name):
    n = name.strip().upper()
    for k, c in CAST.items():
        if n == k or n in c["aliases"]:
            return k
    return None


def room_for(heading):
    h = heading.upper()
    if h.startswith("EXT"):
        return EXTERIOR
    for words, key in HEADINGS:
        if any(w in h for w in words):
            return key
    return None


LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 \-]{0,24}?)\s*:\s*(.+)$")
HEAD = re.compile(r"^\s*(INT|EXT|INT\./EXT|I/E)[\.\s]", re.I)


def parse(script):
    """Screenplay text -> {scenes, lines, runtime, flags}. (W1, W3, W4)

    Scene heading: INT. OIL LOUNGE / EXT. SHIP. Dialogue: NAME: text.
    [brackets] in a line are actions, (parentheses) an emotion. Any other text is an action line.
    """
    scenes, lines, flags = [], [], []
    scene = None
    for n, raw in enumerate(script.splitlines(), 1):
        t = raw.strip()
        if not t:
            continue
        if HEAD.match(t):
            scene = {"heading": t, "room": room_for(t), "line_no": n, "lines": []}
            if scene["room"] is None:
                flags.append({"line_no": n, "kind": "room", "text": f"No room matches \"{t}\""})
            scenes.append(scene)
            continue
        if scene is None:   # dialogue before any heading: an implied first scene
            scene = {"heading": "", "room": None, "line_no": n, "lines": []}
            scenes.append(scene)
        m = LINE.match(t)
        key = cast_key(m.group(1)) if m else None
        if m and key:
            body = m.group(2)
            emo = [e.strip().lower() for e in re.findall(r"\(([^)]*)\)", body)]
            acts = [a.strip() for a in re.findall(r"\[([^\]]*)\]", body)]
            spoken = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", body).strip()
            ln = {"kind": "dialogue", "who": key, "text": spoken, "emotion": next((e for e in emo if e in EMOTIONS), emo[0] if emo else "calm"),
                  "actions": acts, "line_no": n, "scene": len(scenes) - 1}
            if not CAST[key]["words"] and spoken and not BEEPS.match(spoken):
                flags.append({"line_no": n, "kind": "bible", "text": f"{CAST[key]['name']} only beeps: \"{spoken}\""})
            if emo and emo[0] not in EMOTIONS:
                flags.append({"line_no": n, "kind": "emotion", "text": f"Unknown emotion ({emo[0]}): pick one of {', '.join(EMOTIONS)}"})
        elif m and not key and m.group(1).isupper():
            ln = {"kind": "dialogue", "who": None, "text": m.group(2), "emotion": "calm", "actions": [], "line_no": n, "scene": len(scenes) - 1}
            flags.append({"line_no": n, "kind": "cast", "text": f"Unknown speaker {m.group(1)}"})
        else:
            ln = {"kind": "action", "who": None, "text": t.strip("[]"), "emotion": None, "actions": [t.strip("[]")],
                  "line_no": n, "scene": len(scenes) - 1}
        lines.append(ln)
        scene["lines"].append(len(lines) - 1)
    return {"scenes": scenes, "lines": lines, "runtime": estimate(scenes, lines), "flags": flags}


def line_seconds(ln, laugh=LAUGH):
    if ln["kind"] == "action":
        return ACTION_S
    words = len(re.findall(r"\w+", ln["text"]))
    s = max(0.8, words / WPS) + ACTION_S * 0.5 * len(ln["actions"])
    if ln["text"].rstrip().endswith(("!", "?")) or ln.get("punchline"):
        s += laugh
    return s


def estimate(scenes, lines, laugh=LAUGH):
    return round(SCENE_S * len(scenes) + sum(line_seconds(l, laugh) for l in lines), 1)


# ------------------------------------------------------------------ the episode
class Episode:
    def __init__(self, folder):
        self.folder = folder
        self.data = {}

    # ---- files (A4)
    @staticmethod
    def library(root):
        return os.path.join(root, "ShipSitcom")

    @classmethod
    def new(cls, root, title, template="blank", number=None):
        lib = cls.library(root)
        os.makedirs(lib, exist_ok=True)
        if number is None:
            nums = [int(m.group(1)) for d in os.listdir(lib) for m in [re.match(r"Ep(\d+)_", d)] if m]
            number = max(nums, default=0) + 1
        folder = os.path.join(lib, f"Ep{number:02d}_{slug(title)}")
        for sub in ("shots", "voices", "stills", "audio", "publish"):
            os.makedirs(os.path.join(folder, "work", sub), exist_ok=True)
        tp = TEMPLATES.get(template, TEMPLATES["blank"])
        ep = cls(folder)
        ep.data = {"number": number, "title": title, "template": template, "created": time.time(),
                   "runtime_target": tp["runtime"], "rooms": list(tp["rooms"]), "script": tp["script"],
                   "beats": beats_from(tp["beats"]), "stations": {s: "todo" for s in STATIONS},
                   "laugh_pause": LAUGH, "notes": [], "links": {"droids": [], "hero_ship": None}}
        ep.parse()
        ep.save()
        return ep

    @classmethod
    def load(cls, folder):
        ep = cls(folder)
        with open(os.path.join(folder, "episode.json"), encoding="utf-8") as f:
            ep.data = json.load(f)
        return ep

    @classmethod
    def all(cls, root):
        lib = cls.library(root)
        out = []
        if os.path.isdir(lib):
            for d in sorted(os.listdir(lib)):
                if os.path.isfile(os.path.join(lib, d, "episode.json")):
                    try:
                        out.append(cls.load(os.path.join(lib, d)))
                    except (OSError, ValueError):
                        pass
        return out

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        tmp = os.path.join(self.folder, "episode.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.folder, "episode.json"))

    def path(self, *parts):
        return os.path.join(self.folder, *parts)

    @property
    def name(self):
        return os.path.basename(self.folder)

    @property
    def final(self):
        return self.path(self.name + ".mp4")

    # ---- script (W1)
    @property
    def script(self):
        return self.data.get("script", "")

    @script.setter
    def script(self, text):
        self.data["script"] = text

    def parse(self):
        p = parse(self.script)
        self.data["parsed"] = p
        if p["lines"]:
            self.set_station("write", "doing" if self.data["stations"].get("write") == "todo" else self.data["stations"]["write"])
        return p

    # ---- beats (W2)
    def beat_spans(self, total=None):
        """[(name, color, start_s, end_s)] laid over the runtime."""
        total = total or self.data.get("parsed", {}).get("runtime") or self.data.get("runtime_target", 300)
        out, t = [], 0.0
        for b in self.data["beats"]:
            d = b["share"] * total
            out.append((b["name"], tuple(b["color"]), round(t, 2), round(t + d, 2)))
            t += d
        return out

    def chapters(self):
        """YouTube chapters (U2) from the beat map: '0:00 Cold open' ..."""
        out = []
        for name, _c, s, _e in self.beat_spans():
            m, sec = divmod(int(s), 60)
            out.append(f"{m}:{sec:02d} {name}")
        return out

    # ---- stations (A1, A2)
    def set_station(self, key, state):
        assert key in STATIONS and state in ("todo", "doing", "done")
        self.data["stations"][key] = state

    def progress(self):
        return [(s, self.data["stations"].get(s, "todo")) for s in STATIONS]

    def next_station(self):
        return next((s for s, st in self.progress() if st != "done"), "publish")


def beats_from(pairs):
    tot = sum(s for _, s in pairs) or 1.0
    return [{"name": n, "share": s / tot, "color": list(BEAT_COLORS.get(n, (0.6, 0.6, 0.6)))} for n, s in pairs]


def resize_beat(beats, i, new_share):
    """Drag a beat wider or narrower; its right-hand neighbour gives or takes the difference (W2)."""
    if i >= len(beats) - 1:
        i, j = i, i - 1
    else:
        j = i + 1
    pair = beats[i]["share"] + beats[j]["share"]
    new_share = max(0.02, min(pair - 0.02, new_share))
    beats[i]["share"], beats[j]["share"] = new_share, pair - new_share
    return beats
