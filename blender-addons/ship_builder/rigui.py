"""Visible controls for every droid in a set, and a Controls panel to grab them.

A droid comes in with its control shapes (the widget objects its rig uses are
kept, not dropped), drawn in front of the set and a little thicker. Bones that
have no shape of their own (the tracked porter's) get a simple ring sized to the
bone, so there is always something to click. The Controls panel lists each
droid's control groups with show/hide, the main handles (whole droid, body,
head, hands, feet) one click away, and Pose / Done buttons.
"""
import math

import bpy
from mathutils import Matrix

MAIN = (("Whole droid", ("root",)), ("Body", ("cog", "torso", "chassis", "body", "hips")),
        ("Head", ("head", "sensor", "neck")), ("Left hand", ("ik-hand.l", "hand_ik.l", "ik_hand.l", "fk-hand.l", "grip.l")),
        ("Right hand", ("ik-hand.r", "hand_ik.r", "ik_hand.r", "fk-hand.r", "grip.r")),
        ("Left foot", ("ik_foot.l", "ik-foot.l", "foot_ik.l")), ("Right foot", ("ik_foot.r", "ik-foot.r", "foot_ik.r")),
        ("Scoop", ("scoop_lift",)), ("Lean", ("lean", "waist")))
WIDGETS = "SB Droid Widgets"


def keep_family(rig, objs):
    """The rig, its children and every object its bones use as a control shape."""
    fam = {rig} | set(rig.children_recursive)
    if rig.pose:
        fam |= {pb.custom_shape for pb in rig.pose.bones if pb.custom_shape}
    return fam


def _widget_col(scene):
    col = bpy.data.collections.get(WIDGETS)
    if col is None:
        col = bpy.data.collections.new(WIDGETS)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    col.hide_viewport = col.hide_render = True
    return col


def _ring():
    me = bpy.data.meshes.get("SB Widget Ring")
    if me is None:
        n = 24
        verts = [(math.cos(2 * math.pi * k / n) * 0.5, 0.5, math.sin(2 * math.pi * k / n) * 0.5) for k in range(n)]
        me = bpy.data.meshes.new("SB Widget Ring")
        me.from_pydata(verts, [(k, (k + 1) % n) for k in range(n)], [])
    ob = bpy.data.objects.get("SB Widget Ring")
    if ob is None:
        ob = bpy.data.objects.new("SB Widget Ring", me)
    return ob


def show_controls(rig, scene=None):
    """Make the rig's controls visible and clickable in the set."""
    scene = scene or bpy.context.scene
    col = _widget_col(scene)
    for pb in rig.pose.bones:
        sh = pb.custom_shape
        if sh is not None and sh.name not in col.objects:
            for c in list(sh.users_collection):
                if c != col:
                    c.objects.unlink(sh)
            col.objects.link(sh)
        if sh is not None:
            sh.hide_render = True       # a control, never a part of the set
            sh["sb_widget"] = 1
    a = rig.data
    visible = [c for c in a.collections_all if c.is_visible] if hasattr(a, "collections_all") else []
    ring = None
    for b in a.bones:
        pb = rig.pose.bones[b.name]
        on_show = any(c in visible for c in b.collections) if visible else True
        if pb.custom_shape is None and on_show and not b.name.startswith(("MCH", "DEF", "SPR", "ORG")):
            ring = ring or _ring()
            if ring.name not in col.objects:
                col.objects.link(ring)
            ring.hide_render = True
            ring["sb_widget"] = 1
            pb.custom_shape = ring
            pb.custom_shape_scale_xyz = (0.6, 0.6, 0.6)
        if hasattr(pb, "custom_shape_wire_width"):
            pb.custom_shape_wire_width = 2.5
    rig.show_in_front = True
    a.display_type = "WIRE"
    a.show_names = False
    rig.hide_select = False
    rig.hide_set(False)
    return rig


def droids(scene):
    return [o for o in scene.objects if o.type == "ARMATURE" and (o.get("sb_droid") or o.get("sb_cast"))]


def label(rig):
    """The droid's own name (RX-07), not its rig object's (RobotRig)."""
    for c in rig.users_collection:
        if c.name.startswith("Droid "):
            return c.name[6:].split(".")[0].split(" (")[0]
    return rig.get("sb_cast") or rig.name.split(".")[0]


def find(rig, keys):
    names = {b.name.lower(): b.name for b in rig.data.bones}
    for k in keys:
        if k in names:
            return names[k]
    return None


def _select_bone(rig, name):
    """Select one bone (Blender 5 keeps selection on the pose bone, 4.x on the bone)."""
    for b in rig.data.bones:
        pb = rig.pose.bones.get(b.name)
        for it in (b, pb):
            if it is not None and hasattr(it, "select"):
                it.select = False
        for k in ("select_head", "select_tail"):
            if hasattr(b, k):
                setattr(b, k, False)
    b = rig.data.bones.get(name)
    if b is None:
        return
    pb = rig.pose.bones.get(name)
    for it in (b, pb):
        if it is not None and hasattr(it, "select"):
            it.select = True
    rig.data.bones.active = b


def _view3d(ctx):
    win = ctx.window
    if win is None:
        return None, None
    a = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height, default=None)
    return win, a


