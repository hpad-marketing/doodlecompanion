"""Emotive hooks for the sitcom add-on: separate emissive materials RB_LED_<colour> and RB_Antenna_Tip_<L|R>,
each with a 'Glow' emission node (colour + strength) the add-on can drive. python3 emotive.py in out"""
import bpy, sys
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
for c in ('green', 'amber', 'red'):
    m = bpy.data.materials.get('RB_led_' + c)
    if m: m.name = 'RB_LED_' + c
    o = bpy.data.objects.get('led_' + c)
    if o: o.name = 'RB_LED_' + c
for S in 'LR':
    o = bpy.data.objects['antenna_%s_tip' % S]
    base = bpy.data.materials['RB_metal_yellow']
    m = bpy.data.materials.get('RB_Antenna_Tip_' + S) or base.copy(); m.name = 'RB_Antenna_Tip_' + S
    nt = m.node_tree; N = nt.nodes; L = nt.links
    if 'Glow' not in N:
        outn = next(n for n in N if n.bl_idname == 'ShaderNodeOutputMaterial')
        src = outn.inputs['Surface'].links[0].from_socket
        em = N.new('ShaderNodeEmission'); em.name = em.label = 'Glow'
        em.inputs['Color'].default_value = (1.0, 0.75, 0.2, 1); em.inputs['Strength'].default_value = 0.0
        add = N.new('ShaderNodeAddShader'); L.new(src, add.inputs[0]); L.new(em.outputs[0], add.inputs[1]); L.new(add.outputs[0], outn.inputs['Surface'])
    o.data = o.data.copy() if o.data.users > 1 else o.data
    o.data.materials.clear(); o.data.materials.append(m)
print('EMOTIVE', [m.name for m in bpy.data.materials if m.name.startswith(('RB_LED', 'RB_Antenna'))])
bpy.ops.wm.save_as_mainfile(filepath=out)
