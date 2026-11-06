"""Where the library and the 3D Bunny live on disk."""
import os
import sys

ADDON = __package__

_DOCS = os.path.join(os.path.expanduser('~'), 'Documents', 'Talking Character App')


class _ToolkitPrefs:
    """The Creator Toolkit's preferences, seen through the Doodle Library's names."""
    def __init__(self, p):
        self.library_dir = getattr(p, 'doodle_lib_dir', '')
        self.bunny_dir = getattr(p, 'doodle_bunny_dir', '')
        self.auto_capture = getattr(p, 'doodle_auto_capture', True)


def _prefs():
    try:
        import bpy
        addons = bpy.context.preferences.addons
        for k in addons.keys():  # the standalone add-on, when it is on, stays in charge
            if k == 'doodle_library' or k.endswith('.doodle_library'):
                return addons[k].preferences
        top = ADDON.rsplit('.', 1)[0]
        a = addons.get(top)
        return _ToolkitPrefs(a.preferences) if a and a.preferences else None
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
    for d in (sib, os.path.join(_DOCS, 'blender-bunny')):
        if os.path.isdir(os.path.join(d, 'lib')):
            return d
    # no 3D Bunny folder on this PC: use the copy of its code that ships inside the Toolkit
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bunny')


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
    shipped = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bunny', 'lib')
    if os.path.isdir(shipped) and os.path.normcase(shipped) != os.path.normcase(d) and shipped not in sys.path:
        # the Toolkit ships a copy of the Bunny's code: whichever is newer goes first, and the other
        # still supplies modules the first lacks (an older Bunny folder has no powers.py)
        def age(folder):
            try:
                return os.path.getmtime(os.path.join(folder, 'look.py'))
            except OSError:
                return 0
        first, second = (shipped, d) if age(shipped) > age(d) else (d, shipped)
        for x in (first, second):
            if x in sys.path:
                sys.path.remove(x)
        sys.path[0:0] = [first]
        sys.path.append(second)
    elif d not in sys.path:
        sys.path.insert(0, d)
    return __import__(name)
