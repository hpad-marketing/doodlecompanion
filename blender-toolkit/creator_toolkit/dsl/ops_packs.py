"""Buttons for the asset packs: effects, time of day, skies, reactions, lids, screens, seats,
physics and foreground framing. Every button calls the same function the API exposes."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

from . import fx, interact, lighting, packs, storytime


def _items(names):
    return [(n, n.replace('_', ' ').capitalize(), '') for n in names]


class DSL_OT_effect(bpy.types.Operator):
    """Add an effect around Bunny (loops keep going; bursts go off at the playhead)"""
    bl_idname = 'dsl.effect'
    bl_label = 'Add effect'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Effect', items=_items(fx.EFFECTS))
    amount: FloatProperty(name='Amount', default=1.0, min=0.05, max=4.0)

    def execute(self, context):
        ob = fx.add_effect(self.kind, amount=self.amount)
        self.report({'INFO'}, 'Added %s' % ob.name)
        return {'FINISHED'}


class DSL_OT_time(bpy.types.Operator):
    """Light the whole scene for this time of day (night switches every lamp on)"""
    bl_idname = 'dsl.time'
    bl_label = 'Time of day'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Time', items=_items(lighting.TIMES))
    key: BoolProperty(name='Key at playhead', default=False)

    def execute(self, context):
        lighting.set_time(self.kind, context.scene.frame_current if self.key else None)
        return {'FINISHED'}


class DSL_OT_sky(bpy.types.Operator):
    """A hand-drawn sky behind outdoor sets"""
    bl_idname = 'dsl.sky'
    bl_label = 'Sky'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Sky', items=_items(lighting.SKIES))

    def execute(self, context):
        lighting.sky(self.kind)
        return {'FINISHED'}


class DSL_OT_lightning(bpy.types.Operator):
    """Lightning flash at the playhead"""
    bl_idname = 'dsl.lightning'
    bl_label = 'Lightning'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lighting.lightning(context.scene.frame_current)
        return {'FINISHED'}


class DSL_OT_react(bpy.types.Operator):
    """Pop a reaction over Bunny's head at the playhead"""
    bl_idname = 'dsl.react'
    bl_label = 'Reaction'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Reaction', items=_items(packs.REACTIONS))

    def execute(self, context):
        packs.react(self.kind)
        return {'FINISHED'}


