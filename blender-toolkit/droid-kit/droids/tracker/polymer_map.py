"""After kit weather.py: rubber, core and screen-adjacent dark parts -> the shared black polymer; track links -> bare worn steel."""
import bpy, sys
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
P = bpy.data.materials['RB_polymer']; BARE = bpy.data.materials['RB_metal_bare']
n = 0
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.material_slots: continue
    m = o.material_slots[0].material
    if m and m.name in ('RB_rubber', 'RB_core'): o.material_slots[0].material = P; n += 1
for me in {o.data for o in bpy.data.objects if o.name.startswith('track_link_')}:
    me.materials[0] = BARE; n += 1
for m in [m for m in bpy.data.materials if m.users == 0]: bpy.data.materials.remove(m)
print('POLYMAP', n)
bpy.ops.wm.save_as_mainfile(filepath=out)
