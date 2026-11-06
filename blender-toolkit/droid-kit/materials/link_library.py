"""Point a droid or room .blend at the shared material library instead of its own copies.
- The shader GROUPS (RB Weathered Metal, RB Black Polymer) are LINKED: fix a shader once, every droid and room gets it.
- Each droid keeps its own thin materials (paint colour, wear amounts, look drivers), so palettes stay per droid.
- Emotive materials (RB_LED_*, RB_Glow) are linked whole unless the droid already customised one.
python3 link_library.py <library.blend> in.blend out.blend   (library path is stored relative to the droid file)"""
import bpy, sys, os
lib, blend, out = [os.path.abspath(p) for p in sys.argv[-3:]]
bpy.ops.wm.open_mainfile(filepath=blend)
with bpy.data.libraries.load(lib, link=True, relative=True) as (src, dst):
    dst.node_groups = [n for n in src.node_groups if n in ('RB Weathered Metal', 'RB Black Polymer')]
linked = {g.name: g for g in dst.node_groups}
n = 0
for name, g in linked.items():
    local = next((x for x in bpy.data.node_groups if x.name == name and x.library is None), None)
    if local:
        local.user_remap(g); bpy.data.node_groups.remove(local); n += 1
print('LINKED groups', list(linked), 'replaced', n)
bpy.ops.wm.save_as_mainfile(filepath=out)
