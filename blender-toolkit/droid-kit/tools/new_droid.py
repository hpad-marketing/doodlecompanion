"""New-droid starter. One command sets up everything a new droid needs:
  <DeepInDoodles>/<Folder>/            current file goes here (one only)
      ref/  work/  work/versions/  work/stills/  STATUS.md
      work/lookdev.blend               shared look-dev stage: lights, floor, turntable camera, shared shader groups linked
  droid-kit/droids/<id>.json           settings from the template, with every required hook name listed
python3 new_droid.py --id hazard --name "Hazard Droid" --folder HazardDroid --root C:/Users/Sushant/Documents/DeepInDoodles [--ref photo.jpg]
Then: build the model into work/, run tools/check_names.py, tools/lock_sheet.py, tools/overlay.py, tools/status.py."""
import sys, os, json, shutil
KR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = sys.argv[1:]; opt = {a[i]: a[i + 1] for i in range(0, len(a) - 1) if a[i].startswith('--')}
did, name, folder, root = opt['--id'], opt['--name'], opt.get('--folder', opt['--name'].replace(' ', '')), opt['--root']
D = os.path.join(root, folder)
for sub in ('ref', 'work', os.path.join('work', 'versions'), os.path.join('work', 'stills')): os.makedirs(os.path.join(D, sub), exist_ok=True)
sp = os.path.join(KR, 'droids', did + '.json')
if not os.path.exists(sp):
    S = json.load(open(os.path.join(KR, 'droids', '_template.json')))
    S.update(id=did, name=name, folder=folder, current_file=f'{folder}_{did.upper()}.blend')
    json.dump(S, open(sp, 'w'), indent=1)
if '--ref' in opt: shutil.copy(opt['--ref'], os.path.join(D, 'ref', 'photo.jpg'))
# look-dev stage (needs bpy)
lib = os.path.join(root, '_shared', 'RB_Materials.blend')
try:
    import bpy, math
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.new('RB_Lookdev'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.03, 0.035, 0.045, 1)
    bpy.ops.mesh.primitive_plane_add(size=30); fl = bpy.context.object; fl.name = 'Lookdev_Floor'
    fm = bpy.data.materials.new('RB_lookdev_floor'); fm.use_nodes = True; fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.18, 0.17, 1)
    fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7; fl.data.materials.append(fm)
    def light(n, t, e, loc, tgt, col, size=None):
        L = bpy.data.lights.new(n, t); L.energy = e; L.color = col
        if size and t == 'SPOT': L.spot_size = math.radians(size)
        o = bpy.data.objects.new(n, L); sc.collection.objects.link(o); o.location = loc
        o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
    light('Key_Spot', 'SPOT', 6000, (-3.5, -4.5, 6), (0, 0, 1), (1, 0.9, 0.78), 34)
    light('Rim_Spot', 'SPOT', 3000, (3.5, 4, 4.5), (0, 0, 1.2), (0.7, 0.82, 1), 40)
    light('Fill_Area', 'AREA', 160, (4, -3, 2.5), (0, 0, 1), (0.9, 0.95, 1))
    cd = bpy.data.cameras.new('Lookdev_Cam'); cam = bpy.data.objects.new('Lookdev_Cam', cd); sc.collection.objects.link(cam); sc.camera = cam
    cd.lens = 40; cam.location = (-3.6, -4.6, 1.7); cam.rotation_euler = (Vector((0, -0.3, 1.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    pivot = bpy.data.objects.new('Turntable', None); sc.collection.objects.link(pivot)
    pivot.keyframe_insert('rotation_euler', index=2, frame=1); pivot.rotation_euler.z = math.tau; pivot.keyframe_insert('rotation_euler', index=2, frame=97)
    for fc in (pivot.animation_data.action.layers[0].strips[0].channelbags[0].fcurves if hasattr(pivot.animation_data.action, 'layers') else pivot.animation_data.action.fcurves):
        for k in fc.keyframe_points: k.interpolation = 'LINEAR'
    sc.frame_end = 96; sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
    txt = bpy.data.texts.new('README'); txt.write(f'Look-dev stage for {name}. Parent the droid root to "Turntable" for a spin. Same lights as every droid and room.\n')
    if os.path.exists(lib):
        with bpy.data.libraries.load(lib, link=True, relative=True) as (src, dst):
            dst.node_groups = [n for n in src.node_groups if n.startswith('RB ')]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, 'work', 'lookdev.blend'))
    stage = 'work/lookdev.blend'
except ImportError:
    stage = 'skipped (run with the bpy wheel or blender --python to make the look-dev stage)'
os.environ['DROID_SETTINGS'] = sp
sys.argv = ['status.py', D]; exec(open(os.path.join(KR, 'tools', 'status.py')).read(), {'__file__': os.path.join(KR, 'tools', 'status.py'), '__name__': '__main__'})
print('NEW DROID', did, '->', D, '| settings', sp, '| stage', stage)
