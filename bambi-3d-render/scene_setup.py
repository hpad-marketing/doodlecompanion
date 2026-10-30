"""Bambi 3D base scene: Bunny3D_v2 + curved rap studio + track jacket + halftone floor."""
import bpy, sys, os, importlib.util
B='/tmp/claude-0/-home-claude-doodlecompanion/46d4389e-2d5b-5412-9c9e-932683924948/scratchpad/b3d/doodle-studio-3d/source/host/blender/'
LIB='/mnt/user-data/uploads/Documents/Talking Character App/blender-library/'
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
OUT=args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)),'Bambi_base.blend')
if len(args)>2 and not args[1].startswith('--'): B,LIB=args[1],args[2]
bpy.ops.wm.open_mainfile(filepath=os.path.join(B,'Bunny3D_v2.blend'))
sc=bpy.context.scene
with bpy.data.libraries.load(os.path.join(LIB,'sets','sets.blend')) as (s,d): d.collections=['SET_rapstudio']
col=d.collections[0]; sc.collection.children.link(col)
objs=[o for o in col.all_objects if o]
cyc=next(o for o in objs if o.name.endswith(':cyc'))
for o in objs:
    # round 2: keep the rap studio's own mic stand and lights from the 3D library; hide only the shell
    if o is not cyc and not (o.name.endswith(':mic') or o.name.endswith(':lights')): o.hide_render=o.hide_viewport=True
# halftone floor: ochre dots on mustard, big near the lens, fading out up the curve
m=bpy.data.materials.new('BAMBI_cyc_halftone'); m.use_nodes=True; nt=m.node_tree; N=nt.nodes; L=nt.links
for n in list(N): N.remove(n)
out=N.new('ShaderNodeOutputMaterial'); em=N.new('ShaderNodeEmission'); L.new(em.outputs[0],out.inputs[0])
tc=N.new('ShaderNodeTexCoord'); sep=N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'],sep.inputs[0])
v=N.new('ShaderNodeMath'); v.operation='ADD'; L.new(sep.outputs[1],v.inputs[0]); L.new(sep.outputs[2],v.inputs[1])
comb=N.new('ShaderNodeCombineXYZ'); L.new(sep.outputs[0],comb.inputs[0]); L.new(v.outputs[0],comb.inputs[1])
sca=N.new('ShaderNodeVectorMath'); sca.operation='SCALE'; sca.inputs[3].default_value=1/0.12; L.new(comb.outputs[0],sca.inputs[0])
fr=N.new('ShaderNodeVectorMath'); fr.operation='FRACTION'; L.new(sca.outputs[0],fr.inputs[0])
sub=N.new('ShaderNodeVectorMath'); sub.operation='SUBTRACT'; sub.inputs[1].default_value=(0.5,0.5,0); L.new(fr.outputs[0],sub.inputs[0])
ln=N.new('ShaderNodeVectorMath'); ln.operation='LENGTH'; L.new(sub.outputs[0],ln.inputs[0])
rad=N.new('ShaderNodeMapRange'); rad.inputs[1].default_value=-2.0; rad.inputs[2].default_value=2.6; rad.inputs[3].default_value=0.32; rad.inputs[4].default_value=0.0
L.new(v.outputs[0],rad.inputs[0])
# keep a clear disc around Bunny's feet so nothing reads as a cast shadow or touches him
dx=N.new('ShaderNodeVectorMath'); dx.operation='LENGTH'; L.new(tc.outputs['Object'],dx.inputs[0])
clr=N.new('ShaderNodeMapRange'); clr.inputs[1].default_value=0.32; clr.inputs[2].default_value=0.45; clr.inputs[3].default_value=0; clr.inputs[4].default_value=1
L.new(dx.outputs[1],clr.inputs[0])
r2=N.new('ShaderNodeMath'); r2.operation='MULTIPLY'; L.new(rad.outputs[0],r2.inputs[0]); L.new(clr.outputs[0],r2.inputs[1])
lt=N.new('ShaderNodeMath'); lt.operation='LESS_THAN'; L.new(ln.outputs[1],lt.inputs[0]); L.new(r2.outputs[0],lt.inputs[1])
mix=N.new('ShaderNodeMix'); mix.data_type='RGBA'; L.new(lt.outputs[0],mix.inputs[0])
hy=N.new('ShaderNodeMath'); hy.operation='SUBTRACT'; hy.inputs[1].default_value=0.73; L.new(sep.outputs[1],hy.inputs[0])
ha=N.new('ShaderNodeMath'); ha.operation='ABSOLUTE'; L.new(hy.outputs[0],ha.inputs[0])
hl=N.new('ShaderNodeMath'); hl.operation='LESS_THAN'; hl.inputs[1].default_value=0.0  # v002: ink horizon off; it cut tangents through Bunny's hands in most shots; L.new(ha.outputs[0],hl.inputs[0])
hz=N.new('ShaderNodeMath'); hz.operation='LESS_THAN'; hz.inputs[1].default_value=0.03; L.new(sep.outputs[2],hz.inputs[0])
hm=N.new('ShaderNodeMath'); hm.operation='MULTIPLY'; L.new(hl.outputs[0],hm.inputs[0]); L.new(hz.outputs[0],hm.inputs[1])
mix2=N.new('ShaderNodeMix'); mix2.data_type='RGBA'; L.new(hm.outputs[0],mix2.inputs[0]); mix2.inputs[7].default_value=(0.0137,0.0137,0.0123,1)
mix.inputs[6].default_value=(0.745,0.381,0.070,1)   # mustard #E0A64B (linear)
mix.inputs[7].default_value=(0.479,0.207,0.027,1)   # ochre #B87D2E (linear)
L.new(mix.outputs[2],mix2.inputs[6]); L.new(mix2.outputs[2],em.inputs[0])
cyc.data.materials.clear(); cyc.data.materials.append(m)
for mod in cyc.modifiers: pass
# track jacket
sys.path.insert(0,os.path.join(LIB,'outfits'))
spec=importlib.util.spec_from_file_location('apply_outfit',os.path.join(LIB,'outfits','apply_outfit.py')); ao=importlib.util.module_from_spec(spec); spec.loader.exec_module(ao)
if '--outfit' in sys.argv: ao.dress(os.path.join(LIB,'outfits','track'))
sc.render.use_motion_blur=True
try: sc.render.motion_blur_shutter=0.15
except Exception: pass
# round 2 (user, 2026-10-30): dress the studio from the 3D Doodle Library packs, minimal and symmetric,
# every piece inked like Bunny. Bunny stands at the origin facing -Y; flat floor to y=0.73, wall curve behind.
import math
HERE=os.path.dirname(os.path.abspath(__file__))
for lp in (os.path.join(B,'lib'), os.path.join(HERE,'..','blender','lib'), os.path.join(HERE,'lib')):
    if os.path.exists(os.path.join(lp,'look.py')): sys.path.insert(0,lp); break
