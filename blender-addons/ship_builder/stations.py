"""Ship Studio episode stations: the window's station bar, the seven stations,
the episodes board and the six-track timeline drawn over the Timeline.

The station bar sits on top of the Ship Studio panel: Library, Episodes, then
Write, Voice, Stage, Perform, Check, Render and Publish (keys 1 to 7 over the
preview). Each station shows a ring: done, in progress or not started. The same
timeline (beats, shots, voices, acting, sound, ship events) is drawn in every
station; the playhead and zoom are Blender's own, so they stay put.
"""
import os
import subprocess
import sys
import threading

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from . import episode as E
from . import episode_flow as F
from . import catalog as Cat
from . import queue_runner as Q
from .rooms import ROOMS

_EP = {"ep": None, "folder": None}
_ICONS = {}
_JOBS = {"proc": None, "label": "", "log": ""}
STATION_KEYS = ("LIBRARY", "BOARD") + tuple(s.upper() for s in E.STATIONS)
RING = {"done": "CHECKMARK", "doing": "TIME", "todo": "RADIOBUT_OFF"}
STATION_ICON = {"WRITE": "TEXT", "VOICE": "SPEAKER", "STAGE": "CAMERA_DATA", "PERFORM": "ARMATURE_DATA",
                "CHECK": "VIEWZOOM", "RENDER": "RENDER_ANIMATION", "PUBLISH": "EXPORT"}


def _studio():
    from . import studio
    return studio


def root():
    p = _studio().prefs()
    return bpy.path.abspath(p.deep_root) if p else os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles")


def ep():
    f = st().folder
    if not f:
        return None
    if _EP["folder"] != f or _EP["ep"] is None:
        try:
            _EP["ep"], _EP["folder"] = E.Episode.load(f), f
        except (OSError, ValueError):
            _EP["ep"], _EP["folder"] = None, None
    return _EP["ep"]


def save():
    e = _EP["ep"]
    if e is not None:
        e.save()


def st(ctx=None):
    return (ctx or bpy.context).window_manager.sb_ep


# ------------------------------------------------------------------ picture chips (generated images)
def chip(name, rgb, size=64):
    """A flat colour picture used where a library has no thumbnail yet (cast, emotions, events)."""
    key = f"SB Chip {name}"
    im = bpy.data.images.get(key)
    if im is None:
        im = bpy.data.images.new(key, size, size)
        im.generated_color = (*rgb[:3], 1)
        im.use_fake_user = True
    im.preview_ensure()
    return im.preview.icon_id


def picture(path, fallback_rgb=(0.3, 0.3, 0.32)):
    pc = _studio()._PCOLL["main"]
    if path and pc is not None and os.path.isfile(path):
        key = f"{path}|{os.path.getmtime(path)}"
        if key not in pc:
            try:
                pc.load(key, path, "IMAGE")
            except (RuntimeError, KeyError):
                return chip(os.path.basename(path), fallback_rgb)
        return pc[key].icon_id
    return chip(str(fallback_rgb), fallback_rgb)


def room_icon(key):
    p = _studio().prefs()
    it = next((i for i in Cat.items("ROOMS", p) if i.id == key), None)
    return picture(it.thumb if it else None, (0.2, 0.26, 0.3))


# ------------------------------------------------------------------ state
def _station_items(self, ctx):
    out = [("LIBRARY", "Library", "Sets, rooms, droids, props", "ASSET_MANAGER", 0),
           ("BOARD", "Episodes", "Every episode as a card", "SEQ_STRIP_DUPLICATE", 1)]
    for n, s in enumerate(E.STATIONS):
        out.append((s.upper(), f"{n + 1} {E.STATION_LABEL[s]}", f"Station {n + 1}: {E.STATION_LABEL[s]}", STATION_ICON[s.upper()], n + 2))
    return out


def _templates(self, ctx):
    return [(k, v["label"], f"{v['runtime'] // 60} min, rooms: {', '.join(v['rooms']) or 'pick later'}") for k, v in E.TEMPLATES.items()]


def _layer_update(self, ctx):
    e = ep()
    if e:
        F.acting_layers(e)[self.key] = {"on": self.on, "strength": round(self.strength, 3)}
        save()


class SB_Layer(bpy.types.PropertyGroup):
    key: StringProperty()
    label: StringProperty()
    on: BoolProperty(default=True, update=_layer_update)
    strength: FloatProperty(default=0.5, min=0.0, max=1.0, subtype="FACTOR", update=_layer_update)


def _laugh_update(self, ctx):
    e = ep()
    if e:
        e.data["laugh_pause"] = round(self.laugh, 2)
        F.retime(e)
        save()


class SB_EpState(bpy.types.PropertyGroup):
    station: EnumProperty(name="Station", items=_station_items)
    folder: StringProperty(name="Episode folder")
    new_title: StringProperty(name="Title", default="New episode")
    template: EnumProperty(name="Template", items=_templates)
    laugh: FloatProperty(name="Laugh pause", default=0.9, min=0.0, max=3.0, step=10, unit="TIME_ABSOLUTE", update=_laugh_update)
    mode: EnumProperty(name="Quality", items=[("draft", "Draft", "EEVEE 720p, minutes, for review"),
                                               ("final", "Final", "Cycles 4K overnight on Sushi (OptiX)")])
    headline: StringProperty(name="Headline", default="")
    thumb: IntProperty(name="Thumbnail", default=0)
    layers: CollectionProperty(type=SB_Layer)
    show_bible: BoolProperty(name="Story bible", default=False)
    font: StringProperty(name="Headline font", subtype="FILE_PATH", default="C:/Windows/Fonts/arialbd.ttf")


def sync_layers(ctx):
    e = ep()
    s = st(ctx)
    if not e:
        return
    cur = F.acting_layers(e)
    if len(s.layers) != len(F.ACTING):
        s.layers.clear()
        for k, lab, _d in F.ACTING:
            it = s.layers.add()
            it.key, it.label = k, lab
    for it in s.layers:
        v = cur[it.key]
        if it.on != v["on"]:
            it.on = v["on"]
        if abs(it.strength - v["strength"]) > 1e-4:
            it.strength = v["strength"]


# ------------------------------------------------------------------ background jobs (ffmpeg, voice)
def run_bg(label, fn):
    def work():
        _JOBS["label"] = label
        try:
            _JOBS["log"] = fn() or f"{label}: done"
        except Exception as e:   # surfaced in the panel, never a crash
            _JOBS["log"] = f"{label} failed: {e}"
        _JOBS["label"] = ""
    t = threading.Thread(target=work, daemon=True)
    _JOBS["proc"] = t
    t.start()


def busy():
    return bool(_JOBS["proc"] and _JOBS["proc"].is_alive())


