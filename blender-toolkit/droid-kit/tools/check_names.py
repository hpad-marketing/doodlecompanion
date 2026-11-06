"""Names and axes check: does a droid .blend carry every name the sitcom add-on and the kit rely on?
DROID=<id> python3 check_names.py in.blend [report.json]   exit code 0 = pass"""
import bpy, sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
blend = sys.argv[1]; rep = sys.argv[2] if len(sys.argv) > 2 else ''
bpy.ops.wm.open_mainfile(filepath=blend)
H = kit.get('hooks', {}); bad = []; ok = []
rig = bpy.data.objects.get(kit.rig_name())
if not rig or rig.type != 'ARMATURE': bad.append(f"rig object '{kit.rig_name()}' missing")
for m in H.get('leds', []) + H.get('glow_materials', []):
    (ok if bpy.data.materials.get(m) else bad).append('material ' + m)
for m in H.get('glow_materials', []):
    mm = bpy.data.materials.get(m)
    if mm and H.get('glow_node', 'Glow') not in mm.node_tree.nodes: bad.append(f"{m}: no '{H.get('glow_node')}' node")
if H.get('eye'): (ok if bpy.data.objects.get(H['eye']) else bad).append('object ' + H['eye'])
for b in H.get('antenna_chains', []):
    (ok if rig and b in rig.pose.bones else bad).append('bone ' + b)
for k, spec in H.get('controls', {}).items():
    if not spec: bad.append(f'control {k}: not set'); continue
    bone = spec.split(':')[0]
    for S in (('L', 'R') if '{S}' in bone else ('',)):
        bn = bone.replace('{S}', S)
        (ok if rig and bn in rig.pose.bones else bad).append(f'control {k} -> bone {bn}')
# axes: rest pose, droid faces -Y: the toes/front of the feet must sit at lower Y than the heels
if rig:
    fl = [b for b in rig.data.bones if b.name.startswith('DEF-foot')]
    for b in fl:
        if (b.tail_local - b.head_local).y > 0: bad.append(f'{b.name} points +Y: droid does not face -Y')
    for S, sign in (('L', 1), ('R', -1)):
        b = rig.data.bones.get(f'DEF-upper_arm.{S}')
        if b and b.head_local.x * sign < 0: bad.append(f'{b.name} is on the wrong side (L must be +X)')
res = {'droid': kit.get('name'), 'pass': not bad, 'missing_or_wrong': bad, 'found': len(ok)}
print('NAMES', json.dumps(res))
if rep: json.dump(res, open(rep, 'w'), indent=1)
sys.exit(0 if not bad else 1)
