"""Ship Foley: every contact makes a sound.

Feet on the deck, fingers on a prop, a crate set down, a drone bumping a
console. The sounds are made from physics (no sample licences): loudness
follows the energy of the hit (droid mass and impact speed), brightness
follows how hard and fast the strike is, pitch and ring follow the size,
shape and material of what was hit.

N panel > Foley (3D View and Sequencer):
  Bake contact sounds   scan the frame range and lay "FX" strips in the VSE
  Clear                 remove only the FX strips
  Mixdown               write the shot's audio to a WAV beside the .blend
Per droid (select its armature): profile, and a weight override in kg.

Walk mode: when Ship Builder is enabled, every foot plant plays its step live
(hooked into ship_builder.feet.ON_PLANT).

Scripting / other add-ons:
  ship_foley.bake_scene(scene)            -> (events, strips, json path)
  ship_foley.live.contact(arm, "foot.L", speed, surface)   live one-shot
"""
import os

import bpy

from . import profiles, synth, detect, place, live, motors

PROFILE_ITEMS = [(k, v["label"], "%d kg" % v["mass_kg"]) for k, v in profiles.DROIDS.items()]


def bake_scene(scene=None, substeps=2, master=1.0, room_wet=0.06, include_props=True, report=None,
               motors_on=True, motor_level=1.0):
    scene = scene or bpy.context.scene
    mot = {} if motors_on else None
    events = detect.scan(scene, substeps=substeps, include_props=include_props, report=report, motors_out=mot)
    made, js = place.bake(events, scene, master=master, room_wet=room_wet)
    if mot:
        made += place.bake_motors(mot, events, scene, master=master * motor_level)
    return events, made, js


class FOLEY_Settings(bpy.types.PropertyGroup):
    master: bpy.props.FloatProperty(name="Loudness", default=1.0, min=0.0, max=4.0,
                                    description="Overall level of every contact sound")
    room: bpy.props.FloatProperty(name="Room", default=0.06, min=0.0, max=0.6,
                                  description="How much small-steel-room echo each sound carries")
    substeps: bpy.props.IntProperty(name="Precision", default=2, min=1, max=6,
                                    description="Samples per frame when looking for contacts (more = finer timing, slower)")
    motors: bpy.props.BoolProperty(name="Motors", default=True,
                                   description="Joint motors whir and whine as parts turn, and clunk when they stop hard")
    motor_level: bpy.props.FloatProperty(name="Motor level", default=1.0, min=0.0, max=4.0,
                                         description="Loudness of the joint motors against the contact sounds")
    props: bpy.props.BoolProperty(name="Props", default=True,
                                  description="Loose props make sounds when they land, get set down or slide")


class FOLEY_OT_bake(bpy.types.Operator):
    """Find every contact in the frame range and lay its sound on the timeline"""
    bl_idname = "foley.bake"
    bl_label = "Bake contact sounds"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.ship_foley
        msgs = []
        events, made, js = bake_scene(context.scene, st.substeps, st.master, st.room, st.props, msgs.append,
                                      st.motors, st.motor_level)
        counts = {}
        for e in events:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        info = ", ".join("%d %s" % (n, k) for k, n in sorted(counts.items())) or "no contacts found"
        self.report({"INFO"}, "Foley: %s (%s)" % (info, msgs[0] if msgs else ""))
        return {"FINISHED"}


class FOLEY_OT_clear(bpy.types.Operator):
    """Remove the contact-sound strips (FX ...) and nothing else"""
    bl_idname = "foley.clear"
    bl_label = "Clear"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = place.clear(context.scene)
        self.report({"INFO"}, "Removed %d contact sounds" % n)
        return {"FINISHED"}


class FOLEY_OT_mixdown(bpy.types.Operator):
    """Write the shot's audio to a WAV next to the .blend"""
    bl_idname = "foley.mixdown"
    bl_label = "Mixdown"

    def execute(self, context):
        base = bpy.data.filepath or os.path.join(bpy.app.tempdir, "shot.blend")
        out = os.path.splitext(base)[0] + "_foley.wav"
        place.mixdown(out, context.scene)
        self.report({"INFO"}, "Wrote " + out)
        return {"FINISHED"}


