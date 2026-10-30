"""Copy the clothing studio's approved outfits into the library and index them.

  python3 build_outfits.py CLOTHING_LIBRARY_DIR LIBRARY_DIR
CLOTHING_LIBRARY_DIR holds outfits/<id>/{outfit.blend,outfit.json,thumb.png};
the scripts come from the clothing studio's scripts/ next to it."""
import json
import os
import shutil
import sys

src, lib = sys.argv[1], sys.argv[2]
out = os.path.join(lib, 'outfits')
os.makedirs(out, exist_ok=True)
os.makedirs(os.path.join(lib, 'previews', 'outfit'), exist_ok=True)
for f in ('apply_outfit.py', 'apply_accessory.py', 'accessories.py', 'garmentlib.py'):
    shutil.copy2(os.path.join(src, '..', 'scripts', f), os.path.join(out, f))
rows = []
for oid in sorted(os.listdir(os.path.join(src, 'outfits'))):
    d = os.path.join(src, 'outfits', oid)
    if not os.path.isfile(os.path.join(d, 'outfit.json')):
        continue
    man = json.load(open(os.path.join(d, 'outfit.json')))
    shutil.copytree(d, os.path.join(out, oid), dirs_exist_ok=True)
    shutil.copy2(os.path.join(d, 'thumb.png'), os.path.join(lib, 'previews', 'outfit', 'outfit-%s.png' % oid))
    rows.append({'id': 'outfit-' + oid, 'name': man['name'], 'category': 'outfit', 'kind': 'outfit',
                 'sub': 'Outfits', 'description': man.get('description', ''), 'data': {'outfit': oid},
                 'source': 'clothing-studio', 'tags': ['outfit'], 'preview': 'previews/outfit/outfit-%s.png' % oid})
json.dump(rows, open(os.path.join(lib, 'index_parts', 'outfits.json'), 'w'), indent=0)
print('outfits', len(rows))

# accessories: built on the open character, so only the manifest and thumb travel; 'maybe' stays out
acc = []
os.makedirs(os.path.join(lib, 'previews', 'accessory'), exist_ok=True)
for aid in sorted(os.listdir(os.path.join(src, 'accessories'))):
    f = os.path.join(src, 'accessories', aid, 'accessory.json')
    if not os.path.isfile(f):
        continue
    man = json.load(open(f))
    if man.get('status') != 'approved':
        continue
    shutil.copy2(os.path.join(src, 'accessories', aid, 'thumb.png'),
                 os.path.join(lib, 'previews', 'accessory', 'accessory-%s.png' % aid))
    acc.append({'id': 'accessory-' + aid, 'name': man['name'], 'category': 'accessory', 'kind': 'accessory',
                'sub': 'Accessories', 'description': man.get('description', ''), 'data': {'accessory': aid},
                'source': 'clothing-studio', 'tags': ['accessory'] + man.get('fits', []),
                'preview': 'previews/accessory/accessory-%s.png' % aid})
json.dump(acc, open(os.path.join(lib, 'index_parts', 'accessories.json'), 'w'), indent=0)
print('accessories', len(acc), [a['id'] for a in acc])