def ffmpeg():
    for c in (os.environ.get("FFMPEG"), "ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if c:
            try:
                subprocess.run([c, "-version"], capture_output=True, check=True)
                return c
            except (OSError, subprocess.CalledProcessError):
                continue
    return None


def droid_voice():
    """droid_voice.voice when the Droid Voice add-on is installed (PR #76)."""
    for name, mod in list(sys.modules.items()):
        if name.endswith("droid_voice.voice") and hasattr(mod, "speak"):
            return mod
    try:
        import droid_voice.voice as v   # noqa
        return v
    except Exception:
        return None


# ------------------------------------------------------------------ operators
class SHIP_OT_station(bpy.types.Operator):
    """Go to this station"""
    bl_idname = "ship.station"
    bl_label = "Station"
    station: StringProperty()
    step: IntProperty(default=0)

    def execute(self, ctx):
        s = st(ctx)
        if self.station:
            s.station = self.station
        if self.station in ("WRITE",):
            _show_script(ctx)
        else:
            _show_preview(ctx)
        sync_layers(ctx)
        return {"FINISHED"}


def _preview_area(ctx):
    for a in ctx.window.screen.areas:
        if a.type in ("IMAGE_EDITOR", "TEXT_EDITOR") and (a.type == "TEXT_EDITOR" or (a.spaces.active.image and a.spaces.active.image.get("sb_preview"))):
            return a
    return None


def _script_text(e):
    name = f"{e.name} script"
    t = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    if t.as_string() != e.script:
        t.from_string(e.script)
    return t


def _show_script(ctx):
    e, a = ep(), _preview_area(ctx)
    if not e or not a:
        return
    t = _script_text(e)
    a.ui_type = "TEXT_EDITOR"
    sp = a.spaces.active
    sp.text = t
    sp.show_region_ui = True
    sp.show_line_numbers = True
    sp.show_word_wrap = True
    sp.font_size = 16


def _show_preview(ctx):
    a = _preview_area(ctx)
    if a and a.type == "TEXT_EDITOR":
        a.ui_type = "IMAGE_EDITOR"
        sp = a.spaces.active
        sp.image = _studio()._placeholder()
        sp.show_region_ui = True


class SHIP_OT_ep_new(bpy.types.Operator):
    """Start a new episode from this template card"""
    bl_idname = "ship.ep_new"
    bl_label = "New episode"
    template: StringProperty(default="blank")

    def execute(self, ctx):
        s = st(ctx)
        e = E.Episode.new(root(), s.new_title or "New episode", template=self.template)
        s.folder = e.folder
        _EP["ep"], _EP["folder"] = e, e.folder
        s.station = "WRITE"
        _show_script(ctx)
        return {"FINISHED"}


class SHIP_OT_ep_open(bpy.types.Operator):
    """Open this episode at the station the dot shows"""
    bl_idname = "ship.ep_open"
    bl_label = "Open episode"
    folder: StringProperty()
    station: StringProperty(default="")

    def execute(self, ctx):
        s = st(ctx)
        s.folder = self.folder
        _EP["ep"] = None
        e = ep()
        if e is None:
            self.report({"ERROR"}, "Could not read that episode")
            return {"CANCELLED"}
        s.station = self.station or e.next_station().upper()
        s.laugh = e.data.get("laugh_pause", E.LAUGH)
        sync_layers(ctx)
        if s.station == "WRITE":
            _show_script(ctx)
        else:
            _show_preview(ctx)
        blend = e.path("work", e.name + ".blend")
        if os.path.isfile(blend) and bpy.data.filepath != blend:
            self.report({"INFO"}, f"Episode file: {blend} (File › Open to load its scenes)")
        return {"FINISHED"}


class SHIP_OT_ep_script(bpy.types.Operator):
    """Read the script page: speakers, emotions, actions, rooms, runtime and story-bible flags"""
    bl_idname = "ship.ep_script"
    bl_label = "Update from script"

    def execute(self, ctx):
        e = ep()
        if not e:
            return {"CANCELLED"}
        t = bpy.data.texts.get(f"{e.name} script")
        if t:
            e.script = t.as_string()
        p = e.parse()
        F.retime(e)
        save()
        self.report({"INFO"}, f"{len(p['scenes'])} scenes, {len(p['lines'])} lines, about {int(p['runtime'] // 60)}:{int(p['runtime'] % 60):02d}")
        return {"FINISHED"}


class SHIP_OT_ep_beat(bpy.types.Operator):
    """Drag this beat wider or narrower (its neighbour gives or takes the time)"""
    bl_idname = "ship.ep_beat"
    bl_label = "Resize beat"
    index: IntProperty()
    delta: FloatProperty(default=0.02)

    def execute(self, ctx):
        e = ep()
        E.resize_beat(e.data["beats"], self.index, e.data["beats"][self.index]["share"] + self.delta)
        save()
        return {"FINISHED"}


def _room_enum(self, ctx):
    return [(k, m.INFO["label"], "") for k, m in ROOMS.items()] + [(E.EXTERIOR, "Hero ship (exterior)", "")]


class SHIP_OT_ep_room(bpy.types.Operator):
    """Swap the room this scene plays in"""
    bl_idname = "ship.ep_room"
    bl_label = "Swap room"
    bl_property = "room"
    scene: IntProperty()
    room: EnumProperty(items=_room_enum)

    def invoke(self, ctx, ev):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        e = ep()
        sc = e.data["parsed"]["scenes"][self.scene]
        lab = ROOMS[self.room].INFO["label"].upper() if self.room in ROOMS else "SHIP"
        lines = e.script.splitlines()
        n = sc["line_no"] - 1
        if 0 <= n < len(lines) and E.HEAD.match(lines[n]):
            lines[n] = ("EXT. " if self.room == E.EXTERIOR else "INT. ") + lab
            e.script = "\n".join(lines)
            t = bpy.data.texts.get(f"{e.name} script")
            if t:
                t.from_string(e.script)
        e.parse()
        save()
        return {"FINISHED"}


class SHIP_OT_ep_bible(bpy.types.Operator):
    """Edit this droid's card in the story bible"""
    bl_idname = "ship.ep_bible"
    bl_label = "Story bible card"
    who: StringProperty()
    wants: StringProperty(name="Wants")
    fears: StringProperty(name="Fears")
    speaks: StringProperty(name="Speaks")

    def invoke(self, ctx, ev):
        b = F.load_bible(root())["cast"].get(self.who, {})
        self.wants, self.fears, self.speaks = b.get("wants", ""), b.get("fears", ""), b.get("speaks", "")
        return ctx.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, ctx):
        b = F.load_bible(root())
        b["cast"][self.who] = {"wants": self.wants, "fears": self.fears, "speaks": self.speaks}
        F.save_bible(root(), b)
        return {"FINISHED"}


class SHIP_OT_ep_gag(bpy.types.Operator):
    """Add a running gag; cue words find the episodes it shows up in"""
    bl_idname = "ship.ep_gag"
    bl_label = "Add running gag"
    name: StringProperty(name="Gag")
    cues: StringProperty(name="Cue words", description="Comma separated words that mark the gag in a script")

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, ctx):
        b = F.load_bible(root())
        b["gags"].append({"name": self.name, "cues": [c.strip() for c in self.cues.split(",") if c.strip()]})
        F.save_bible(root(), b)
        return {"FINISHED"}


