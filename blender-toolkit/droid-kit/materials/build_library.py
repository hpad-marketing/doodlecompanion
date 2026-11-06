"""Build the ONE shared material library: DeepInDoodles/_shared/RB_Materials.blend
Holds the node groups every droid and room uses (RB Weathered Metal, RB Black Polymer), the standard materials
(bare steel, pins, polymer, lens, paint per role) and the emotive materials (RB_LED_*, RB_Glow). All are asset-marked.
Scanned maps are referenced RELATIVE to the library: //textures/<asset>/<file>_2k.jpg  (the shared texture shelf).
python3 build_library.py <shelf_dir_or_''> out.blend"""
import bpy, os, sys, glob
KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit')
shelf, out = sys.argv[-2:]
bpy.ops.wm.read_factory_settings(use_empty=True)
src = open(os.path.join(KIT, 'weather.py')).read()
defs = src[src.index('def srgb'):src.index('import os as _os')]
SCAN = {}
ASSETS = ('blue_metal_plate', 'concrete_floor_worn_001', 'green_metal_rust', 'metal_plate', 'rubber_tiles', 'rust_coarse_01', 'rusty_metal_04')
for a in ASSETS:
    for m in ('diff', 'rough', 'nor_gl', 'disp'):
        k = f'{a}_{m}'; rel = f'//textures/{a}/{k}_2k.jpg'
        im = bpy.data.images.new(k, 8, 8); im.source = 'FILE'; im.filepath = rel
        if m != 'diff': im.colorspace_settings.name = 'Non-Color'
        im.use_fake_user = True; SCAN[k] = im
ns = {'bpy': bpy, 're': __import__('re'), 'SCAN': SCAN}; exec(defs, ns)
MG, PG = ns['metal_group'](), ns['polymer_group'](); srgb = ns['srgb']; material = ns['material']
for g in (MG, PG): g.use_fake_user = True; g.asset_mark(); g.asset_data.description = 'Droid Kit shared shader'
mats = []
PAINT = {'grey': '#434E58', 'tan': '#A38F68', 'teal': '#5F9692', 'navy': '#2B3A5C', 'yellow': '#C99A2E', 'sage': '#85A68C', 'olive': '#66713D'}
for k, hx in PAINT.items(): mats.append(material(f'RB_metal_{k}', MG, {'Paint Colour': srgb(hx)}, srgb(hx)))
mats.append(material('RB_metal_bare', MG, {'Paint Colour': srgb('#3A3D40'), 'Paint': 0.0, 'Rust': 0.7}, srgb('#55585B')))
mats.append(material('RB_metal_pin', MG, {'Paint': 0.0, 'Rust': 0.15, 'Grime': 0.35, 'Scale': 3.0}, srgb('#7A7D80')))
mats.append(material('RB_polymer', PG, {}, srgb('#151617')))
mats.append(material('RB_lens', PG, {'Colour': srgb('#0B0C0D'), 'Scuffs': 0.1}, srgb('#0B0C0D')))
def emissive(name, col, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = col
    b.inputs['Emission Color'].default_value = col; b.inputs['Emission Strength'].default_value = strength
    b.inputs['Roughness'].default_value = 0.15; b.inputs['Transmission Weight'].default_value = 0.3
    m.diffuse_color = col; return m
for nm, c in (('green', (0.1, 1, 0.2, 1)), ('amber', (1, 0.45, 0.05, 1)), ('red', (1, 0.06, 0.03, 1)), ('blue', (0.1, 0.4, 1, 1)), ('white', (1, 0.95, 0.85, 1))):
    mats.append(emissive('RB_LED_' + nm, c, 3.0))
mats.append(emissive('RB_Glow', (1.0, 0.75, 0.2, 1), 0.0))
for m in mats: m.use_fake_user = True; m.asset_mark(); m.asset_data.description = 'Droid Kit shared material'
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=False)
print('LIBRARY', len(mats), 'materials,', 2, 'groups,', len(SCAN), 'scan images ->', out)
