"""Where the library and the 3D Bunny live on disk."""
import os
import sys

ADDON = __package__

_DOCS = os.path.join(os.path.expanduser('~'), 'Documents', 'Talking Character App')


def _prefs():
    try:
        import bpy
        a = bpy.context.preferences.addons.get(ADDON)
        return a.preferences if a else None
    except Exception:
        return None


def library_root():
    p = _prefs()
    if p and p.library_dir:
        return bpy_abspath(p.library_dir)
    return os.environ.get('DSL_LIBRARY') or os.path.join(_DOCS, 'blender-library')


def bunny_dir():
    p = _prefs()
    if p and p.bunny_dir:
        return bpy_abspath(p.bunny_dir)
    if os.environ.get('DSL_BUNNY'):
        return os.environ['DSL_BUNNY']
    sib = os.path.join(os.path.dirname(library_root().rstrip('/\\')), 'blender-bunny')
    return sib if os.path.isdir(sib) else os.path.join(_DOCS, 'blender-bunny')


def bpy_abspath(p):
    try:
        import bpy
        return os.path.normpath(bpy.path.abspath(p))
    except Exception:
        return p


def lib_path(*parts):
    return os.path.join(library_root(), *parts)


def bunny_module(name):
    """Import one of the 3D Bunny's own modules (look, ds_map, collision...) so
    the library always uses the rig thread's current code instead of a copy."""
    d = os.path.join(bunny_dir(), 'lib')
    if not os.path.isdir(d):
        raise RuntimeError('3D Bunny not found at %s (set it in the add-on preferences)' % bunny_dir())
    if d not in sys.path:
        sys.path.insert(0, d)
    return __import__(name)
