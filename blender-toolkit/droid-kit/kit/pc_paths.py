"""Point the scanned images at the shared texture shelf instead of packing them (keeps the .blend small).
Default shelf is relative to a droid file at DeepInDoodles/<Folder>/: //../_shared/textures/. Override with DROID_TEX.
Scans no longer used by anything (the linked library brings its own) are dropped."""
import bpy, sys, os
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
ROOT = os.environ.get('DROID_TEX', '//../_shared/textures/')
n = 0
for im in bpy.data.images:
    k = im.name
    for asset in ('blue_metal_plate', 'concrete_floor_worn_001', 'green_metal_rust', 'metal_plate', 'rubber_tiles', 'rust_coarse_01', 'rusty_metal_04'):
        if k.startswith(asset + '_') and (k[len(asset) + 1:] in ('diff', 'rough', 'nor_gl', 'disp')):
            if im.packed_file: im.unpack(method='REMOVE')
            im.use_fake_user = False
            im.filepath = ROOT + asset + '/' + k + '_2k.jpg'; n += 1
            break
print('REPATH', n, [im.filepath for im in bpy.data.images if 'rust_coarse_01_diff' in im.name])
for L in bpy.data.libraries:
    if os.environ.get('DROID_LIB'): L.filepath = os.environ['DROID_LIB']
print('LIBS', [L.filepath for L in bpy.data.libraries])
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