# ---- voice
class SHIP_OT_ep_voice(bpy.types.Operator):
    """Send the script to the droid voices: every line, three takes each"""
    bl_idname = "ship.ep_voice"
    bl_label = "Voice every line"
    only_changed: BoolProperty(default=False)

    def execute(self, ctx):
        e = ep()
        if not e or busy():
            return {"CANCELLED"}
        dv = droid_voice()
        speak = (lambda d, text, take, fps: dv.speak(d, text, take=take, fps=fps)) if dv else None
        if dv is None:
            self.report({"WARNING"}, "Droid Voice isn't installed: timing guides only, no audio yet")

        def go():
            n = F.voice_lines(e, speak, only_changed=self.only_changed)
            F.retime(e)
            save()
            return f"Voiced {n} lines" + ("" if dv else " (timing guides)")
        run_bg("Voicing", go)
        return {"FINISHED"}


class SHIP_OT_ep_take(bpy.types.Operator):
    """Use this take (↻ makes three fresh ones)"""
    bl_idname = "ship.ep_take"
    bl_label = "Take"
    line: IntProperty()
    take: IntProperty()

    def execute(self, ctx):
        e = ep()
        if self.take < 0:   # fresh takes
            dv = droid_voice()
            v = e.data.get("voices", {}).get(str(self.line))
            if dv and v:
                ln = next(l for l in e.data["parsed"]["lines"] if l["line_no"] == self.line)
                base = len(v["takes"])
                v["takes"] = [{"wav": c.get("robot"), "duration": c["duration"], "lipsync": c.get("lipsync")}
                              for c in (dv.speak(F.VOICE_ID.get(ln["who"], ln["who"].lower()), ln["text"], take=base + t, refresh=True) for t in range(3))]
                v["pick"] = 0
        else:
            F.pick_take(e, self.line, self.take)
            v = e.data.get("voices", {}).get(str(self.line))
            wav = v and v["takes"][self.take].get("wav")
            if wav and os.path.isfile(wav):
                _play(wav)
        F.retime(e)   # only this clip re-times; everything after it shifts along
        save()
        return {"FINISHED"}


_SOUND = {"handle": None}


def _play(path):
    try:
        import aud
        dev = aud.Device()
        if _SOUND["handle"] is not None:
            _SOUND["handle"].stop()
        _SOUND["handle"] = dev.play(aud.Sound(path))
    except Exception as e:
        print("play:", e)


class SHIP_OT_ep_sample(bpy.types.Operator):
    """Hear this droid's voice"""
    bl_idname = "ship.ep_sample"
    bl_label = "Hear voice"
    who: StringProperty()

    def execute(self, ctx):
        dv = droid_voice()
        if not dv:
            self.report({"WARNING"}, "Droid Voice isn't installed yet")
            return {"CANCELLED"}
        line = {"RX07": "Good morning. I have polished the floor.", "HAZARD": "I am in charge now!",
                "DRONE": "bweep bweep", "COMPUTER": "Minor anomaly detected."}.get(self.who, "Hello.")
        c = dv.speak(F.VOICE_ID.get(self.who, self.who.lower()), line)
        _play(c.get("robot") or c.get("dry"))
        return {"FINISHED"}


# ---- stage
class SHIP_OT_ep_build(bpy.types.Operator):
    """Build every room the script uses, put the droids on their marks and give every shot its camera"""
    bl_idname = "ship.ep_build"
    bl_label = "Build scenes and shots"
    coverage: BoolProperty(default=True)

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        if not e:
            return {"CANCELLED"}
        F.retime(e)
        if self.coverage or not e.data.get("shots"):
            F.coverage(e)
        rep = X.build(e, _studio().prefs())
        _save_blend(e)
        save()
        ed = bpy.data.scenes.get(X.EDIT.format(ep=X.short(e)))
        if ed and ctx.window:
            ctx.window.scene = ed
        msg = f"{len(rep['rooms'])} rooms, {rep['cams']} shot cameras"
        if rep["warnings"]:
            msg += f", {len(rep['warnings'])} cross the 180° line"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


def _save_blend(e):
    path = e.path("work", e.name + ".blend")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=bpy.data.filepath not in ("", path))
    except RuntimeError as ex:
        print("save episode file:", ex)
    return path


PRESETS = list(dict.fromkeys(list(F.SITCOM_PACK.values()) + ["Over the shoulder", "Low hero", "High worried", "Dutch beat",
                                                            "Slow push in", "Whip pan", "Crash zoom"]))


def _preset_enum(self, ctx):
    return [(p, p, "") for p in PRESETS]


class SHIP_OT_ep_shot(bpy.types.Operator):
    """Swap this shot's Director preset"""
    bl_idname = "ship.ep_shot"
    bl_label = "Swap shot"
    bl_property = "preset"
    shot: StringProperty()
    preset: EnumProperty(items=_preset_enum)

    def invoke(self, ctx, ev):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        F.swap_shot(ep(), self.shot, self.preset)
        save()
        return {"FINISHED"}


class SHIP_OT_ep_jump(bpy.types.Operator):
    """Go to this shot: playhead to its start, its camera live"""
    bl_idname = "ship.ep_jump"
    bl_label = "Go to shot"
    shot: StringProperty()

    def execute(self, ctx):
        e = ep()
        s = next((x for x in e.data.get("shots", []) if x["id"] == self.shot), None)
        if not s:
            return {"CANCELLED"}
        sc = bpy.data.scenes.get(s.get("scene_name") or "")
        if sc and ctx.window:
            ctx.window.scene = sc
            cam = bpy.data.objects.get(s.get("camera") or "")
            if cam:
                sc.camera = cam
        ctx.scene.frame_set(int(round(s["start"] * 24)) + 1)
        return {"FINISHED"}


class SHIP_OT_ep_exterior(bpy.types.Operator):
    """Drop an exterior hero ship shot at the playhead"""
    bl_idname = "ship.ep_exterior"
    bl_label = "Exterior cutaway"
    preset: StringProperty()

    def execute(self, ctx):
        e = ep()
        t = (ctx.scene.frame_current - 1) / 24
        si = max([s["scene"] for s in e.data.get("shots", []) if s["start"] <= t] or [0])
        e.data.setdefault("shots", []).append({"id": f"X{len(e.data['shots']) + 1:03d}", "preset": self.preset, "kind": "exterior",
                                               "scene": si, "start": round(t, 3), "end": round(t + 2.0, 3), "subject": None, "locked": True})
        e.data["shots"].sort(key=lambda s: s["start"])
        save()
        return {"FINISHED"}


class SHIP_OT_ep_blocking(bpy.types.Operator):
    """Top-down blocking map of this scene's room: marks, paths round the furniture, camera cones"""
    bl_idname = "ship.ep_blocking"
    bl_label = "Blocking map"

    def execute(self, ctx):
        for a in ctx.window.screen.areas:
            if a.type == "VIEW_3D":
                r3 = a.spaces.active.region_3d
                r3.view_perspective = "ORTHO"
                with ctx.temp_override(area=a, region=next(r for r in a.regions if r.type == "WINDOW")):
                    bpy.ops.view3d.view_axis(type="TOP")
                    bpy.ops.view3d.view_all()
                a.spaces.active.overlay.show_extras = True
                BLOCK["on"] = True
                a.tag_redraw()
                break
        return {"FINISHED"}


