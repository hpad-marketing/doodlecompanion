import bpy, sys, json
sys.path.insert(0, 'scripts')
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2]); import stage
def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1,)
ROLES = ['grey', 'tan', 'teal', 'navy', 'yellow', 'sage', 'olive']
P = json.load(open(sys.argv[-1]))
sc = bpy.context.scene; sc.cycles.device = 'CPU'; sc.render.resolution_x, sc.render.resolution_y = 540, 675
sc.frame_set(40)
for key, pal in P.items():
    for r in ROLES:
        g = bpy.data.materials['RB_metal_' + r].node_tree.nodes['Look']
        g.inputs['Paint Colour'].default_value = srgb(pal[r])
    stage.render('out/pal/%s.png' % key, res=None, samples=28)
