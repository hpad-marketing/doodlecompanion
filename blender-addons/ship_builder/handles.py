"""Handles on every droid, right in the 3D view: the easiest way to pose.

Big coloured rings float on each droid's hands, feet, body and head (blue = its
left, red = its right, yellow = middle). Drag a ring and that part follows the
mouse; with auto-key on, the move is keyed. A dial under the droid turns it, a
dial at its head turns the head. Each ring carries a small name tag. Works in
Object and Pose mode, in every 3D view; the "Handles" switch turns them off.
"""
import math

import blf
import bpy
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

from . import posekit as P
from . import rigui

COL = {"L": (0.25, 0.55, 1.0), "R": (1.0, 0.3, 0.25), "C": (1.0, 0.78, 0.2)}
COL_HI = {"L": (0.6, 0.8, 1.0), "R": (1.0, 0.65, 0.6), "C": (1.0, 0.95, 0.6)}
_DRAW = {"h": None}


def on(scene):
    return bool(scene.get("sb_handles", 1))


def _sig(scene):
    out = []
    for rig in rigui.droids(scene):
        out.append((rig.name, tuple(h.key for h in P.handles(rig))))
    return tuple(out)


class SHIP_GGT_handles(bpy.types.GizmoGroup):
    bl_idname = "SHIP_GGT_handles"
    bl_label = "Droid handles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT", "SHOW_MODAL_ALL"}

    @classmethod
    def poll(cls, ctx):
        sc = ctx.scene
        return sc is not None and on(sc) and ctx.mode in ("OBJECT", "POSE") and bool(rigui.droids(sc))

    def setup(self, ctx):
        self.sig = None
        self.items = []
        self._build(ctx)

    def _build(self, ctx):
        for gz, *_ in self.items:
            self.gizmos.remove(gz)
        self.items = []
        for rig in rigui.droids(ctx.scene):
            hh = P.height(rig)
            for h in P.handles(rig):
                gz = self.gizmos.new("GIZMO_GT_move_3d")
                gz.draw_style = "RING_2D"
                gz.draw_options = {"FILL_SELECT", "ALIGN_VIEW"}
                gz.scale_basis = 0.16 if h.key == "whole" else 0.11
                gz.line_width = 3.0
                gz.color, gz.color_highlight = COL[h.side], COL_HI[h.side]
                gz.alpha, gz.alpha_highlight = 0.85, 1.0
                gz.matrix_basis = Matrix.Identity(4)
                rn, hk = rig.name, h.key
                gz.target_set_handler("offset", get=self._getter(rn, hk), set=self._setter(rn, hk))
                self.items.append((gz, rn, hk, "move"))
                if h.key in P.TURNABLE:
                    dz = self.gizmos.new("GIZMO_GT_dial_3d")
                    dz.draw_options = {"ANGLE_VALUE"} if h.key == "whole" else set()
                    dz.scale_basis = hh * (0.55 if h.key == "whole" else 0.28)
                    dz.use_draw_scale = False
                    dz.line_width = 3.0
                    dz.color, dz.color_highlight = COL["C"], COL_HI["C"]
                    dz.alpha, dz.alpha_highlight = 0.55, 1.0
                    dz.target_set_handler("offset", get=self._turn_get(rn, hk), set=self._turn_set(rn, hk))
                    self.items.append((dz, rn, hk, "turn"))
        self.sig = _sig(ctx.scene)
        self._place()

    # -- handlers (looked up by name each call, so undo / renames never crash)
    @staticmethod
    def _getter(rn, hk):
        def get():
            rig = bpy.data.objects.get(rn)
            h = P.get(rig, hk) if rig else None
            return tuple(P.point(rig, h)) if h else (0.0, 0.0, 0.0)
        return get

    @staticmethod
    def _setter(rn, hk):
        def set_(value):
            rig = bpy.data.objects.get(rn)
            h = P.get(rig, hk) if rig else None
            if h:
                P.move_to(rig, h, value)
        return set_

    @staticmethod
    def _turn_get(rn, hk):
        def get():
            rig = bpy.data.objects.get(rn)
            return float(rig.get(f"sb_turn_{hk}", 0.0)) if rig else 0.0
        return get

    @staticmethod
    def _turn_set(rn, hk):
        def set_(value):
            rig = bpy.data.objects.get(rn)
            h = P.get(rig, hk) if rig else None
            if not h:
                return
            was = float(rig.get(f"sb_turn_{hk}", 0.0))
            rig[f"sb_turn_{hk}"] = value
            P.turn(rig, h, value - was)
        return set_

    def _place(self):
        for gz, rn, hk, kind in self.items:
            rig = bpy.data.objects.get(rn)
            h = P.get(rig, hk) if rig else None
            if h is None:
                gz.hide = True
                continue
            gz.hide = False
            if kind == "turn":
                p = P.point(rig, h)
                if hk == "whole":
                    p = p + Vector((0, 0, 0.02))
                gz.matrix_basis = Matrix.Translation(p)

    def refresh(self, ctx):
        if _sig(ctx.scene) != self.sig:
            self._build(ctx)
        else:
            self._place()

    def draw_prepare(self, ctx):
        self._place()