class DSL_OT_open(bpy.types.Operator):
    """Open or close the selected piece's lid, doors, curtain or flap (keyed at the playhead)"""
    bl_idname = 'dsl.open'
    bl_label = 'Open / close'
    bl_options = {'REGISTER', 'UNDO'}
    amount: FloatProperty(name='Open', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    key: BoolProperty(name='Key it', default=True)

    def execute(self, context):
        ob = context.active_object
        n = packs.set_open(ob, self.amount, context.scene.frame_current if self.key else None)
        if not n:
            self.report({'WARNING'}, 'Nothing on %s opens.' % ob.name)
        return {'FINISHED'}


class DSL_OT_screen(bpy.types.Operator):
    """Show your own image or video on the selected screen, frame or poster"""
    bl_idname = 'dsl.screen'
    bl_label = 'Show my clip'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg;*.mp4;*.mov;*.webm', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        packs.set_screen(context.active_object, bpy.path.abspath(self.filepath))
        return {'FINISHED'}


class DSL_OT_sit(bpy.types.Operator):
    """Bunny sits on the nearest seat (or the selected sit spot) at the playhead"""
    bl_idname = 'dsl.sit'
    bl_label = 'Sit down'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        spot = ob if ob and ob.get('dsl_anchor') == 'sit' else None
        if spot is None and ob is not None:
            spot = next((c for c in ob.children if c.get('dsl_anchor') == 'sit'), None)
        try:
            s = interact.sit(spot)
        except RuntimeError as e:
            self.report({'WARNING'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Sitting on %s' % (s.parent.name if s.parent else s.name))
        return {'FINISHED'}


class DSL_OT_physics(bpy.types.Operator):
    """Make the selected prop fall, bounce and settle (sets, furniture and Bunny collide)"""
    bl_idname = 'dsl.physics'
    bl_label = 'Physics'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Acts like', items=_items(interact.PHYSICS))

    def execute(self, context):
        interact.physics(context.active_object, self.kind)
        interact.simulate()
        return {'FINISHED'}


class DSL_OT_frame_shot(bpy.types.Operator):
    """Park the selected framing piece near the lens on a third (frame within a frame)"""
    bl_idname = 'dsl.frame_shot'
    bl_label = 'Frame the shot'
    bl_options = {'REGISTER', 'UNDO'}
    side: EnumProperty(items=[('left', 'Left third', ''), ('right', 'Right third', '')])

    def execute(self, context):
        packs.frame_shot(context.active_object, self.side)
        return {'FINISHED'}


class DSL_OT_chat(bpy.types.Operator):
    """A phone chat that fills in message by message (one line each: 'me: text' or 'them: text')"""
    bl_idname = 'dsl.chat'
    bl_label = 'Text chat'
    bl_options = {'REGISTER', 'UNDO'}
    lines: StringProperty(name='Messages', default='them: you up? | me: no')
    gap: bpy.props.IntProperty(name='Frames apart', default=18, min=4)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, context):
        msgs = []
        for part in self.lines.split('|'):
            who, _, text = part.partition(':')
            if text.strip():
                msgs.append((who.strip().lower(), text.strip()))
        storytime.chat(msgs, gap=self.gap)
        return {'FINISHED'}


class DSL_OT_pin_label(bpy.types.Operator):
    """A hand-lettered label with an arrow pointing at the selected object"""
    bl_idname = 'dsl.pin_label'
    bl_label = 'Label + arrow'
    bl_options = {'REGISTER', 'UNDO'}
    text: StringProperty(name='Label', default='this one')
    side: EnumProperty(items=[('right', 'Right', ''), ('left', 'Left', '')])

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not context.active_object:
            self.report({'WARNING'}, 'Select what the arrow points at.')
            return {'CANCELLED'}
        storytime.label(context.active_object, self.text, side=self.side)
        return {'FINISHED'}


class DSL_OT_journey(bpy.types.Operator):
    """A map whose path draws itself from stop to stop"""
    bl_idname = 'dsl.journey'
    bl_label = 'Journey map'
    bl_options = {'REGISTER', 'UNDO'}
    stops: StringProperty(name='Stops (comma separated)', default='Home, Office, Beach')
    length: bpy.props.IntProperty(name='Frames', default=96, min=12)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def execute(self, context):
        storytime.journey([s.strip() for s in self.stops.split(',') if s.strip()], length=self.length)
        return {'FINISHED'}


class DSL_OT_time_skip(bpy.types.Operator):
    """A full-frame time-skip card at the playhead"""
    bl_idname = 'dsl.time_skip'
    bl_label = 'Time skip'
    bl_options = {'REGISTER', 'UNDO'}
    text: StringProperty(name='Words', default='3 hours later')
    length: bpy.props.IntProperty(name='Frames', default=36, min=12)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        storytime.time_skip(self.text, length=self.length)
        return {'FINISHED'}


class DSL_OT_horror(bpy.types.Operator):
    """Horror light kit: night, under-light, flicker, vignette, drone (off unless you turn it on)"""
    bl_idname = 'dsl.horror'
    bl_label = 'Horror lights'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        on = not context.scene.get('dsl_horror', False)
        storytime.horror(on)
        self.report({'INFO'}, 'Horror lights on' if on else 'Horror lights off')
        return {'FINISHED'}


class DSL_OT_end_screen(bpy.types.Operator):
    """End screen with two video slots and a subscribe press, from the playhead"""
    bl_idname = 'dsl.end_screen'
    bl_label = 'End screen'
    bl_options = {'REGISTER', 'UNDO'}
    channel: StringProperty(name='Channel', default='DeepInDoodles')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        storytime.end_screen(channel=self.channel)
        return {'FINISHED'}


classes = (DSL_OT_chat, DSL_OT_pin_label, DSL_OT_journey, DSL_OT_time_skip, DSL_OT_horror, DSL_OT_end_screen,
           DSL_OT_effect, DSL_OT_time, DSL_OT_sky, DSL_OT_lightning, DSL_OT_react, DSL_OT_open, DSL_OT_screen,
           DSL_OT_sit, DSL_OT_physics, DSL_OT_frame_shot)
