"""Lay the scanned worn-concrete photo over the procedural floor (keeps cracks, joints, oil and footprints).
python3 scanfloor.py in.blend out.blend   (run after edges.py with RB_TEX, so the images are packed)"""
import bpy, sys
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
m = bpy.data.materials['RB_concrete']; nt = m.node_tree; N = nt.nodes; L = nt.links
b = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
tc = next(n for n in N if n.bl_idname == 'ShaderNodeTexCoord')
mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (0.42, 0.42, 0.42)
L.new(tc.outputs['Object'], mp.inputs[0])
def img(k):
    t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images[k]; t.interpolation = 'Cubic'; L.new(mp.outputs[0], t.inputs[0]); return t
d = img('concrete_floor_worn_001_diff'); r = img('concrete_floor_worn_001_rough')
# base colour: overlay the photo's detail on the procedural colour (keeps its tone and painted joints)
src = b.inputs['Base Color'].links[0].from_socket
ov = N.new('ShaderNodeMix'); ov.data_type = 'RGBA'; ov.blend_type = 'OVERLAY'; ov.inputs[0].default_value = 0.75
L.new(src, ov.inputs[6]); L.new(d.outputs['Color'], ov.inputs[7]); L.new(ov.outputs[2], b.inputs['Base Color'])
# roughness: add the photo's variation
rs = b.inputs['Roughness'].links[0].from_socket if b.inputs['Roughness'].links else None
ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; ad.use_clamp = True
sub = N.new('ShaderNodeMath'); sub.operation = 'MULTIPLY_ADD'; sub.inputs[1].default_value = 0.5; sub.inputs[2].default_value = -0.25
L.new(r.outputs['Color'], sub.inputs[0])
if rs: L.new(rs, ad.inputs[0])
else: ad.inputs[0].default_value = b.inputs['Roughness'].default_value
L.new(sub.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], b.inputs['Roughness'])
print('FLOOR scanned overlay added')
bpy.ops.wm.save_as_mainfile(filepath=out)
