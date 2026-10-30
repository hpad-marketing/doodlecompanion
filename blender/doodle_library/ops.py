"""Operators behind the Doodle panels."""
import os
import subprocess
import sys

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import api, capture, index, paths, sets, style, ui


def _report_errors(fn):
    def run(self, context):
        try:
            return fn(self, context)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
    return run


class DSL_OT_refresh(bpy.types.Operator):
    bl_idname = 'dsl.refresh'
    bl_label = 'Reload library'
    bl_description = 'Re-read the library folder (after another app or file added assets)'

    def execute(self, context):
        index.load(force=True)
        ui.refresh(None, context)
        return {'FINISHED'}


class DSL_OT_insert(bpy.types.Operator):
    bl_idname = 'dsl.insert'
    bl_label = 'Insert'
    bl_description = 'Insert the selected library item'
    bl_options = {'REGISTER', 'UNDO'}
    item_id: StringProperty()

    @_report_errors
    def execute(self, context):
        wm = context.window_manager
        it = index.get(self.item_id)
        opts = {}
        if it['category'] == 'motion':
            opts = dict(fix_clipping=wm.dsl_opt_fix, mirror=wm.dsl_opt_mirror, include_camera=wm.dsl_opt_camera)
        elif it['category'] == 'prop':
            opts = dict(hold=wm.dsl_opt_hold, location=context.scene.cursor.location.copy())
        elif it['category'] in ('scenery', 'card'):
            opts = dict(location=context.scene.cursor.location.copy())
        res = api.insert(self.item_id, **opts)
        if isinstance(res, dict) and res.get('clip_fixes'):
            self.report({'INFO'}, '%s: %d frames, clipping fixed on %d keys' % (it['name'], res['frames'], res['clip_fixes']))
        else:
            self.report({'INFO'}, 'Inserted ' + it['name'])
        return {'FINISHED'}


class _Named:
    name: StringProperty(name='Name', default='')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class DSL_OT_save_motion(_Named, bpy.types.Operator):
    bl_idname = 'dsl.save_motion'
    bl_label = 'Save motion to library'
    bl_description = "Store Bunny's animation (whole action, or the preview range if set) as a library motion"
    only_range: BoolProperty(name='Only the preview range', default=False)

    @_report_errors
    def execute(self, context):
        sc = context.scene
        fr = (sc.frame_preview_start, sc.frame_preview_end) if (self.only_range and sc.use_preview_range) else None
        it = api.save_motion(self.name or 'My motion', fr)
        self.report({'INFO'}, 'Saved motion ' + it['name'])
        ui.refresh(None, context)
        return {'FINISHED'}


class DSL_OT_save_face(_Named, bpy.types.Operator):
    bl_idname = 'dsl.save_face'
    bl_label = 'Save face to library'
    bl_description = "Store Bunny's current expression, gaze and mouth as a library face"

    @_report_errors
    def execute(self, context):
        it = api.save_expression(self.name or 'My face')
        self.report({'INFO'}, 'Saved face ' + it['name'])
        ui.refresh(None, context)
        return {'FINISHED'}


class DSL_OT_save_selection(_Named, bpy.types.Operator):
    bl_idname = 'dsl.save_selection'
    bl_label = 'Save selection to library'
    bl_description = 'Store the selected objects as one library asset (joined copy, origin at the active object)'
    category: EnumProperty(name='Section', items=[('prop', 'Prop', ''), ('scenery', 'Scenery', '')])

    @_report_errors
    def execute(self, context):
        objs = [context.active_object] + [o for o in context.selected_objects if o is not context.active_object]
        it = api.save_objects([o for o in objs if o], self.name or (objs[0].name if objs and objs[0] else 'Asset'), self.category)
        self.report({'INFO'}, 'Saved ' + it['name'])
        ui.refresh(None, context)
        return {'FINISHED'}


class DSL_OT_set_all(bpy.types.Operator):
    bl_idname = 'dsl.set_all'
    bl_label = 'All pieces'
    bl_options = {'UNDO'}
    on: BoolProperty()

    def execute(self, context):
        for it in context.window_manager.dsl_set_props:
            it.on = self.on
        return {'FINISHED'}


class DSL_OT_declutter(bpy.types.Operator):
    bl_idname = 'dsl.declutter'
    bl_label = 'Declutter'
    bl_description = 'Keep the four biggest pieces of the set and hide the rest'
    bl_options = {'UNDO'}

    @_report_errors
    def execute(self, context):
        sets.declutter(4)
        ui.sync_set_props(context)
        return {'FINISHED'}


class DSL_OT_camera(bpy.types.Operator):
    bl_idname = 'dsl.camera'
    bl_label = 'Eye-level camera'
    bl_description = 'Perspective camera at eye level, framed like Doodle Studio (needed for parallax)'
    bl_options = {'UNDO'}

    def execute(self, context):
        cam = sets.setup_camera()
        style.retarget_camera(cam)
        return {'FINISHED'}


class DSL_OT_parallax(bpy.types.Operator):
    bl_idname = 'dsl.parallax'
    bl_label = 'Add parallax move'
    bl_description = 'Key an eased camera move from the playhead that shows the depth of the set'
    bl_options = {'UNDO'}

    @_report_errors
    def execute(self, context):
        wm = context.window_manager
        sets.parallax_camera(wm.dsl_parallax_mode, wm.dsl_parallax_frames, wm.dsl_parallax_amount)
        return {'FINISHED'}


class DSL_OT_retarget(bpy.types.Operator):
    bl_idname = 'dsl.retarget'
    bl_label = 'Re-aim ink'
    bl_description = 'Point every library asset\'s ink at the active camera (after switching cameras)'

    def execute(self, context):
        n = style.retarget_camera(context.scene.camera)
        self.report({'INFO'}, '%d objects re-aimed' % n)
        return {'FINISHED'}


class DSL_OT_inbox(bpy.types.Operator):
    bl_idname = 'dsl.inbox'
    bl_label = 'Add to library collection'
    bl_description = 'Make the "Add to Doodle Library" collection: anything you put in it is saved to the library when you save'

    def execute(self, context):
        capture.ensure_inbox()
        return {'FINISHED'}


class DSL_OT_open_folder(bpy.types.Operator):
    bl_idname = 'dsl.open_folder'
    bl_label = 'Open library folder'

    def execute(self, context):
        p = paths.library_root()
        if sys.platform.startswith('win'):
            os.startfile(p)
        else:
            subprocess.Popen(['xdg-open' if sys.platform.startswith('linux') else 'open', p])
        return {'FINISHED'}


class DSL_OT_prefs(bpy.types.Operator):
    bl_idname = 'dsl.prefs'
    bl_label = 'Doodle Library preferences'

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        context.preferences.active_section = 'ADDONS'
        context.window_manager.addon_search = 'Doodle Library'
        return {'FINISHED'}


CLASSES = (DSL_OT_refresh, DSL_OT_insert, DSL_OT_save_motion, DSL_OT_save_face, DSL_OT_save_selection,
           DSL_OT_set_all, DSL_OT_declutter, DSL_OT_camera, DSL_OT_parallax, DSL_OT_retarget, DSL_OT_inbox,
           DSL_OT_open_folder, DSL_OT_prefs)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
