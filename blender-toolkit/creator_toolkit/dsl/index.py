"""library.json: one row per asset, plus how often and when it was last used."""
import json
import os
import time

from . import paths

CATEGORIES = [
    ('motion', 'Motions', 'Bunny motions (Doodle Studio library and your own)', 'ARMATURE_DATA'),
    ('expression', 'Faces', 'Expressions, gazes, blinks and winks', 'USER'),
    ('mouth_set', 'Mouths', 'Mouth sets for lip sync', 'SPEAKER'),
    ('outfit', 'Outfits', 'Brand-black outfits that replace the hoodie (Bunny, Koala, Frog)', 'MOD_CLOTH'),
    ('accessory', 'Accessories', 'Glasses and ties for the side cast; wear several at once', 'MOD_CLOTH'),
    ('prop', 'Props', '360° props (3D) and your own', 'OBJECT_DATA'),
    ('scenery', 'Scenery', 'Background pieces rebuilt in 3D', 'MESH_CUBE'),
    ('card', '2D cards', 'Doodle Studio background drawings as flat cards that sit in 3D', 'IMAGE_PLANE'),
    ('set', 'Sets', 'Whole rooms built around Bunny', 'SCENE_DATA'),
]

_cache = {'mtime': None, 'data': None}


def path():
    return paths.lib_path('library.json')


KEEP = {'blender', 'cmu-mocap', 'mesh2motion', 'performance'}  # rows other tools add survive a rebuild
PART_ORDER = ['motions', 'faces', 'faces_story', 'mouth_sets', 'outfits', 'accessories', 'props', 'packs', 'scenery', 'sets_rooms']


def merge_parts(lib, quiet=True):
    """Rebuild library.json from index_parts/*.json, keeping your own saves, rows from other
    tools and every use count. Runs by itself when a library update brings newer parts."""
    import glob
    p = os.path.join(lib, 'library.json')
    old = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'version': 1, 'items': []}
    usage = {i['id']: {k: i[k] for k in ('uses', 'last_used') if k in i} for i in old['items']}
    items = [i for i in old['items'] if i.get('source') in KEEP or str(i.get('source', '')).startswith('ext:')]
    ids = {i['id'] for i in items}
    parts = sorted(glob.glob(os.path.join(lib, 'index_parts', '*.json')),
                   key=lambda f: PART_ORDER.index(os.path.basename(f)[:-5]) if os.path.basename(f)[:-5] in PART_ORDER
                   else 99)
    for f in parts:
        if os.path.basename(f) == 'sets.json':
            continue  # Doodle Studio auto-layout rules: superseded by the hand-dressed room sets
        for row in json.load(open(f, encoding='utf-8')):
            if row['id'] in ids:
                continue
            row.update(usage.get(row['id'], {}))
            row.setdefault('uses', 0)
            prev = os.path.join(lib, 'previews', row['category'], row['id'] + '.png')
            if os.path.exists(prev):
                row['preview'] = 'previews/%s/%s.png' % (row['category'], row['id'])
            items.append(row)
            ids.add(row['id'])
    tmp = '%s.%d.tmp' % (p, os.getpid())
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump({'version': 1, 'items': items}, fh, indent=1)
    os.replace(tmp, p)
    if not quiet:
        from collections import Counter
        print(Counter(i['category'] for i in items))
    return items


def _parts_newer(p):
    import glob
    parts = glob.glob(os.path.join(os.path.dirname(p), 'index_parts', '*.json'))
    if not parts:
        return False
    return not os.path.exists(p) or max(os.path.getmtime(f) for f in parts) > os.path.getmtime(p)


def load(force=False):
    p = path()
    try:
        if _parts_newer(p):
            merge_parts(os.path.dirname(p))
    except OSError as e:
        print('Doodle Library: could not merge the library update:', e)
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
    tmp = '%s.%d.tmp' % (p, os.getpid())  # two Blenders saving at once never share a temp file
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
    try:
        save(data)
    except OSError as e:  # usage counts are a nicety: never fail an insert over them
        print('Doodle Library: could not save usage count:', e)


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
