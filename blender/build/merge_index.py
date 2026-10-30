"""Merge index_parts/*.json into library.json, keeping anything the user saved (source == 'blender')
rows from other tools (mocap, performance motions) and usage counts.   python3 merge_index.py LIBRARY_DIR"""
import glob
import json
import os
import sys

lib = sys.argv[1]
p = os.path.join(lib, 'library.json')
old = json.load(open(p)) if os.path.exists(p) else {'version': 1, 'items': []}
usage = {i['id']: {k: i[k] for k in ('uses', 'last_used') if k in i} for i in old['items']}
# rows other tools add to the library survive a rebuild: your own saves, mocap and performance motions
KEEP = {'blender', 'cmu-mocap', 'mesh2motion', 'performance'}
items = [i for i in old['items'] if i.get('source') in KEEP or str(i.get('source', '')).startswith('ext:')]
ids = {i['id'] for i in items}
order = ['motions', 'faces', 'mouth_sets', 'props', 'scenery', 'sets_rooms']
parts = sorted(glob.glob(os.path.join(lib, 'index_parts', '*.json')),
               key=lambda f: order.index(os.path.basename(f)[:-5]) if os.path.basename(f)[:-5] in order else 99)
for f in parts:
    if os.path.basename(f) == 'sets.json':
        continue  # Doodle Studio auto-layout rules: superseded by the hand-dressed room sets
    for row in json.load(open(f)):
        if row['id'] in ids:
            continue
        row.update(usage.get(row['id'], {}))
        row.setdefault('uses', 0)
        prev = os.path.join(lib, 'previews', row['category'], row['id'] + '.png')
        if os.path.exists(prev):
            row['preview'] = 'previews/%s/%s.png' % (row['category'], row['id'])
        items.append(row)
        ids.add(row['id'])
json.dump({'version': 1, 'items': items}, open(p, 'w'), indent=1)
from collections import Counter
print(Counter(i['category'] for i in items))