class SHIP_OT_ep_animatic(bpy.types.Operator):
    """Play from here: a fast 540p EEVEE animatic of the edit with the voices"""
    bl_idname = "ship.ep_animatic"
    bl_label = "Animatic"

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        ed = bpy.data.scenes.get(X.EDIT.format(ep=X.short(e))) if e else None
        if ed is None:
            self.report({"ERROR"}, "Build scenes and shots first")
            return {"CANCELLED"}
        ctx.window.scene = ed
        r = ed.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 540, 100
        r.image_settings.file_format = "FFMPEG"
        r.ffmpeg.format, r.ffmpeg.codec, r.ffmpeg.audio_codec = "MPEG4", "H264", "AAC"
        r.filepath = e.path("work", e.name + "_animatic.mp4")
        r.use_file_extension = False
        for s in bpy.data.scenes:
            if s.name.startswith(X.short(e) + " · ") and s is not ed:
                names = [x.identifier for x in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
                s.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in names else "BLENDER_EEVEE"
        bpy.ops.render.opengl("INVOKE_DEFAULT", animation=True, sequencer=True)
        return {"FINISHED"}


# ---- perform
class SHIP_OT_ep_act(bpy.types.Operator):
    """Run every switched-on acting layer on every shot (your own keys always override them)"""
    bl_idname = "ship.ep_act"
    bl_label = "Apply to episode"

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        n = X.apply_acting(e)
        X.apply_events(e)
        save()
        self.report({"INFO"}, f"Acted {n} lines")
        return {"FINISHED"}


class SHIP_OT_ep_emotion(bpy.types.Operator):
    """Set this line's emotion: swaps its pose set and LED colour"""
    bl_idname = "ship.ep_emotion"
    bl_label = "Emotion"
    line: IntProperty()
    emotion: StringProperty()

    def execute(self, ctx):
        F.set_emotion(ep(), self.line, self.emotion)
        save()
        return {"FINISHED"}


class SHIP_OT_ep_event(bpy.types.Operator):
    """Drop this ship event at the playhead: it drives lights, props, screens and sound together"""
    bl_idname = "ship.ep_event"
    bl_label = "Ship event"
    kind: StringProperty()

    def execute(self, ctx):
        F.add_event(ep(), self.kind, (ctx.scene.frame_current - 1) / 24)
        save()
        return {"FINISHED"}


class SHIP_OT_ep_puppet(bpy.types.Operator):
    """Loop this line and perform over it with the DualSense: left stick walks, right stick looks, R2 grabs, △ plays a gesture"""
    bl_idname = "ship.ep_puppet"
    bl_label = "Puppet a take"

    def execute(self, ctx):
        e = ep()
        ln = line_at(e, ctx.scene.frame_current)
        if ln:
            ctx.scene.frame_preview_start = int(ln["start"] * 24) + 1
            ctx.scene.frame_preview_end = int(ln["end"] * 24) + 12
            ctx.scene.use_preview_range = True
        try:
            bpy.ops.ship.walk_here("INVOKE_DEFAULT")
        except RuntimeError as ex:
            self.report({"WARNING"}, str(ex))
        return {"FINISHED"}


def line_at(e, frame):
    t = (frame - 1) / 24
    for x in e.data.get("timing", []) if e else []:
        if x["start"] - 0.2 <= t <= x["end"] + 0.4 and x["kind"] == "dialogue":
            return x
    return None


# ---- check
class SHIP_OT_ep_check(bpy.types.Operator):
    """Run the episode checks. They only report, never block"""
    bl_idname = "ship.ep_check"
    bl_label = "Check episode"

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        res = X.run_check(e)
        chips = F.check_chips(e, res)
        save()
        bad = sum(len(v) for _k, _l, v in chips)
        self.report({"INFO"} if not bad else {"WARNING"}, "All clear" if not bad else f"{bad} things to look at")
        return {"FINISHED"}


class SHIP_OT_ep_stills(bpy.types.Operator):
    """One GPU still per shot, in a grid. Approve them all to unlock a clean render"""
    bl_idname = "ship.ep_stills"
    bl_label = "Render stills"
    every10: BoolProperty(default=False)

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        d = e.path("work", "stills")
        os.makedirs(d, exist_ok=True)
        n = 0
        for s in e.data.get("shots", []):
            if X.render_still(e, s["id"], os.path.join(d, s["id"] + ".png")):
                n += 1
        save()
        self.report({"INFO"}, f"{n} stills in {d}")
        return {"FINISHED"}


class SHIP_OT_ep_still(bpy.types.Operator):
    """Pin a note on this still, or approve it"""
    bl_idname = "ship.ep_still"
    bl_label = "Still"
    shot: StringProperty()
    note: StringProperty(name="Note")
    approve: BoolProperty(default=False)

    def invoke(self, ctx, ev):
        if self.approve:
            return self.execute(ctx)
        self.note = F.stills_state(ep()).get(self.shot, {}).get("note", "")
        return ctx.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, ctx):
        e = ep()
        s = e.data.setdefault("stills", {}).setdefault(self.shot, {"approved": False, "note": ""})
        if self.approve:
            s["approved"] = not s.get("approved")
        else:
            s["note"] = self.note
        save()
        return {"FINISHED"}


class SHIP_OT_ep_approve(bpy.types.Operator):
    """Approve every still: unlocks a clean render"""
    bl_idname = "ship.ep_approve"
    bl_label = "Approve all stills"

    def execute(self, ctx):
        F.approve_all(ep())
        save()
        return {"FINISHED"}


# ---- render
class SHIP_OT_ep_queue(bpy.types.Operator):
    """Send every shot to the Sushi render queue (a crash resumes from the last finished shot)"""
    bl_idname = "ship.ep_queue"
    bl_label = "Send to Sushi queue"

    def execute(self, ctx):
        e = ep()
        mode = st(ctx).mode
        if mode == "final" and not F.render_unlocked(e):
            self.report({"WARNING"}, "Approve the stills in Check first: Final waits for them")
            return {"CANCELLED"}
        blend = _save_blend(e)
        jobs, eta = F.queue_jobs(e, root(), blend, mode)
        save()
        Q.start(root(), bpy.app.binary_path)
        self.report({"INFO"}, f"{len(jobs)} shots queued, done about {eta}")
        return {"FINISHED"}


class SHIP_OT_ep_mix(bpy.types.Operator):
    """Cut the finished shots together and mix: voices panned and in the room, foley and tone under, music ducked, -14 LUFS"""
    bl_idname = "ship.ep_mix"
    bl_label = "Auto edit and mix"

    def execute(self, ctx):
        e = ep()
        ff = ffmpeg()
        if not ff:
            self.report({"ERROR"}, "ffmpeg not found")
            return {"CANCELLED"}
        plan = F.mix_plan(e, st(ctx).mode)
        missing = [v for v in plan["video"] if not os.path.isfile(v)]
        if missing:
            self.report({"WARNING"}, f"{len(missing)} shots still rendering")
            return {"CANCELLED"}
        argv = F.ffmpeg_mix(plan, ff)

        def go():
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError(r.stderr[-400:])
            e.set_station("render", "done")
            save()
            return f"Edit ready: {plan['out']}"
        run_bg("Editing and mixing", go)
        return {"FINISHED"}


