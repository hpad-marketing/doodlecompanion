"""Outfits and side-cast accessories from the clothing studio.

Outfits live in the library at outfits/<id>/ (outfit.blend + outfit.json +
thumb.png) and replace the hoodie. Accessories (glasses, ties) have no .blend:
they are built on the open character so they fit every head, and several can be
worn at once. Both run the clothing studio's own scripts, copied into the
library's outfits folder, so its fixes reach this add-on without a copy here.
"""
import importlib
import os
import sys

from . import index, paths


BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outfit_scripts')
_dir = None


def _scripts_dir():
    """The library's own copy of the clothing studio scripts, unless it predates the
    Blender 5.2 fix (gn_values: nodes-modifier inputs are no longer ID properties there).
    Then the patched copy bundled with this add-on is used, all four scripts together."""
    global _dir
    if _dir:
        return _dir
    d = paths.lib_path('outfits')
    try:
        with open(os.path.join(d, 'apply_outfit.py'), encoding='utf-8') as f:
            fixed = 'def gn_values' in f.read()
    except OSError:
        fixed = False
    _dir = d if fixed else BUNDLED
    return _dir


def _script(name):
    d = _scripts_dir()
    if not os.path.isfile(os.path.join(d, name + '.py')):
        raise RuntimeError('%s.py is missing from the library outfits folder.' % name)
    if d not in sys.path:
        sys.path.insert(0, d)  # apply_outfit and apply_accessory import each other by name
    return importlib.import_module(name)


def dress(item):
    coll = _script('apply_outfit').dress(paths.lib_path(os.path.join('outfits', item['data']['outfit'])))
    index.mark_used(item['id'])
    return coll


def undress():
    _script('apply_outfit').undress()


def wear(item):
    r = _script('apply_accessory').wear(item['data']['accessory'])
    index.mark_used(item['id'])
    return r


def take_off(item):
    return _script('apply_accessory').remove(item['data']['accessory'])


def worn_accessories():
    try:
        return list(_script('apply_accessory').worn())
    except Exception:
        return []