class FOLEY_OT_audition(bpy.types.Operator):
    """Hear one footstep and one grab from the selected droid at a walk and at a stomp"""
    bl_idname = "foley.audition"
    bl_label = "Hear this droid"

    speed: bpy.props.FloatProperty(default=0.4)

    def execute(self, context):
        arm = context.active_object
        if arm is None or arm.type != "ARMATURE":
            self.report({"WARNING"}, "Select a droid's armature")
            return {"CANCELLED"}
        live.contact(arm, "foot.L", self.speed)
        return {"FINISHED"}


def _draw(self, context):
    lay = self.layout
    st = context.scene.ship_foley
    row = lay.row(align=True)
    row.scale_y = 1.4
    row.operator("foley.bake", icon="SPEAKER")
    row.operator("foley.clear", text="", icon="TRASH")
    row.operator("foley.mixdown", text="", icon="EXPORT")
    row = lay.row(align=True)
    row.prop(st, "master")
    row.prop(st, "room")
    row = lay.row(align=True)
    row.prop(st, "substeps")
    row.prop(st, "props", toggle=True)
    row = lay.row(align=True)
    row.prop(st, "motors", toggle=True)
    row.prop(st, "motor_level", text="Level")
    ob = context.active_object
    if ob is not None and ob.type == "ARMATURE":
        prof = detect.profile_for(ob)
        box = lay.box()
        box.label(text="%s: %d kg" % (prof["label"], prof["mass_kg"]), icon="ARMATURE_DATA")
        row = box.row(align=True)
        row.prop(ob, "foley_profile_ui", text="")
        row.prop(ob, "foley_mass_ui", text="kg")
        row = box.row(align=True)
        row.operator("foley.audition", text="Soft step").speed = 0.15
        row.operator("foley.audition", text="Walk").speed = 0.4
        row.operator("foley.audition", text="Stomp").speed = 1.2


class FOLEY_PT_view3d(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Foley"
    bl_label = "Contact sounds"
    draw = _draw


class FOLEY_PT_seq(bpy.types.Panel):
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Foley"
    bl_label = "Contact sounds"
    draw = _draw


def _get_prof(self):
    pid = self.get("foley_profile") or detect.profile_for(self)["id"]
    return list(profiles.DROIDS).index(pid) if pid in profiles.DROIDS else 0


def _set_prof(self, i):
    self["foley_profile"] = list(profiles.DROIDS)[i]


def _get_mass(self):
    return float(self.get("foley_mass_kg") or detect.profile_for(self)["mass_kg"])


def _set_mass(self, v):
    self["foley_mass_kg"] = float(v)


CLASSES = (FOLEY_Settings, FOLEY_OT_bake, FOLEY_OT_clear, FOLEY_OT_mixdown, FOLEY_OT_audition,
           FOLEY_PT_view3d, FOLEY_PT_seq)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.ship_foley = bpy.props.PointerProperty(type=FOLEY_Settings)
    bpy.types.Object.foley_profile_ui = bpy.props.EnumProperty(
        name="Droid", items=PROFILE_ITEMS, get=_get_prof, set=_set_prof,
        description="Which droid this is (sets weight, sole and finger materials)")
    bpy.types.Object.foley_mass_ui = bpy.props.FloatProperty(
        name="Weight", min=0.5, max=5000.0, get=_get_mass, set=_set_mass,
        description="Droid weight in kg: heavier droids hit harder and sound deeper")
    bpy.app.timers.register(_hook, first_interval=1.0, persistent=True)
    bpy.app.handlers.load_post.append(_on_load)


def _hook():
    live.attach_walk()
    return 5.0          # keep checking: Ship Builder may be enabled later


@bpy.app.handlers.persistent
def _on_load(_):
    live.attach_walk()


def unregister():
    if bpy.app.timers.is_registered(_hook):
        bpy.app.timers.unregister(_hook)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    live.detach_walk()
    del bpy.types.Object.foley_mass_ui
    del bpy.types.Object.foley_profile_ui
    del bpy.types.Scene.ship_foley
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
