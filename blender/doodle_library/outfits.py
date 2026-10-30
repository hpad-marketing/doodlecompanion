"""Outfits from the clothing studio: brand-black garments that replace the hoodie.

Each outfit lives in the library at outfits/<id>/ (outfit.blend + outfit.json +
thumb.png). Dressing runs the clothing studio's own apply_outfit.py from the
library's outfits folder, so its fixes reach this add-on without a copy here.
"""
import importlib.util
import os

from . import index, paths


def _apply_module():
    p = paths.lib_path(os.path.join('outfits', 'apply_outfit.py'))
    if not os.path.isfile(p):
        raise RuntimeError('apply_outfit.py is missing from the library outfits folder.')
    spec = importlib.util.spec_from_file_location('dsl_apply_outfit', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dress(item):
    d = paths.lib_path(os.path.join('outfits', item['data']['outfit']))
    coll = _apply_module().dress(d)
    index.mark_used(item['id'])
    return coll


def undress():
    _apply_module().undress()
