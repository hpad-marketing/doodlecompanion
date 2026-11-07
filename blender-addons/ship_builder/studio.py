"""Ship Studio: the add-on's own full window.

Window > Ship Studio (or F3 "Ship Studio") opens a separate window laid out
like Doodle Studio:

  +----------------------------------+----------------------+
  | PREVIEW (big picture / movie)    | LIVE SCENE (camera)  |
  |                     | LIBRARY    |                      |
  |                     | tabs, grid |                      |
  +----------------------------------+----------------------+
  | TIMELINE                                                 |
  +---------------------------------------------------------+

Every set, room, droid, motion, prop, camera, mood and hero ship preset shows
as a picture in the library. Clicking one previews it in the big area without
loading anything heavy; "Add to scene" / "Apply" brings it in.
"""
import os
import subprocess
import sys

import bpy
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, PointerProperty
import bpy.utils.previews

from . import catalog as Cat
from . import ship as S
from . import props as Pr
from . import lighting as Li

PKG = __package__
_PCOLL = {"main": None}
_BAKE = {"proc": None, "log": "", "done": 0}


def prefs():
    a = bpy.context.preferences.addons.get(PKG)
    return a.preferences if a else None


def _builtin(name):
    return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[name].value


def icon_for(item):
    pc = _PCOLL["main"]
    if pc is None:
        return _builtin(dict((c, i) for c, _l, i in Cat.CATEGORIES)[item.cat])
    for path, kind in ((item.thumb, "IMAGE"), (item.movie, "MOVIE")):
        if path:
            key = f"{path}|{os.path.getmtime(path) if os.path.exists(path) else 0}"
            if key not in pc:
                try:
                    pc.load(key, path, kind)
                except (RuntimeError, KeyError):
                    continue
            return pc[key].icon_id
    return _builtin(dict((c, i) for c, _l, i in Cat.CATEGORIES)[item.cat])


# ------------------------------------------------------------------ state
def _cat_items(self, ctx):
    return [(c, l, "", i, n) for n, (c, l, i) in enumerate(Cat.CATEGORIES)]


def _droid_items(self, ctx):
    ds = Cat.droids(prefs())
    return [(d["id"], d["name"], "") for d in ds] or [("NONE", "No droids found", "Set the Droid Kit folder in preferences")]


class SB_State(bpy.types.PropertyGroup):
    cat: EnumProperty(name="Library", items=_cat_items)
    selected: StringProperty(name="Selected")
    droid: EnumProperty(name="Droid", items=_droid_items, description="Whose motions to show")
    cols: IntProperty(name="Columns", default=0, min=0, max=8, description="Pictures per row (0 = fit the panel)")


