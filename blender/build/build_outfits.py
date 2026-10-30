"""Copy the clothing studio's approved outfits into the library and index them.

  python3 build_outfits.py CLOTHING_LIBRARY_DIR LIBRARY_DIR
CLOTHING_LIBRARY_DIR holds outfits/<id>/{outfit.blend,outfit.json,thumb.png};
apply_outfit.py comes from the clothing studio's scripts/ next to it."""
import json
import os
import shutil
import sys

src, lib = sys.argv[1], sys.argv[2]
out = os.path.join(lib, 'outfits')
os.makedirs(out, exist_ok=True)
os.makedirs(os.path.join(lib, 'previews', 'outfit'), exist_ok=True)
shutil.copy2(os.path.join(src, '..', 'scripts', 'apply_outfit.py'), os.path.join(out, 'apply_outfit.py'))
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
