"""Port the Doodle Studio data libraries: motions (+ face beats), expressions, mouth sets, room rules.

  python3 build_data.py SRC_DIR FACE_LIBRARY.json OUT_LIBRARY_DIR

SRC_DIR holds the app's src/ files: motion-templates.json, motion-face-profiles.json,
mouth-sets-presets.js, background-auto.json.
"""
import json
import os
import sys

src, face_lib_path, out = sys.argv[1:4]
os.makedirs(os.path.join(out, 'motions'), exist_ok=True)
os.makedirs(os.path.join(out, 'mouths'), exist_ok=True)
os.makedirs(os.path.join(out, 'index_parts'), exist_ok=True)
face_lib = json.load(open(face_lib_path))
FACES = face_lib['faces']
SPEECH = face_lib['speech']

# ---------------------------------------------------------------- motions
tpl = json.load(open(os.path.join(src, 'motion-templates.json')))
prof = json.load(open(os.path.join(src, 'motion-face-profiles.json')))['profiles']
motions, rows = {}, []
for m in tpl['items']:
    n = int(m['frames'])
    poses = {int(round(f)): dict(p) for f, p in m['poses']}
    p = prof.get(m['id'])
    if p:
        # face beats are phases of the motion; they replace the body's ear keys (as in the app)
        for k in ('earLFold', 'earRFold', 'earLForward', 'earRForward'):
            if any(k in pose for _, pose in p['poses']):
                for f in poses:
                    poses[f].pop(k, None)
        for ph, pose in p['poses']:
            f = int(round(ph * n))
            d = poses.setdefault(f, {})
            for k, v in pose.items():
                if k == 'expression':
                    v = FACES.index(v) if v in FACES else 0
                d[k] = v
    item_id = 'motion-' + m['id']
    motions[item_id] = {'frames': n, 'poses': sorted([f, d] for f, d in poses.items()),
                        'linearTracks': m.get('linearTracks', []), 'loop': m.get('loop', False)}
    rows.append({'id': item_id, 'name': m['name'], 'category': 'motion', 'kind': 'ds', 'sub': m['category'],
                 'tags': m.get('tags', []), 'description': m.get('description', '') + (' Face: ' + p['intent'] if p else ''),
                 'source': 'doodle-studio', 'frames': n, 'loop': m.get('loop', False)})
json.dump({'version': 1, 'source': 'Doodle Studio motion-templates.json + motion-face-profiles.json',
           'motions': motions}, open(os.path.join(out, 'motions', 'doodle_studio.json'), 'w'))
print('motions', len(rows))

# ---------------------------------------------------------------- expressions
face_rows = []
for i, name in enumerate(FACES):
    sub = 'Blink & wink' if name.startswith(('WINK', 'BLINK')) else 'Expressions'
    data = {'expression': i, 'gaze': 0, 'speech_mouth': 0, 'blink': 0}
    if name.startswith('BLINK'):
        data = {'expression': 0, 'gaze': 0, 'speech_mouth': 0, 'blink': int(name.split()[-1].split('/')[0])}
    face_rows.append({'id': 'face-%02d' % i, 'name': name.split(' ', 1)[1] if name[:2].isdigit() else name.title(),
                      'category': 'expression', 'kind': 'face', 'sub': sub, 'data': data,
                      'source': 'doodle-studio', 'tags': []})
for g, name in enumerate(face_lib['gazes']):
    if g == 0:
        continue
    face_rows.append({'id': 'gaze-%d' % g, 'name': 'Look ' + name.lower(), 'category': 'expression', 'kind': 'face',
                      'sub': 'Gaze', 'data': {'gaze': g}, 'source': 'doodle-studio', 'tags': ['gaze']})
for s, name in enumerate(SPEECH):
    if s == 0:
        continue
    face_rows.append({'id': 'mouth-%d' % s, 'name': 'Mouth ' + name, 'category': 'expression', 'kind': 'face',
                      'sub': 'Mouth shapes', 'data': {'speech_mouth': s}, 'source': 'doodle-studio', 'tags': ['mouth']})
print('faces', len(face_rows))

# ---------------------------------------------------------------- mouth sets
js = open(os.path.join(src, 'mouth-sets-presets.js'), encoding='utf-8').read()
presets = json.loads(js[js.index('['):js.rindex(']') + 1])