# ---- publish
class SHIP_OT_ep_thumbs(bpy.types.Operator):
    """Render the six most expressive frames to pick a thumbnail from"""
    bl_idname = "ship.ep_thumbs"
    bl_label = "Find thumbnail frames"

    def execute(self, ctx):
        from . import ep_scene as X
        e = ep()
        d = e.path("work", "publish", "thumbs")
        os.makedirs(d, exist_ok=True)
        frames = F.thumbnail_frames(e)
        out = []
        for k, fr in enumerate(frames):
            t = (fr - 1) / 24
            s = next((x for x in e.data.get("shots", []) if x["start"] <= t <= x["end"] and x["kind"] != "exterior"), None)
            if not s:
                continue
            sc = bpy.data.scenes.get(s.get("scene_name") or "")
            cam = bpy.data.objects.get(s.get("camera") or "")
            if not sc:
                continue
            sc.camera = cam or sc.camera
            sc.frame_set(fr)
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 100
            p = os.path.join(d, f"cand_{k + 1}.png")
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True, scene=sc.name)
            out.append(p)
        e.data["thumb_candidates"] = out
        save()
        return {"FINISHED"}


class SHIP_OT_ep_thumb(bpy.types.Operator):
    """Use this frame and add the headline on a dark band"""
    bl_idname = "ship.ep_thumb"
    bl_label = "Make thumbnail"
    index: IntProperty()

    def execute(self, ctx):
        e = ep()
        s = st(ctx)
        c = e.data.get("thumb_candidates", [])
        if not c:
            return {"CANCELLED"}
        src = c[min(self.index, len(c) - 1)]
        out = e.path("work", "publish", "thumbnail.jpg")
        ff = ffmpeg()
        text = (s.headline or e.data.get("title", "")).replace("'", "’").replace(":", "\\:")
        font = s.font if os.path.isfile(s.font) else ""
        vf = "scale=1280:720,drawbox=y=ih*0.62:w=iw:h=ih*0.3:color=black@0.62:t=fill," \
             f"drawtext=text='{text}':fontcolor=0xE0A64B:fontsize=86:x=(w-text_w)/2:y=h*0.62+(h*0.3-text_h)/2" + (f":fontfile='{font}'" if font else "")
        if not ff:
            self.report({"ERROR"}, "ffmpeg not found")
            return {"CANCELLED"}
        r = subprocess.run([ff, "-y", "-i", src, "-vf", vf, "-q:v", "2", out], capture_output=True, text=True)
        if r.returncode:
            self.report({"ERROR"}, r.stderr[-200:])
            return {"CANCELLED"}
        e.data["thumbnail"] = out
        s.thumb = self.index
        save()
        return {"FINISHED"}


class SHIP_OT_ep_publish(bpy.types.Operator):
    """Make the upload pack: final, thumbnail, title, description, tags, chapters, captions, end screen and the Shorts"""
    bl_idname = "ship.ep_publish"
    bl_label = "Make upload pack"

    def execute(self, ctx):
        e = ep()
        final = e.final if os.path.isfile(e.final) else e.path("work", f"{e.name}_draft.mp4")
        ff = ffmpeg()

        def go():
            shorts = []
            if ff and os.path.isfile(final):
                for k, sh in enumerate(F.shorts(e), 1):
                    out = e.path("work", "publish", f"short_{k}.mp4")
                    subprocess.run(F.shorts_ffmpeg(final, sh, out, ff), capture_output=True)
                    shorts.append(out)
            pub = F.upload_pack(e, final if os.path.isfile(final) else None, e.data.get("thumbnail"), shorts)
            save()
            miss = e.data["publish"]["hi_missing"]
            return f"Upload pack: {pub}" + (f" (Hindi text missing on {len(miss)} lines)" if miss else "")
        run_bg("Making the upload pack", go)
        return {"FINISHED"}


class SHIP_OT_ep_youtube(bpy.types.Operator):
    """Upload the pack to your channel (needs a one-time Google sign-in; optional)"""
    bl_idname = "ship.ep_youtube"
    bl_label = "Upload to YouTube"
    privacy: EnumProperty(items=[("private", "Private", ""), ("unlisted", "Unlisted", ""), ("public", "Public", "")], default="private")
    schedule: StringProperty(name="Publish at (IST)", description="e.g. 2026-11-10 18:00, empty = now")

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, ctx):
        from . import youtube
        e = ep()
        ok, msg = youtube.ready(root())
        if not ok:
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        run_bg("Uploading to YouTube", lambda: youtube.upload(root(), e.path("work", "publish"), self.privacy, self.schedule))
        return {"FINISHED"}


# ---- rough cut (A5)
class SHIP_OT_ep_rough(bpy.types.Operator):
    """Rough cut from script: voices every line, picks rooms, blocks the droids, covers each scene, adds the auto acting and opens the animatic"""
    bl_idname = "ship.ep_rough"
    bl_label = "Rough cut from script"

    def execute(self, ctx):
        e = ep()
        if not e:
            return {"CANCELLED"}
        bpy.ops.ship.ep_script()
        dv = droid_voice()
        F.voice_lines(e, (lambda d, t, k, fps: dv.speak(d, t, take=k, fps=fps)) if dv else None)
        F.retime(e)
        F.coverage(e)
        bpy.ops.ship.ep_build(coverage=False)
        bpy.ops.ship.ep_act()
        bpy.ops.ship.ep_check()
        st(ctx).station = "CHECK"
        bpy.ops.ship.ep_animatic()
        save()
        return {"FINISHED"}


# ------------------------------------------------------------------ drawing
def draw_bar(L, ctx):
    s = st(ctx)
    e = ep()
    row = L.row(align=True)
    row.scale_y = 1.45
    for key, lab, ic in (("LIBRARY", "Library", "ASSET_MANAGER"), ("BOARD", "Episodes", "SEQ_STRIP_DUPLICATE")):
        row.operator("ship.station", text=lab, icon=ic, depress=s.station == key).station = key
    row.separator()
    prog = dict(e.progress()) if e else {}
    for n, sk in enumerate(E.STATIONS):
        icon = RING[prog.get(sk, "todo")] if e else STATION_ICON[sk.upper()]
        sub = row.row(align=True)
        sub.enabled = e is not None
        sub.operator("ship.station", text=f"{n + 1} {E.STATION_LABEL[sk]}", icon=icon, depress=s.station == sk.upper()).station = sk.upper()
    if e:
        r = L.row()
        r.label(text=f"{e.name.replace('_', ' ')}  ·  next: {E.STATION_LABEL[e.next_station()]}", icon="FILE_MOVIE")
        r.operator("ship.ep_rough", icon="PLAY")
    if busy() or _JOBS["log"]:
        L.label(text=_JOBS["label"] + "..." if busy() else _JOBS["log"], icon="SORTTIME" if busy() else "INFO")