class SB_Prefs(bpy.types.AddonPreferences):
    bl_idname = PKG
    deep_root: StringProperty(name="DeepInDoodles folder", subtype="DIR_PATH",
                              default=os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles"))
    kit_dir: StringProperty(name="Droid Kit folder", subtype="DIR_PATH", description="Folder with droids/<id>.json",
                             default=os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles", "_shared", "droid-kit"))
    thumbs_dir: StringProperty(name="Preview cache", subtype="DIR_PATH",
                               default=os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles", "Ship", "thumbs"))
    scans_dir: StringProperty(name="Scans / stills folder", subtype="DIR_PATH")
    hero_dir: StringProperty(name="Hero ship previews", subtype="DIR_PATH", description="Folder with manifest.json")

    def draw(self, ctx):
        c = self.layout.column()
        for p in ("deep_root", "kit_dir", "thumbs_dir", "scans_dir", "hero_dir"):
            c.prop(self, p)


def state(ctx=None):
    return (ctx or bpy.context).window_manager.sb_studio


def current_items(ctx):
    st = state(ctx)
    return Cat.items(st.cat, prefs(), None if st.droid == "NONE" else st.droid)


def selected_item(ctx):
    st = state(ctx)
    return next((i for i in current_items(ctx) if i.key == st.selected), None)


# ------------------------------------------------------------------ preview area
def preview_spaces():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "IMAGE_EDITOR":
                sp = a.spaces.active
                if sp.image is not None and sp.image.get("sb_preview"):
                    yield a, sp


def _placeholder():
    im = bpy.data.images.get("SB Preview")
    if im is None:
        im = bpy.data.images.new("SB Preview", 16, 9)
        im.generated_color = (0.05, 0.05, 0.055, 1)
    im["sb_preview"] = 1
    return im


def show_preview(item):
    path = item.movie or item.thumb if item else None
    if not path:
        im = _placeholder()
    else:
        im = bpy.data.images.load(path, check_existing=True)
        im["sb_preview"] = 1
        if item.movie and path == item.movie:
            im.source = "MOVIE"
    for a, sp in list(preview_spaces()):
        sp.image = im
        if im.source == "MOVIE":
            sp.image_user.frame_duration = max(1, im.frame_duration)
            sp.image_user.use_auto_refresh = True
            sp.image_user.use_cyclic = True
        win = next((w for w in bpy.context.window_manager.windows if a in w.screen.areas[:]), None)
        reg = next((r for r in a.regions if r.type == "WINDOW"), None)
        if win and reg:  # fill the preview area with the picture
            try:
                with bpy.context.temp_override(window=win, area=a, region=reg):
                    bpy.ops.image.view_all(fit_view=True)
            except RuntimeError:
                pass
        a.tag_redraw()


# ------------------------------------------------------------------ operators
class SHIP_OT_pick(bpy.types.Operator):
    """Preview this item"""
    bl_idname = "ship.pick"
    bl_label = "Pick"
    key: StringProperty()

    def execute(self, ctx):
        state(ctx).selected = self.key
        show_preview(selected_item(ctx))
        return {"FINISHED"}


class SHIP_OT_use(bpy.types.Operator):
    """Bring the picked item into the scene (sets and rooms build in a new scene)"""
    bl_idname = "ship.use"
    bl_label = "Add to scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        it = selected_item(ctx)
        if it is None:
            self.report({"WARNING"}, "Pick something in the library first")
            return {"CANCELLED"}
        try:
            msg = USE[it.cat](ctx, it)
        except Exception as e:  # show the reason instead of a stack trace
            self.report({"ERROR"}, f"{it.label}: {e}")
            return {"CANCELLED"}
        if msg:
            self.report({"INFO"}, msg)
        return {"FINISHED"}


def _new_scene(ctx, name):
    sc = bpy.data.scenes.new(name)
    ctx.window.scene = sc
    Li.render_setup(sc)
    Li.space_world()
    return sc


def _use_set(ctx, it):
    _new_scene(ctx, f"Ship {it.label}")
    info = S.build(it.id)
    return f"Built {len(info['rooms'])} rooms, {len(info['links'])} docked doors"


def _use_room(ctx, it):
    _new_scene(ctx, f"Ship {it.label}")
    S.build([it.id])
    return f"Built {it.label}"


def _use_droid(ctx, it):
    d = it.data
    if not os.path.isfile(d["blend"]):
        raise RuntimeError(f"file not found: {d['blend']}")
    with bpy.data.libraries.load(d["blend"], link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None]
    rig = next((o for o in objs if o.name.split(".")[0] == d["rig"]), None) or next((o for o in objs if o.type == "ARMATURE"), None)
    if rig is None:
        for o in objs:
            bpy.data.objects.remove(o)
        raise RuntimeError("no rig in the droid file")
    from . import castfit, rigui
    fam = rigui.keep_family(rig, objs)
    col = bpy.data.collections.new(f"Droid {d['name']}")
    ctx.scene.collection.children.link(col)
    for o in objs:
        if o in fam:
            col.objects.link(o)
            if o is rig or o.parent is not None:
                o["sb_droid"] = d["id"]
        else:
            bpy.data.objects.remove(o)
    castfit.fit(rig, d["id"], d)
    rigui.show_controls(rig, ctx.scene)
    info = S.info(ctx.scene)
    if info and info["rooms"]:
        r = info["rooms"][0]
        rig.location = (r["x"], r["y"] + r["D"] * 0.4, 0.0)
    else:
        rig.location = ctx.scene.cursor.location
    for o in ctx.view_layer.objects:
        o.select_set(False)
    rig.select_set(True)
    ctx.view_layer.objects.active = rig
    return f"Added {d['name']}"


def _scene_rig(ctx, droid_id):
    ob = ctx.active_object
    while ob is not None and ob.type != "ARMATURE" and ob.parent is not None:
        ob = ob.parent
    if ob is not None and ob.type == "ARMATURE":
        return ob
    return next((o for o in ctx.scene.objects if o.type == "ARMATURE" and o.get("sb_droid") == droid_id), None)


def _use_motion(ctx, it):
    rig = _scene_rig(ctx, it.data["droid"])
    if rig is None:
        raise RuntimeError("add the droid first, then pick its motion")
    act = bpy.data.actions.get(it.id)
    if act is None:
        with bpy.data.libraries.load(it.data["blend"], link=False) as (src, dst):
            dst.actions = [it.id]
        act = dst.actions[0]
    ad = rig.animation_data or rig.animation_data_create()
    ad.action = act
    if hasattr(ad, "action_slot") and getattr(act, "slots", None) and len(act.slots):
        ad.action_slot = act.slots[0]
    f0, f1 = act.frame_range
    ctx.scene.frame_start, ctx.scene.frame_end = int(f0), int(f1)
    return f"{rig.name}: {it.label}"


def _use_prop(ctx, it):
    Pr.add(it.id)
    return f"Added {it.label} at the 3D cursor"


def _use_cam(ctx, it):
    cam = bpy.data.objects.get(it.id)
    ctx.scene.camera = cam
    for a in ctx.window.screen.areas:
        if a.type == "VIEW_3D":
            a.spaces.active.region_3d.view_perspective = "CAMERA"
    return None


def _use_mood(ctx, it):
    Li.set_mood(it.id, ctx.scene)
    return None


def _use_view(ctx, it):
    from . import views as V
    if ctx.scene.world is None or ctx.scene.world.name != V.WORLD:
        V.build(ctx.scene)
    # with auto-key on, the switch is keyed at the current frame (cut to hyperspace mid-scene)
    key = ctx.scene.tool_settings.use_keyframe_insert_auto
    V.set_view(it.id, ctx.scene, frame=ctx.scene.frame_current if key else None)
    return None


def _hero_module():
    for name, mod in list(sys.modules.items()):
        if name.split(".")[-1] == "hero_ship" and hasattr(mod, "build"):
            return mod
    return None


def _use_ship(ctx, it):
    hs = _hero_module()
    if hs is None:
        raise RuntimeError("the Hero Ship add-on isn't installed yet; its previews still play here")
    pres = sys.modules.get(hs.__name__ + ".presets") or __import__(hs.__name__ + ".presets", fromlist=["apply"])
    root = bpy.data.objects.get("Hero Ship") or hs.build()
    pres.apply(root, it.id, frame_start=ctx.scene.frame_start)
    return f"Hero ship: {it.label}"


USE = {"SETS": _use_set, "ROOMS": _use_room, "DROIDS": _use_droid, "MOTIONS": _use_motion, "PROPS": _use_prop,
       "CAMERAS": _use_cam, "MOODS": _use_mood, "VIEWS": _use_view, "SHIP": _use_ship}
USE_LABEL = {"SETS": "Build set", "ROOMS": "Build room", "DROIDS": "Add droid", "MOTIONS": "Play on droid",
             "PROPS": "Add prop", "CAMERAS": "Look through", "MOODS": "Apply mood", "VIEWS": "Show outside", "SHIP": "Apply preset"}


class SHIP_OT_cam_step(bpy.types.Operator):
    """Next or previous camera"""
    bl_idname = "ship.cam_step"
    bl_label = "Camera"
    step: IntProperty(default=1)

    def execute(self, ctx):
        info = S.info(ctx.scene)
        cams = [bpy.data.objects[c["name"]] for c in info["cameras"] if c["name"] in bpy.data.objects] if info else \
            [o for o in ctx.scene.objects if o.type == "CAMERA"]
        if not cams:
            return {"CANCELLED"}
        i = cams.index(ctx.scene.camera) if ctx.scene.camera in cams else -1
        ctx.scene.camera = cams[(i + self.step) % len(cams)]
        return {"FINISHED"}


class SHIP_OT_walk_here(bpy.types.Operator):
    """Walk the selected droid through the ship (WASD or DualSense, Esc to stop)"""
    bl_idname = "ship.walk_here"
    bl_label = "Walk mode"

    def execute(self, ctx):
        for a in ctx.window.screen.areas:
            if a.type == "VIEW_3D":
                r = next(r for r in a.regions if r.type == "WINDOW")
                a.spaces.active.region_3d.view_perspective = "CAMERA"
                with ctx.temp_override(area=a, region=r):
                    bpy.ops.ship.walk("INVOKE_DEFAULT")
                return {"FINISHED"}
        bpy.ops.ship.walk("INVOKE_DEFAULT")
        return {"FINISHED"}


class SHIP_OT_bake(bpy.types.Operator):
    """Render the missing preview pictures and motion clips in the background (GPU), so every item shows a picture"""
    bl_idname = "ship.bake_previews"
    bl_label = "Bake previews"
    what: EnumProperty(items=[("ALL", "Everything missing", ""), ("CAT", "This tab", "")], default="ALL")

    def execute(self, ctx):
        if _BAKE["proc"] is not None and _BAKE["proc"].poll() is None:
            self.report({"INFO"}, "Already baking")
            return {"CANCELLED"}
        p = prefs()
        out = bpy.path.abspath(p.thumbs_dir) if p else ""
        if not out:
            self.report({"ERROR"}, "Set the preview cache folder in the add-on preferences")
            return {"CANCELLED"}
        os.makedirs(out, exist_ok=True)
        script = os.path.join(os.path.dirname(__file__), "bake_previews.py")
        cats = state(ctx).cat if self.what == "CAT" else "ALL"
        args = [bpy.app.binary_path, "-b", "--factory-startup", "--python", script, "--",
                os.path.dirname(os.path.dirname(__file__)), os.path.basename(os.path.dirname(__file__)), out, cats,
                bpy.path.abspath(p.kit_dir or ""), bpy.path.abspath(p.deep_root or "")]
        log = open(os.path.join(out, "bake.log"), "w", encoding="utf-8")
        _BAKE.update(proc=subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT), log=log.name, done=0)
        bpy.app.timers.register(_bake_poll, first_interval=2.0)
        self.report({"INFO"}, "Baking previews in the background; pictures appear as they finish")
        return {"FINISHED"}


def _bake_poll():
    pr = _BAKE["proc"]
    if pr is None:
        return None
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()
    if pr.poll() is None:
        return 3.0
    _BAKE["proc"] = None
    return None


class SHIP_OT_gallery(bpy.types.Operator):
    """Big picture view of this tab"""
    bl_idname = "ship.gallery"
    bl_label = "Browse"

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_popup(self, width=1100)

    def draw(self, ctx):
        draw_grid(self.layout, ctx, 7, 6.5)

    def execute(self, ctx):
        return {"FINISHED"}


def _set_area(win, area, kind):
    area.ui_type = kind


class SHIP_OT_open(bpy.types.Operator):
    """Open Ship Studio in its own window"""
    bl_idname = "ship.open_studio"
    bl_label = "Ship Studio"

    def execute(self, ctx):
        wm = ctx.window_manager
        before = set(wm.windows[:])
        bpy.ops.wm.window_new()
        win = next((w for w in wm.windows if w not in before), None)
        if win is None:
            return {"CANCELLED"}
        scr = win.screen
        # keep the biggest area, close the rest
        while len(scr.areas) > 1:
            small = min(scr.areas, key=lambda a: a.width * a.height)
            with ctx.temp_override(window=win, screen=scr, area=small):
                bpy.ops.screen.area_close()
        main = scr.areas[0]
        main.ui_type = "VIEW_3D"
        # sizes are reliable right after a split, positions are not: pick areas by size
        with ctx.temp_override(window=win, screen=scr, area=main):
            bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.22)
        bottom = min(scr.areas, key=lambda a: a.height)
        top = max(scr.areas, key=lambda a: a.height)
        bottom.ui_type = "TIMELINE"
        with ctx.temp_override(window=win, screen=scr, area=top):
            bpy.ops.screen.area_split(direction="VERTICAL", factor=0.58)
        tops = [a for a in scr.areas if a != bottom]
        left = max(tops, key=lambda a: a.width)   # the wide one: preview + library
        right = min(tops, key=lambda a: a.width)  # the live camera view
        left.ui_type = "IMAGE_EDITOR"
        sp = left.spaces.active
        sp.image = _placeholder()
        sp.show_region_ui = True
        sp.show_region_toolbar = False
        right.ui_type = "VIEW_3D"
        v3 = right.spaces.active
        v3.region_3d.view_perspective = "CAMERA"
        v3.shading.type = "MATERIAL"
        v3.show_region_toolbar = False
        v3.overlay.show_overlays = True
        v3.overlay.show_extras = False  # no light/empty/camera wires over the shot
        with ctx.temp_override(window=win, screen=scr, area=left):
            try:
                bpy.ops.wm.context_set_enum(data_path="space_data.mode", value="VIEW")
            except RuntimeError:
                pass
        state(ctx).cat = state(ctx).cat or "SETS"
        from . import uiwidth
        uiwidth.later(left, SIDEBAR_PX)
        _fit_later(left)
        return {"FINISHED"}


SIDEBAR_PX = 460


def _fit_later(area):
    ptr = area.as_pointer()

    def go():
        for win in bpy.context.window_manager.windows:
            for a in win.screen.areas:
                if a.as_pointer() == ptr and a.type == "IMAGE_EDITOR":
                    reg = next((r for r in a.regions if r.type == "WINDOW"), None)
                    if reg is not None and reg.width > 1:
                        with bpy.context.temp_override(window=win, area=a, region=reg):
                            try:
                                bpy.ops.image.view_all(fit_view=True)
                            except RuntimeError:
                                pass
        return None
    bpy.app.timers.register(go, first_interval=0.6)


# ------------------------------------------------------------------ library panel
def draw_grid(layout, ctx, cols, scale):
    st = state(ctx)
    its = current_items(ctx)
    if not its:
        box = layout.box()
        box.label(text=EMPTY.get(st.cat, "Nothing here yet"), icon="INFO")
        return
    g = layout.grid_flow(row_major=True, columns=cols, even_columns=True, even_rows=True, align=False)
    for it in its:
        cell = g.column(align=True)
        cell.template_icon(icon_value=icon_for(it), scale=scale)
        op = cell.operator("ship.pick", text=it.label, depress=(it.key == st.selected))
        op.key = it.key


EMPTY = {
    "DROIDS": "No droids yet: set the Droid Kit folder in the add-on preferences",
    "MOTIONS": "Pick a droid that has motions in its file",
    "CAMERAS": "Build a set or room first; its cameras show here",
    "SHIP": "Hero ship previews appear when its manifest.json folder is set in preferences",
}


class SHIP_PT_library(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Ship Studio"
    bl_label = "Ship Studio"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, ctx):
        sp = ctx.space_data
        return sp is not None and sp.image is not None and bool(sp.image.get("sb_preview"))

    def draw(self, ctx):
        L = self.layout
        from . import stations
        stations.draw_bar(L, ctx)
        if ctx.window_manager.sb_ep.station != "LIBRARY":
            stations.draw_station(L, ctx)
            return
        st = state(ctx)
        # tabs: two rows of four, pictures + words
        tabs = L.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
        tabs.scale_y = 1.3
        for c, lab, ic in Cat.CATEGORIES:
            tabs.prop_enum(st, "cat", c, text=lab, icon=ic)
        if st.cat == "DROIDS":
            from . import rigui
            rigui.draw_controls(L, ctx)
        if st.cat == "MOTIONS":
            L.prop(st, "droid", text="Droid")
        # what's picked + the one big action
        it = selected_item(ctx)
        row = L.row(align=True)
        row.scale_y = 1.6
        if it:
            row.operator("ship.use", text=f"{USE_LABEL[it.cat]}: {it.label}", icon="IMPORT")
        else:
            row.label(text="Click a picture to preview it", icon="HAND")
        row = L.row(align=True)
        row.scale_y = 1.25
        row.operator("ship.walk_here", icon="CON_FOLLOWPATH")
        row.operator("ship.cam_step", text="", icon="TRIA_LEFT").step = -1
        row.operator("ship.cam_step", text="Camera", icon="CAMERA_DATA").step = 1
        row.operator("ship.gallery", text="", icon="FULLSCREEN_ENTER")
        if it and it.blurb:
            L.label(text=it.blurb)
        cols = st.cols or max(2, int(ctx.region.width / (150 * ctx.preferences.system.ui_scale)))
        draw_grid(L, ctx, cols, 5.0)
        row = L.row(align=True)
        busy = _BAKE["proc"] is not None and _BAKE["proc"].poll() is None
        row.operator("ship.bake_previews", text="Baking previews..." if busy else "Bake missing previews", icon="RENDER_STILL").what = "ALL"
        row.prop(st, "cols", text="Per row")


def menu_func(self, ctx):
    self.layout.operator("ship.open_studio", icon="WINDOW")


CLASSES = (SB_State, SB_Prefs, SHIP_OT_pick, SHIP_OT_use, SHIP_OT_cam_step, SHIP_OT_walk_here, SHIP_OT_bake,
           SHIP_OT_gallery, SHIP_OT_open, SHIP_PT_library)


def register():
    _PCOLL["main"] = bpy.utils.previews.new()
    bpy.types.WindowManager.sb_studio = PointerProperty(type=SB_State)
    bpy.types.TOPBAR_MT_window.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_window.remove(menu_func)
    del bpy.types.WindowManager.sb_studio
    if _PCOLL["main"] is not None:
        bpy.utils.previews.remove(_PCOLL["main"])
        _PCOLL["main"] = None
