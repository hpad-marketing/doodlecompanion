"""Point the scanned images at the PC's texture folder instead of packing them (keeps the .blend small)."""
import bpy, sys
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
ROOT = r'C:\Users\Sushant\Documents\DeepInDoodles\Robot\work\textures' + '\\'
n = 0
for im in bpy.data.images:
    k = im.name
    for asset in ('blue_metal_plate', 'concrete_floor_worn_001', 'green_metal_rust', 'metal_plate', 'rubber_tiles', 'rust_coarse_01', 'rusty_metal_04'):
        if k.startswith(asset + '_') and (k[len(asset) + 1:] in ('diff', 'rough', 'nor_gl', 'disp')):
            if im.packed_file: im.unpack(method='REMOVE')
            im.filepath = ROOT + asset + '\\' + k + '_2k.jpg'; n += 1
            break
print('REPATH', n, [im.filepath for im in bpy.data.images if 'rust_coarse_01_diff' in im.name])
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