class SHIP_OT_pose(bpy.types.Operator):
    """Pose this droid: its controls light up; drag them in the view (G move, R rotate)"""
    bl_idname = "ship.pose"
    bl_label = "Pose"
    rig: bpy.props.StringProperty()
    bone: bpy.props.StringProperty()

    def execute(self, ctx):
        rig = bpy.data.objects.get(self.rig)
        if rig is None:
            return {"CANCELLED"}
        show_controls(rig, ctx.scene)
        win, area = _view3d(ctx)
        vl = ctx.view_layer
        if ctx.mode != "OBJECT" and ctx.active_object is not rig:
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in vl.objects:
            o.select_set(False)
        rig.select_set(True)
        vl.objects.active = rig
        over = dict(window=win, area=area, region=next(r for r in area.regions if r.type == "WINDOW")) if area else {}
        with ctx.temp_override(**over):
            if self.bone and self.bone != "*":
                if rig.mode != "POSE":
                    bpy.ops.object.mode_set(mode="POSE")
                _select_bone(rig, self.bone)
            elif self.bone == "*":
                if rig.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
            else:
                bpy.ops.object.mode_set(mode="POSE")
        return {"FINISHED"}


class SHIP_OT_pose_done(bpy.types.Operator):
    """Leave posing (back to moving whole objects)"""
    bl_idname = "ship.pose_done"
    bl_label = "Done"

    def execute(self, ctx):
        if ctx.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        return {"FINISHED"}


class SHIP_OT_pose_reset(bpy.types.Operator):
    """Put this droid back in its rest pose"""
    bl_idname = "ship.pose_reset"
    bl_label = "Reset pose"
    rig: bpy.props.StringProperty()

    def execute(self, ctx):
        rig = bpy.data.objects.get(self.rig)
        if rig is None:
            return {"CANCELLED"}
        for pb in rig.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.scale = (1, 1, 1)
        return {"FINISHED"}


class SHIP_OT_set_view(bpy.types.Operator):
    """Set view: walls and ceilings between you and a room cut away as you orbit (renders untouched)"""
    bl_idname = "ship.set_view"
    bl_label = "Set view"

    def execute(self, ctx):
        from . import cutaway
        sc = ctx.scene
        sc["sb_set_view"] = 0 if sc.get("sb_set_view", 1) else 1
        cutaway.start()
        cutaway._STATE["eye"] = None
        cutaway.update()
        return {"FINISHED"}


def draw_set_view(L, ctx):
    on = bool(ctx.scene.get("sb_set_view", 1))
    L.operator("ship.set_view", text="Set view: see into rooms" if on else "Set view off (walls solid)",
               icon="HIDE_OFF" if on else "HIDE_ON", depress=on)


def _draw_pose_strip(col, ctx, rig):
    """One-click pose presets with a picture each."""
    from . import posekit as PK, studio as St, catalog as Cat
    pr = St.prefs()
    did = str(rig.get("sb_droid") or rig.get("sb_cast") or "")
    g = col.grid_flow(row_major=True, columns=6, even_columns=True, align=True)
    for k, lab in PK.poses_for(rig):
        it = Cat.Item("POSES", k, lab, "", Cat.find(pr, f"pose_{did}_{k}") or Cat.find(pr, f"droid_{did}"))
        c = g.column(align=True)
        c.template_icon(icon_value=St.icon_for(it), scale=2.4)
        o = c.operator("ship.pose_preset", text=lab)
        o.rig, o.preset = rig.name, k


def draw_controls(L, ctx):
    """The Controls box: one block per droid in the scene."""
    rigs = droids(ctx.scene)
    box = L.box()
    head = box.row()
    head.label(text="Droid controls", icon="ARMATURE_DATA")
    from . import handles
    head.operator("ship.handles", text="Handles on droids", icon="GIZMO", depress=handles.on(ctx.scene))
    if ctx.mode == "POSE":
        head.operator("ship.pose_done", icon="CHECKMARK")
    if not rigs:
        box.label(text="Add a droid from the Droids tab to pose it here")
        return
    for rig in rigs:
        col = box.column(align=True)
        r = col.row(align=True)
        r.scale_y = 1.3
        r.operator("ship.pose", text=f"Pose {label(rig)}", icon="POSE_HLT", depress=rig.mode == "POSE").rig = rig.name
        o = r.operator("ship.pose", text="Move whole", icon="OBJECT_ORIGIN")
        o.rig, o.bone = rig.name, "*"
        r.operator("ship.pose_reset", text="", icon="LOOP_BACK").rig = rig.name
        g = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for name, keys in MAIN:
            bn = find(rig, keys)
            if bn:
                o = g.operator("ship.pose", text=name)
                o.rig, o.bone = rig.name, bn
        a = rig.data
        if hasattr(a, "collections_all"):
            g = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            for c in a.collections_all:
                if c.name.lower() in ("deform", "mechanics", "mch", "org"):
                    continue
                g.prop(c, "is_visible", text=c.name, toggle=True)
        _draw_pose_strip(col, ctx, rig)
        kg = rig.get("foley_mass_kg")
        if kg:
            col.label(text=f"{kg:.0f} kg  ·  scale {rig.get('sb_set_scale', 1.0):.2f}", icon="PHYSICS")


CLASSES = (SHIP_OT_pose, SHIP_OT_pose_done, SHIP_OT_pose_reset, SHIP_OT_set_view)