def to_ds(p):
    return [round((p[0] - 252.5) * 0.01, 5), round((829 - p[1]) * 0.01, 5)]


def inside(pt, poly):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


sets, set_rows = [], []
for ps in presets:
    items = []
    for key, mouth in ps['mouths'].items():
        if key not in SPEECH:
            continue
        sp = SPEECH.index(key)
        ink, holes, strokes = [], [], []
        for sh in mouth['shapes']:
            pts = [to_ds(p) for p in sh['pts']]
            if sh.get('fill') == 'ink':
                ink.append({'outer': pts, 'holes': []})
            elif sh.get('fill') == 'face':
                holes.append(pts)
            if sh.get('stroke'):
                strokes.append({'pts': pts, 'closed': bool(sh.get('closed'))})
        for h in holes:  # face-colour shapes are cut out of the ink fill they sit on
            c = [sum(p[0] for p in h) / len(h), sum(p[1] for p in h) / len(h)]
            for f in ink:
                if inside(c, f['outer']):
                    f['holes'].append(h)
                    break
        for f in ink:
            items.append({'kind': 'fill', 'role': 'speech', 'face': -1, 'gaze': -1, 'speech': sp, 'width': 0,
                          'closed': True, 'outer': f['outer'], 'holes': f['holes']})
        for s in strokes:
            items.append({'kind': 'stroke', 'role': 'speech', 'face': -1, 'gaze': -1, 'speech': sp, 'width': 1,
                          'closed': s['closed'], 'pts': s['pts']})
    sets.append({'id': ps['id'], 'name': ps['name'], 'note': ps.get('note', ''), 'items': items})
    set_rows.append({'id': 'mouthset-' + ps['id'].replace('mouths-', ''), 'name': ps['name'].replace('Bunny ', ''),
                     'category': 'mouth_set', 'kind': 'mouth_set', 'sub': 'Expression sets' if '-x-' in ps['id'] else 'Speech sets',
                     'description': ps.get('note', ''), 'data': {'set': ps['id']}, 'source': 'doodle-studio', 'tags': []})
set_rows.insert(0, {'id': 'mouthset-builtin', 'name': 'Doodle Studio (built-in)', 'category': 'mouth_set',
                    'kind': 'mouth_set', 'sub': 'Speech sets', 'data': {'set': None}, 'source': 'doodle-studio', 'tags': []})
# sets made by other tools (e.g. the story-beat 'Through teeth' set), already in library form
import glob  # noqa: E402
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extra', 'mouth-set-*.json'))):
    ms = json.load(open(f))
    if ms['id'] in [x['id'] for x in sets]:
        continue
    sets.append(ms)
    set_rows.append({'id': 'mouthset-' + ms['id'].replace('mouths-', ''), 'name': ms['name'], 'category': 'mouth_set',
                     'kind': 'mouth_set', 'sub': 'Expression sets' if '-x-' in ms['id'] else 'Speech sets',
                     'description': ms.get('note', ''), 'data': {'set': ms['id']}, 'source': 'doodle-studio', 'tags': []})
json.dump({'version': 1, 'stride': 100, 'sets': sets}, open(os.path.join(out, 'mouths', 'mouth_sets.json'), 'w'))
print('mouth sets', len(sets))

# ---------------------------------------------------------------- rooms (rules only; pieces come from build_scenery)
bg = json.load(open(os.path.join(src, 'background-auto.json')))
room_rows = []
for r in bg['rooms']:
    props = [{k: v for k, v in p.items() if k not in ('asset',)} for p in r['props']]
    room_rows.append({'id': 'set-' + r['id'], 'name': r['name'], 'category': 'set', 'kind': 'set',
                      'sub': 'Outdoor' if r['outdoor'] else 'Indoor', 'data': {'room': r['id'], 'horizon': r['horizon'],
                      'outdoor': r['outdoor'], 'props': props}, 'source': 'doodle-studio', 'tags': []})
print('sets', len(room_rows))

# story-beat faces (expressions-v2): stored by face name, since Bunny, Koala and Frog number faces differently
story_rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extra', 'story-beat-rows.json')))['rows']
for name, part in (('motions', rows), ('faces', face_rows), ('mouth_sets', set_rows), ('sets', room_rows),
                   ('faces_story', story_rows)):
    json.dump(part, open(os.path.join(out, 'index_parts', name + '.json'), 'w'), indent=0)
