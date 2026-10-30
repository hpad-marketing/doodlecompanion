"""library.json: one row per asset, plus how often and when it was last used."""
import json
import os
import time

from . import paths

CATEGORIES = [
    ('motion', 'Motions', 'Bunny motions (Doodle Studio library and your own)', 'ARMATURE_DATA'),
    ('expression', 'Faces', 'Expressions, gazes, blinks and winks', 'USER'),
    ('mouth_set', 'Mouths', 'Mouth sets for lip sync', 'SPEAKER'),
    ('prop', 'Props', '360° props (3D) and your own', 'OBJECT_DATA'),
    ('scenery', 'Scenery', 'Background pieces rebuilt in 3D', 'MESH_CUBE'),
    ('card', '2D cards', 'Doodle Studio background drawings as flat cards that sit in 3D', 'IMAGE_PLANE'),
    ('set', 'Sets', 'Whole rooms built around Bunny', 'SCENE_DATA'),
]

_cache = {'mtime': None, 'data': None}


def path():
    return paths.lib_path('library.json')


def load(force=False):
    p = path()
    if not os.path.exists(p):
        return {'version': 1, 'items': []}
    m = os.path.getmtime(p)
    if force or _cache['mtime'] != m:
        with open(p, encoding='utf-8') as f:
            _cache['data'] = json.load(f)
        _cache['mtime'] = m
    return _cache['data']


def save(data):
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)
    _cache['data'] = data
    _cache['mtime'] = os.path.getmtime(p)


def items(category=None):
    return [i for i in load()['items'] if category is None or i['category'] == category]


def get(item_id):
    for i in load()['items']:
        if i['id'] == item_id:
            return i
    return None


def unique_id(base):
    base = ''.join(c if c.isalnum() else '-' for c in base.lower()).strip('-') or 'asset'
    ids = {i['id'] for i in load()['items']}
    out, n = base, 2
    while out in ids:
        out, n = '%s-%d' % (base, n), n + 1
    return out


def add(item):
    data = load(force=True)
    data['items'] = [i for i in data['items'] if i['id'] != item['id']] + [item]
    item.setdefault('uses', 0)
    item.setdefault('added', time.strftime('%Y-%m-%dT%H:%M:%S'))
    save(data)
    return item


def mark_used(item_id):
    data = load(force=True)
    for i in data['items']:
        if i['id'] == item_id:
            i['uses'] = i.get('uses', 0) + 1
            i['last_used'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    save(data)


def blob(rel):
    """Big per-category data files (motions, mouth sets) cached by mtime."""
    p = paths.lib_path(rel)
    key = 'blob:' + p
    m = os.path.getmtime(p)
    hit = _cache.get(key)
    if not hit or hit[0] != m:
        with open(p, encoding='utf-8') as f:
            hit = (m, json.load(f))
        _cache[key] = hit
    return hit[1]