def draw_board(L, ctx):
    s = st(ctx)
    L.label(text="New episode: pick a template card", icon="ADD")
    L.prop(s, "new_title")
    g = L.grid_flow(row_major=True, columns=5, even_columns=True, align=False)
    for k, t in E.TEMPLATES.items():
        c = g.column(align=True)
        c.template_icon(icon_value=room_icon(t["rooms"][0]) if t["rooms"] else chip("blank", (0.12, 0.12, 0.13)), scale=4.0)
        c.operator("ship.ep_new", text=t["label"]).template = k
        c.label(text=f"{t['runtime'] // 60} min · {len(t['beats'])} beats")
    L.separator()
    eps = E.Episode.all(root())
    L.label(text=f"Episodes ({len(eps)})  ·  {E.Episode.library(root())}", icon="FILE_FOLDER")
    g = L.grid_flow(row_major=True, columns=3, even_columns=True, align=False)
    for e in eps:
        box = g.box()
        still = next((os.path.join(e.path("work", "stills"), f) for f in sorted(os.listdir(e.path("work", "stills")))
                      if f.endswith(".png")), None) if os.path.isdir(e.path("work", "stills")) else None
        box.template_icon(icon_value=picture(e.data.get("thumbnail") or still, (0.15, 0.17, 0.2)), scale=5.0)
        op = box.operator("ship.ep_open", text=f"Ep {e.data.get('number', 0)}: {e.data.get('title', '')}")
        op.folder = e.folder
        dots = box.row(align=True)
        for n, (sk, state) in enumerate(e.progress()):
            o = dots.operator("ship.ep_open", text="", icon=RING[state])
            o.folder, o.station = e.folder, sk.upper()


def draw_write(L, ctx):
    e = ep()
    p = e.data.get("parsed", {})
    r = L.row(align=True)
    r.scale_y = 1.4
    r.operator("ship.ep_script", icon="FILE_REFRESH")
    rt = p.get("runtime", 0)
    r.label(text=f"Runtime about {int(rt // 60)}:{int(rt % 60):02d}  (target {e.data.get('runtime_target', 300) // 60} min)", icon="TIME")
    L.label(text="NAME: line · [action] · (emotion) · INT. ROOM heading", icon="INFO")
    cr = L.row(align=True)
    for k, c in E.CAST.items():
        col = cr.column(align=True)
        col.template_icon(icon_value=chip(f"cast {k}", c["color"]), scale=1.6)
        col.label(text=c["name"])
    # beat map strip
    L.label(text="Beat map (drag with - / +); becomes YouTube chapters", icon="SEQ_STRIP_META")
    beats = e.data["beats"]
    row = L.row(align=True)
    left = 1.0
    for i, b in enumerate(beats):
        f = b["share"] / left if i < len(beats) - 1 else 1.0
        sp = row.split(factor=max(0.05, min(0.95, f)), align=True)
        cell = sp.column(align=True)
        cell.template_icon(icon_value=chip(f"beat {b['name']}", b["color"]), scale=1.0)
        cell.label(text=b["name"])
        rr = cell.row(align=True)
        o = rr.operator("ship.ep_beat", text="", icon="REMOVE"); o.index, o.delta = i, -0.02
        o = rr.operator("ship.ep_beat", text="", icon="ADD"); o.index, o.delta = i, 0.02
        left -= b["share"]
        row = sp.row(align=True)
    # rooms from scene headings
    L.label(text="Rooms from scene headings (click to swap)", icon="HOME")
    g = L.grid_flow(row_major=True, columns=4, even_columns=True, align=False)
    for i, sc in enumerate(p.get("scenes", [])):
        c = g.column(align=True)
        c.template_icon(icon_value=room_icon(sc["room"]) if sc["room"] in ROOMS else chip("ext", (0.08, 0.1, 0.22)), scale=3.0)
        c.operator("ship.ep_room", text=(sc["heading"] or "No heading")[:28]).scene = i
    flags = p.get("flags", [])
    if flags:
        b = L.box()
        b.label(text=f"{len(flags)} script notes", icon="ERROR")
        for f in flags[:8]:
            b.label(text=f"line {f['line_no']}: {f['text']}")
    L.prop(st(ctx), "show_bible", icon="BOOKMARKS", toggle=True)
    if st(ctx).show_bible:
        bible = F.load_bible(root())
        g = L.grid_flow(row_major=True, columns=2, even_columns=True)
        for k, c in E.CAST.items():
            bx = g.box()
            hr = bx.row()
            hr.template_icon(icon_value=chip(f"cast {k}", c["color"]), scale=1.4)
            hr.operator("ship.ep_bible", text=c["name"], icon="GREASEPENCIL").who = k
            d = bible["cast"].get(k, {})
            for lab in ("wants", "fears", "speaks"):
                bx.label(text=f"{lab.title()}: {d.get(lab, '')}")
        gb = L.box()
        gr = gb.row()
        gr.label(text="Running gags", icon="LOOP_BACK")
        gr.operator("ship.ep_gag", text="", icon="ADD")
        for gg in F.gag_hits(root()):
            gb.label(text=f"{gg['name']}: {', '.join(x.split('_', 1)[0] for x in gg['episodes']) or 'not used yet'}")


def draw_voice(L, ctx):
    e = ep()
    s = st(ctx)
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_voice", text="Voice every line", icon="SPEAKER").only_changed = False
    r.operator("ship.ep_voice", text="Only changed lines", icon="FILE_REFRESH").only_changed = True
    L.prop(s, "laugh", slider=True)
    if not droid_voice():
        L.label(text="Droid Voice isn't installed: lines get silent timing guides", icon="ERROR")
    L.label(text="Cast voices", icon="USER")
    g = L.grid_flow(row_major=True, columns=4, even_columns=True)
    for k, c in E.CAST.items():
        col = g.column(align=True)
        col.template_icon(icon_value=chip(f"cast {k}", c["color"]), scale=3.0)
        col.operator("ship.ep_sample", text=f"▶ {c['name']}").who = k
        col.label(text=c["voice"])
    vo = e.data.get("voices", {})
    tm = {t["line_no"]: t for t in e.data.get("timing", [])}
    for ln in e.data.get("parsed", {}).get("lines", []):
        if ln["kind"] != "dialogue":
            continue
        b = L.box()
        hr = b.row()
        c = E.CAST.get(ln["who"], {"name": ln["who"] or "?", "color": (0.5, 0.5, 0.5)})
        hr.template_icon(icon_value=chip(f"cast {ln['who']}", c["color"]), scale=1.0)
        t = tm.get(ln["line_no"])
        hr.label(text=f"{c['name']}: {ln['text'][:60]}" + (f"   {t['start']:.1f}s" if t else ""))
        v = vo.get(str(ln["line_no"]))
        tr = b.row(align=True)
        if v:
            for k, tk in enumerate(v["takes"]):
                o = tr.operator("ship.ep_take", text=f"T{k + 1} {tk['duration']:.1f}s", depress=v["pick"] == k)
                o.line, o.take = ln["line_no"], k
            o = tr.operator("ship.ep_take", text="", icon="FILE_REFRESH")
            o.line, o.take = ln["line_no"], -1
        else:
            tr.label(text="not voiced yet", icon="RADIOBUT_OFF")