import look
mats=look.materials()
for o in objs:
    if o.name.endswith(':mic'): o.hide_render=o.hide_viewport=True   # the pack mic stand replaces it
DRESS=[('scenery-speaker_pair',(0,0.62,0),0),        # speakers flank him, gap behind his body
       ('scenery-mic_stand',(0.62,0.12,0),-20),       # front-right, out of arm reach
       ('scenery-spotlight',(-1.2,0.35,0),35),('scenery-spotlight',(1.2,0.35,0),-35),
       ('scenery-neon_sign',(0,2.12,1.75),0),         # high on the back wall, clear of the ears
       ('scenery-fairy_lights',(0,2.16,2.35),0)]
with bpy.data.libraries.load(os.path.join(LIB,'packs','packs.blend')) as (s,d): d.objects=sorted({n for n,_,_ in DRESS})
src={o.name:o for o in d.objects if o}
dress=bpy.data.collections.new('Bambi studio dressing'); sc.collection.children.link(dress)
for n,loc,rz in DRESS:
    if n not in src: print('missing',n); continue
    ob=src[n] if src[n].users_collection==() or not src[n].users_collection else src[n].copy()
    if not ob.users_collection: dress.objects.link(ob)
    else:
        ob=src[n].copy(); dress.objects.link(ob)
    ob.location=loc; ob.rotation_euler=(0,0,math.radians(rz))
    try: look.apply_ink(ob, sc.camera, mats)
    except Exception as e: print('ink skipped',n,e)
print('dressed',[o.name for o in dress.objects])
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('SAVED',OUT, 'cyc mat', [mm.name for mm in cyc.data.materials])
