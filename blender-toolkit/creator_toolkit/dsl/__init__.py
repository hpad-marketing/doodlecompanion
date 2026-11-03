"""Doodle Library inside the Creator Toolkit: the same code Doodle Studio 3D ships as the
"Doodle Library" add-on (sets, props, faces, motions, outfits, effects, time of day, storytime
kit, grips, placement, collision guard). If that add-on is also turned on, it stays in charge
and this copy stays quiet, so nothing is registered twice."""

import os  # noqa: E402

import bpy  # noqa: E402
from bpy.app.handlers import persistent  # noqa: E402

from . import capture, gpu, index, ops, paths, ui  # noqa: E402

LIB_NAME = 'Doodle Library'


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


_active = {'on': False}


def standalone_enabled():
    keys = bpy.context.preferences.addons.keys()
    return any(k == 'doodle_library' or k.endswith('.doodle_library') for k in keys)


def register():
    if standalone_enabled():
        return
    _active['on'] = True
    ui.register()
    ops.register()
    capture.register()
    gpu.register()
    bpy.app.handlers.load_post.append(on_load)
    bpy.app.timers.register(_first_refresh, first_interval=0.5, persistent=True)


def unregister():
    if not _active['on']:
        return
    _active['on'] = False
    if bpy.app.timers.is_registered(_first_refresh):
        bpy.app.timers.unregister(_first_refresh)
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
    gpu.unregister()
    capture.unregister()
    ops.unregister()
    ui.unregister()