def draw_labels():
    ctx = bpy.context
    sc = ctx.scene
    if sc is None or not on(sc) or ctx.mode not in ("OBJECT", "POSE"):
        return
    region, r3 = ctx.region, ctx.region_data
    if r3 is None:
        return
    rigs = rigui.droids(sc)
    if not rigs:
        return
    font = 0
    ui = ctx.preferences.system.ui_scale
    blf.size(font, 11 * ui)
    for rig in rigs:
        if not rig.visible_get():
            continue
        for h in P.handles(rig):
            p2 = view3d_utils.location_3d_to_region_2d(region, r3, P.point(rig, h))
            if p2 is None:
                continue
            txt = rigui.label(rig) if h.key == "whole" else h.label
            c = COL[h.side]
            blf.color(font, 0, 0, 0, 0.7)
            blf.position(font, p2.x + 15 * ui, p2.y - 5 * ui, 0)
            blf.draw(font, txt)
            blf.color(font, c[0], c[1], c[2], 1.0)
            blf.position(font, p2.x + 14 * ui, p2.y - 4 * ui, 0)
            blf.draw(font, txt)


class SHIP_OT_handles(bpy.types.Operator):
    """Show or hide the drag handles on every droid in the view"""
    bl_idname = "ship.handles"
    bl_label = "Handles"

    def execute(self, ctx):
        ctx.scene["sb_handles"] = 0 if on(ctx.scene) else 1
        for w in ctx.window_manager.windows:
            for a in w.screen.areas:
                a.tag_redraw()
        return {"FINISHED"}


class SHIP_OT_pose_preset(bpy.types.Operator):
    """Pose this droid from a preset (keyed at the playhead when auto-key is on)"""
    bl_idname = "ship.pose_preset"
    bl_label = "Pose preset"
    bl_options = {"REGISTER", "UNDO"}
    rig: bpy.props.StringProperty()
    preset: bpy.props.StringProperty()

    def execute(self, ctx):
        rig = bpy.data.objects.get(self.rig)
        if rig is None or self.preset not in P.POSES:
            return {"CANCELLED"}
        lab = P.apply(rig, self.preset)
        self.report({"INFO"}, f"{rigui.label(rig)}: {lab}")
        return {"FINISHED"}


CLASSES = (SHIP_GGT_handles, SHIP_OT_handles, SHIP_OT_pose_preset)


def register():
    if _DRAW["h"] is None:
        _DRAW["h"] = bpy.types.SpaceView3D.draw_handler_add(draw_labels, (), "WINDOW", "POST_PIXEL")


def unregister():
    if _DRAW["h"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["h"], "WINDOW")
        _DRAW["h"] = None
