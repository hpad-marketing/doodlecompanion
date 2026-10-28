# python3 make_module.py picks.json out.js : embeds the approved props (eye-level views + a thumbnail + hold) into the Doodle Studio module
import sys, json
picks, out = json.load(open(sys.argv[1])), sys.argv[2]
PITCHES = [0]  # Doodle Studio shows Bunny at eye level; the full 168-view set stays in the library JSON
props = []
for i in picks['approved']:
    r = json.load(open(f'lib/props/{i}.json'))
    views = {k: v for k, v in r['views']['svg'].items() if int(k.split('_')[1]) in PITCHES or k == '30_30'}  # 30_30 = menu thumbnail
    h = r['hold']
    props.append(dict(id=i, label=r['label'], category=r['category'], grip=r['grip'], size=r['size'], views=views,
                      hold=dict(hand=h['hand'], attach=h['attach'], pose=h['pose'], centroid=h['centroid'], offset=h['offset'], placement=h['placement'])))
data = json.dumps(dict(version=1, pitches=PITCHES, props=props), separators=(',', ':'))
open(out, 'w').write(open('module_tpl.js').read().replace('__PROP360_DATA__', data))
print(len(props), 'props', round(len(data) / 1e6, 2), 'MB')