def draw_stage(L, ctx):
    e = ep()
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_build", icon="SCENE_DATA")
    r.operator("ship.ep_blocking", icon="VIEW_ORTHO")
    r.operator("ship.ep_animatic", text="Play from here", icon="PLAY")
    r.operator("ship.walk_here", text="", icon="CON_FOLLOWPATH")
    for w in e.data.get("blocking_warnings", []):
        L.label(text=w, icon="ERROR")
    L.label(text="Exterior cutaways (drop at the playhead)", icon="WORLD")
    g = L.grid_flow(row_major=True, columns=4, even_columns=True)
    for k, p in enumerate(F.EXTERIORS):
        c = g.column(align=True)
        c.template_icon(icon_value=chip(f"ext {k}", (0.06 + 0.05 * k, 0.08, 0.2 + 0.05 * k)), scale=2.5)
        c.operator("ship.ep_exterior", text=p.replace("Hero ship ", "").title()).preset = p
    L.label(text=f"Shots ({len(e.data.get('shots', []))}) · click to swap the preset", icon="CAMERA_DATA")
    g = L.grid_flow(row_major=True, columns=4, even_columns=True)
    stills = e.path("work", "stills")
    for s in e.data.get("shots", []):
        c = g.column(align=True)
        c.template_icon(icon_value=picture(os.path.join(stills, s["id"] + ".png"), (0.18, 0.2, 0.24)), scale=3.0)
        c.operator("ship.ep_jump", text=f"{s['id']} {s['start']:.1f}s").shot = s["id"]
        c.operator("ship.ep_shot", text=s["preset"][:22], icon="LOCKED" if s.get("locked") else "NONE").shot = s["id"]


def draw_perform(L, ctx):
    e = ep()
    s = st(ctx)
    sync_layers(ctx)
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_act", icon="ARMATURE_DATA")
    r.operator("ship.ep_puppet", icon="EVENT_GAMEPAD" if "EVENT_GAMEPAD" in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items else "OUTLINER_OB_ARMATURE")
    for it in s.layers:
        row = L.row(align=True)
        row.prop(it, "on", text="")
        sub = row.row(align=True)
        sub.active = it.on
        sub.prop(it, "strength", text=it.label, slider=True)
    ln = line_at(e, ctx.scene.frame_current)
    L.label(text="Emotion of the line under the playhead", icon="MONKEY")
    if ln:
        line = next(l for l in e.data["parsed"]["lines"] if l["line_no"] == ln["line_no"])
        cur = F.line_emotion(e, line)
        L.label(text=f"{E.CAST.get(line['who'], {}).get('name', '')}: {line['text'][:60]}")
        g = L.grid_flow(row_major=True, columns=6, even_columns=True, align=True)
        for emo in E.EMOTIONS:
            c = g.column(align=True)
            c.template_icon(icon_value=chip(f"emo {emo}", F.emotion_look(emo)["led"]), scale=1.6)
            o = c.operator("ship.ep_emotion", text=emo.title(), depress=emo == cur)
            o.line, o.emotion = line["line_no"], emo
    else:
        L.label(text="Move the playhead onto a line")
    L.label(text="Ship events (drop at the playhead)", icon="LIGHT_SUN")
    g = L.grid_flow(row_major=True, columns=5, even_columns=True)
    cols = {"shake": (0.4, 0.3, 0.2), "red_alert": (0.8, 0.08, 0.05), "lights_out": (0.03, 0.03, 0.05), "meteors": (0.5, 0.35, 0.15), "jump": (0.3, 0.5, 1.0)}
    for k, (lab, d, what) in F.EVENTS.items():
        c = g.column(align=True)
        c.template_icon(icon_value=chip(f"ev {k}", cols[k]), scale=2.5)
        c.operator("ship.ep_event", text=lab).kind = k


def draw_check(L, ctx):
    e = ep()
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_check", icon="VIEWZOOM")
    r.operator("ship.ep_stills", icon="RENDER_STILL")
    r.operator("ship.ep_approve", icon="CHECKMARK")
    chk = e.data.get("check", {})
    g = L.grid_flow(row_major=True, columns=6, even_columns=True, align=True)
    for k, lab in F.CHIPS:
        issues = chk.get(k)
        c = g.column(align=True)
        c.label(text=lab, icon="QUESTION" if issues is None else ("CHECKMARK" if not issues else "ERROR"))
        if issues:
            c.label(text=f"{len(issues)}")
            for sid, note in issues[:3]:
                if sid:
                    c.operator("ship.ep_jump", text=sid).shot = sid
                else:
                    c.label(text=note[:30])
    L.label(text="Stills: click to pin a note, tick to approve", icon="IMAGE")
    g = L.grid_flow(row_major=True, columns=4, even_columns=True)
    stills = e.path("work", "stills")
    sts = F.stills_state(e)
    for sid, v in sts.items():
        c = g.column(align=True)
        c.template_icon(icon_value=picture(os.path.join(stills, sid + ".png"), (0.18, 0.2, 0.24)), scale=3.0)
        rr = c.row(align=True)
        rr.operator("ship.ep_still", text=v.get("note", "")[:16] or sid, icon="PINNED" if v.get("note") else "NONE").shot = sid
        o = rr.operator("ship.ep_still", text="", icon="CHECKBOX_HLT" if v.get("approved") else "CHECKBOX_DEHLT")
        o.shot, o.approve = sid, True
    L.label(text="Render unlocked" if F.render_unlocked(e) else "Approve all stills to unlock Final", icon="UNLOCKED" if F.render_unlocked(e) else "LOCKED")


def draw_render(L, ctx):
    e = ep()
    s = st(ctx)
    L.row(align=True).prop(s, "mode", expand=True)
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_queue", icon="RENDER_ANIMATION")
    r.operator("ship.ep_mix", icon="SEQUENCE")
    rd = e.data.get("render", {})
    if rd:
        L.label(text=f"{rd.get('queued', 0)} shots queued ({rd.get('mode')}), done about {rd.get('eta_ist')}", icon="TIME")
    L.label(text=("Queue: " + (Q.RUN["log"] or "idle")), icon="SORTTIME" if Q.busy() else "PAUSE")
    stills = e.path("work", "stills")
    for sid, preset, state in F.queue_progress(e, root(), s.mode):
        row = L.row(align=True)
        row.template_icon(icon_value=picture(os.path.join(stills, sid + ".png"), (0.18, 0.2, 0.24)), scale=1.2)
        row.label(text=f"{sid}  {preset}")
        row.label(text=state, icon={"done": "CHECKMARK", "queued": "TIME"}.get(state, "RADIOBUT_OFF"))


def draw_publish(L, ctx):
    e = ep()
    s = st(ctx)
    r = L.row(align=True)
    r.scale_y = 1.4
    r.operator("ship.ep_thumbs", icon="IMAGE")
    L.prop(s, "headline")
    L.prop(s, "font")
    g = L.grid_flow(row_major=True, columns=3, even_columns=True)
    for k, p in enumerate(e.data.get("thumb_candidates", [])):
        c = g.column(align=True)
        c.template_icon(icon_value=picture(p), scale=4.0)
        c.operator("ship.ep_thumb", text="Use this" if s.thumb != k else "Using this", depress=s.thumb == k).index = k
    if e.data.get("thumbnail"):
        L.template_icon(icon_value=picture(e.data["thumbnail"]), scale=6.0)
    L.label(text="Chapters: " + "  ".join(e.chapters()[:5]), icon="SEQ_STRIP_META")
    r = L.row(align=True)
    r.scale_y = 1.5
    r.operator("ship.ep_publish", icon="PACKAGE")
    r.operator("ship.ep_youtube", icon="URL")
    pub = e.data.get("publish")
    if pub:
        L.label(text=pub["folder"], icon="FILE_FOLDER")
        if pub.get("hi_missing"):
            L.label(text=f"Hindi captions: {len(pub['hi_missing'])} lines still need Hindi text", icon="ERROR")


