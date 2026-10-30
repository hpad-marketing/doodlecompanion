"""Doodle Library: Bunny's shared asset library for Blender and Doodle Studio 3D."""
bl_info = {
    'name': 'Doodle Library',
    'author': 'DeepInDoodles',
    'version': (1, 1, 0),
    'blender': (4, 5, 0),
    'location': '3D View › Sidebar › Doodle',
    'description': "Bunny's motions, faces, mouth sets, 360° props and room sets, saved as you use them",
    'category': 'Animation',
}

import os  # noqa: E402

import bpy  # noqa: E402
from bpy.app.handlers import persistent  # noqa: E402
from bpy.props import BoolProperty, StringProperty  # noqa: E402

from . import capture, gpu, index, ops, paths, ui  # noqa: E402

LIB_NAME = 'Doodle Library'


class DSLPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    library_dir: StringProperty(name='Library folder', subtype='DIR_PATH',
                                description='Folder holding library.json (default: Documents/Talking Character App/blender-library)')
    bunny_dir: StringProperty(name='3D Bunny folder', subtype='DIR_PATH',
                              description='Folder holding Bunny3D.blend and lib/ (default: next to the library)')
    auto_capture: BoolProperty(name='Auto-save to library', default=True,
                               description="On every save, store Bunny's new animation, new faces and anything in the 'Add to Doodle Library' collection")

    def draw(self, context):
        L = self.layout
        L.prop(self, 'library_dir')
        L.prop(self, 'bunny_dir')
        L.prop(self, 'auto_capture')
        L.label(text='Using: ' + paths.library_root())


def register_asset_library():
    """Make the folder show up in Blender's own Asset Browser too (drag and drop)."""
    root = paths.library_root()
    if not os.path.isdir(root):
        return
    libs = bpy.context.preferences.filepaths.asset_libraries
    for lib in libs:
        if os.path.normcase(os.path.normpath(lib.path)) == os.path.normcase(os.path.normpath(root)):
            return
    try:
        bpy.ops.preferences.asset_library_add(directory=root)
        libs[-1].name = LIB_NAME
        libs[-1].import_method = 'APPEND'
    except Exception as e:
        print('Doodle Library: could not register the asset library:', e)


@persistent
def on_load(_dummy=None):
    try:
        ui.refresh(None, bpy.context)
        ui._enum_cache['syncing'] = True
        st = dict(bpy.context.scene.get('dsl_set_state', {}) or {})
        if st.get('set'):
            bpy.context.window_manager.dsl_set = st['set']
        ui._enum_cache['syncing'] = False
        ui.sync_set_props(bpy.context)
    except Exception as e:
        ui._enum_cache['syncing'] = False
        print('Doodle Library: refresh after load failed:', e)


def _first_refresh():
    on_load()
    register_asset_library()
    return None


def register():
    bpy.utils.register_class(DSLPreferences)
    ui.register()
    ops.register()
    capture.register()
    gpu.register()
    bpy.app.handlers.load_post.append(on_load)
    bpy.app.timers.register(_first_refresh, first_interval=0.5)


def unregister():
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    gpu.unregister()
    capture.unregister()
    ops.unregister()
    ui.unregister()
    bpy.utils.unregister_class(DSLPreferences)