DRAW = {"BOARD": draw_board, "WRITE": draw_write, "VOICE": draw_voice, "STAGE": draw_stage, "PERFORM": draw_perform,
        "CHECK": draw_check, "RENDER": draw_render, "PUBLISH": draw_publish}


def draw_station(L, ctx):
    s = st(ctx)
    if s.station != "BOARD" and ep() is None:
        L.label(text="Open or start an episode on the Episodes board", icon="INFO")
        L.operator("ship.station", text="Episodes", icon="SEQ_STRIP_DUPLICATE").station = "BOARD"
        return
    DRAW[s.station](L, ctx)


class SHIP_PT_script(bpy.types.Panel):
    """The station bar beside the script page (Write)."""
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "Ship Studio"
    bl_label = "Ship Studio"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, ctx):
        e = ep()
        return e is not None and ctx.space_data.text is not None and ctx.space_data.text.name == f"{e.name} script"

    def draw(self, ctx):
        draw_bar(self.layout, ctx)
        draw_station(self.layout, ctx)


# ------------------------------------------------------------------ timeline overlay (A3)
_DRAW = {"tl": None, "v3": None}
BLOCK = {"on": False}
TRACK_H = 13


def _rect(sh, x0, y0, x1, y1, col):
    b = batch_for_shader(sh, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]})
    sh.uniform_float("color", col)
    b.draw(sh)


def draw_timeline():
    ctx = bpy.context
    e = _EP["ep"]
    if e is None or ctx.area is None or ctx.area.ui_type != "TIMELINE" or not hasattr(ctx.window_manager, "sb_ep") or not st(ctx).folder:
        return
    reg = ctx.region
    v2 = reg.view2d
    tracks, total = F.track_items(e)
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    font = 0
    blf.size(font, 10)
    base = 22
    fps = ctx.scene.render.fps or 24
    for k, (name, items) in enumerate(reversed(tracks)):
        y0 = base + k * (TRACK_H + 2)
        _rect(sh, 0, y0, reg.width, y0 + TRACK_H, (0.08, 0.08, 0.09, 0.55))
        for s, en, lab, col in items:
            x0 = v2.view_to_region(s * fps + 1, 0, clip=False)[0]
            x1 = v2.view_to_region(en * fps + 1, 0, clip=False)[0]
            if x1 < 0 or x0 > reg.width:
                continue
            _rect(sh, x0, y0 + 1, max(x0 + 2, x1 - 1), y0 + TRACK_H - 1, (*col[:3], 0.85))
            if x1 - x0 > 30:
                blf.position(font, x0 + 3, y0 + 3, 0)
                blf.color(font, 0.05, 0.05, 0.05, 1)
                blf.draw(font, lab[: int((x1 - x0) / 6)])
        blf.position(font, 4, y0 + 3, 0)
        blf.color(font, 0.9, 0.9, 0.9, 0.9)
        blf.draw(font, E.TRACKS[len(E.TRACKS) - 1 - k].title())
    gpu.state.blend_set("NONE")


def draw_blocking():
    """Marks, the path each droid walks round the furniture, and every shot camera's view cone."""
    if not BLOCK["on"] or _EP["ep"] is None:
        return
    ctx = bpy.context
    sc = ctx.scene
    if not sc.get("sb_ship"):
        return
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    import math
    from mathutils import Vector
    for o in sc.objects:
        if o.get("sb_cast"):
            c = E.CAST.get(o["sb_cast"], {}).get("color", (1, 1, 1))
            p = o.location
            pts = [(p.x + 0.35 * math.cos(a * math.pi / 12), p.y + 0.35 * math.sin(a * math.pi / 12), 0.02) for a in range(25)]
            b = batch_for_shader(sh, "LINE_STRIP", {"pos": pts})
            sh.uniform_float("color", (*c[:3], 1))
            b.draw(sh)
        if o.type == "CAMERA" and o.get("sb_shot_cam"):
            m = o.matrix_world
            half = math.atan(18 / o.data.lens)
            fwd = (m.to_3x3() @ Vector((0, 0, -1))).to_2d().normalized()
            L = 4.0
            a = (o.location.x, o.location.y, 0.03)
            pts = []
            for s in (-half, half):
                d = Vector((fwd.x * math.cos(s) - fwd.y * math.sin(s), fwd.x * math.sin(s) + fwd.y * math.cos(s)))
                pts += [a, (a[0] + d.x * L, a[1] + d.y * L, 0.03)]
            b = batch_for_shader(sh, "LINES", {"pos": pts})
            sh.uniform_float("color", (0.88, 0.65, 0.29, 0.8))
            b.draw(sh)
    gpu.state.blend_set("NONE")


# ------------------------------------------------------------------ keys
_KEYS = []


def register():
    bpy.types.WindowManager.sb_ep = bpy.props.PointerProperty(type=SB_EpState)
    _DRAW["tl"] = bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw_timeline, (), "WINDOW", "POST_PIXEL")
    _DRAW["v3"] = bpy.types.SpaceView3D.draw_handler_add(draw_blocking, (), "WINDOW", "POST_VIEW")
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for km_name, space in (("Image", "IMAGE_EDITOR"), ("Dopesheet Generic", "DOPESHEET_EDITOR")):
            km = kc.keymaps.new(name=km_name, space_type=space)
            for n, key in enumerate(("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN")):
                kmi = km.keymap_items.new("ship.station", key, "PRESS")
                kmi.properties.station = E.STATIONS[n].upper()
                _KEYS.append((km, kmi))


def unregister():
    for km, kmi in _KEYS:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _KEYS.clear()
    if _DRAW["tl"]:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_DRAW["tl"], "WINDOW")
    if _DRAW["v3"]:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["v3"], "WINDOW")
    _DRAW["tl"] = _DRAW["v3"] = None
    del bpy.types.WindowManager.sb_ep


CLASSES = (SB_Layer, SB_EpState, SHIP_OT_station, SHIP_OT_ep_new, SHIP_OT_ep_open, SHIP_OT_ep_script, SHIP_OT_ep_beat,
           SHIP_OT_ep_room, SHIP_OT_ep_bible, SHIP_OT_ep_gag, SHIP_OT_ep_voice, SHIP_OT_ep_take, SHIP_OT_ep_sample,
           SHIP_OT_ep_build, SHIP_OT_ep_shot, SHIP_OT_ep_jump, SHIP_OT_ep_exterior, SHIP_OT_ep_blocking, SHIP_OT_ep_animatic,
           SHIP_OT_ep_act, SHIP_OT_ep_emotion, SHIP_OT_ep_event, SHIP_OT_ep_puppet, SHIP_OT_ep_check, SHIP_OT_ep_stills,
           SHIP_OT_ep_still, SHIP_OT_ep_approve, SHIP_OT_ep_queue, SHIP_OT_ep_mix, SHIP_OT_ep_thumbs, SHIP_OT_ep_thumb,
           SHIP_OT_ep_publish, SHIP_OT_ep_youtube, SHIP_OT_ep_rough, SHIP_PT_script)
