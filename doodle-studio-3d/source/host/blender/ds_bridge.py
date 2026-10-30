"""Doodle Studio -> Blender shot bridge.

  blender -b Bunny3D.blend --python ds_bridge.py -- shot.json OUT_DIR [options]

shot.json (written by Doodle Studio, one entry per frame, same track ids as
Doodle Studio's set_pose / read_project):
  {
    "fps": 30, "width": 1080, "height": 1920,
    "frames": [ {"turn": 0, "view": 0, "headYaw": 12, "armL": 40, ...,
                 "expression": 1, "gaze": 0, "mouth": 3, "blink": 0,
                 "bodyX": 0, "bodyY": 0, "depth": 0, "s": 1,
                 "camFov": 0, "camZoom": 1, "lineBoil": 30}, ... ],
    "settings": {"ink_px": 10.5, "boil_step": 3},
    "ik": {"arm.L": 0, "arm.R": 0, "leg.L": 0, "leg.R": 0}
  }

Options
  --still N        render only frame N (1-based) as OUT_DIR/still.png
  --transparent    Bunny on a transparent background (for compositing in Doodle Studio)
  --no-springs     skip the ear spring bake
  --no-cloth       skip the hoodie cloth
  --no-collide     keep authored arm/ear values even where they cut into the head
  --check          run the 3D rule checks per frame, write OUT_DIR/rules.json (exit 1 on a violation)
  --save FILE      also save the posed/baked .blend (for hand-tweaking in Blender)
  --range A B      render only frames A..B (keys and physics still cover the whole shot)
  --scale P        render at P percent of the shot size (previews)
  --video FILE     write an H.264 MP4 instead of PNG frames
  --audio FILE     mux this sound file into the video (starts at frame 1)

A frame may carry a 'cam' block for a real 3D camera instead of Doodle Studio's
flat camera: {yaw, pitch, dist, lens, roll, tz, props, shake} (degrees, metres,
mm). 'props' shows or hides the 'Park' collection; 'shake' adds handheld noise.
"""
import bpy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
sys.path.insert(0, HERE)
import ds_map, dynamics, rules3d, collision, compat  # noqa: E402
import stage  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
if argv and argv[0].endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=argv[0])
    argv = argv[1:]
shot_path, out_dir = argv[0], argv[1]
opts = argv[2:]
flag = lambda f: f in opts
still = int(opts[opts.index('--still') + 1]) if '--still' in opts else None
save = opts[opts.index('--save') + 1] if '--save' in opts else None
os.makedirs(out_dir, exist_ok=True)

shot = json.load(open(shot_path))
sc = bpy.context.scene
arm = bpy.data.objects['BUNNY_rig']
cam = sc.camera
settings = bpy.data.objects['BUNNY_settings']
meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
S = meta['S']
frames = shot['frames']
n = len(frames)
fps = int(shot.get('fps', 30))
sc.render.fps = fps
sc.frame_start = 1
sc.frame_end = n
sc.render.resolution_x = int(shot.get('width', 1080))
sc.render.resolution_y = int(shot.get('height', 1920))
sc.render.film_transparent = flag('--transparent')
for k, v in (shot.get('settings') or {}).items():
    if k in settings.keys():
        settings[k] = v
for k, v in (shot.get('ik') or {}).items():
    limb, side = k.split('.')
    arm[f'{limb}_ik.{side}'] = float(v)

PIVOT_Z = 4.145 * S
BASE_ORTHO = 17.07 * S
persp = any(float(f.get('camFov', 0)) > 0 for f in frames)
park = [o for o in bpy.data.objects if o.users_collection and any(c.name == 'Park' for c in o.users_collection)]


def camera_3d(c, t):
    """Orbit camera around Bunny: yaw + swings to screen right, pitch + looks down."""
    from mathutils import Vector, Euler
    yaw, pitch = math.radians(c['yaw']), math.radians(c['pitch'])
    T = Vector((c.get('tx', 0.0), c.get('ty', 0.0), c['tz']))
    d = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = T + d * c['dist']
    q = (T - cam.location).to_track_quat('-Z', 'Y')
    roll = math.radians(c.get('roll', 0.0))
    if c.get('shake'):
        # handheld: a few slow, incommensurate wobbles, about half a degree
        roll += math.radians(0.35 * math.sin(7.1 * t + 0.4))
        q = q @ Euler((math.radians(0.45 * math.sin(5.3 * t) + 0.25 * math.sin(11.7 * t)),
                       math.radians(0.45 * math.sin(4.1 * t + 1.3) + 0.2 * math.sin(9.9 * t)), 0)).to_quaternion()
    from mathutils import Quaternion
    q = q @ Quaternion((0, 0, 1), roll)
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = q.to_euler('XYZ')
    cam.data.type = 'PERSP'
    cam.data.lens = c['lens']
    # rack focus: a focus distance above 0 turns depth of field on
    focus = float(c.get('focus', 0.0) or 0.0)
    cam.data.dof.use_dof = focus > 0
    if focus > 0:
        cam.data.dof.focus_distance = focus
        cam.data.dof.aperture_fstop = float(c.get('fstop', 2.8) or 2.8)

# previz grey: a fast blocking pass in plain grey clay, no cloth, no springs, no ink pass
previz = bool(shot.get('previz'))
if previz:
    opts += ['--no-cloth', '--no-springs']
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'SINGLE'
    sc.display.shading.single_color = (0.27, 0.27, 0.26)
    sc.display.shading.show_object_outline = True
    sc.display.shading.object_outline_color = (0.012, 0.012, 0.011)

# the room set, light, outfit and accessories come first: outfits re-bind to the rig
stage_items = stage.setup(shot, lambda m: print(m, flush=True))

if any(float(f.get('squashBody', 0) or 0) for f in frames):
    ds_map.squash_setup(arm)
pose_bones = [b for b in arm.pose.bones if not b.name.startswith(('MCH-', 'DEF-'))]
objs = collision.objects()
ear_sets = collision.ear_vertex_sets(objs['head'])
apply = lambda v: ds_map.apply_pose(arm, meta['controls'], v, S, settings)
fixes = []
rep = None
for i, vals in enumerate(frames):
    f = i + 1
    if flag('--no-collide'):
        apply(vals)
    else:
        vals, rep = collision.solve_frame(apply, vals, objs, ear_sets, hint=rep)
        if rep['arm_fix'] or rep['ear_fix'] is not None:
            fixes.append({'frame': f, **rep})
    if 'cam' in vals:
        camera_3d(vals['cam'], i / fps)
        for o in park:
            o.hide_render = not vals['cam'].get('props', 0)
            o.keyframe_insert('hide_render', frame=f)
    else:
        ds_map.apply_camera(cam, vals, S, PIVOT_Z, base_ortho=BASE_ORTHO)
    if persp and 'cam' not in vals:
        fov = float(vals.get('camFov', 0)) or 8.0
        cam.data.type = 'PERSP'
        cam.data.angle = math.radians(fov)
        # keep the subject plane framed like Doodle Studio's flat view (dolly with the lens)
        dist = (BASE_ORTHO / float(vals.get('camZoom', 1) or 1) / 2) / math.tan(math.radians(fov) / 2)
        view = math.radians(float(vals.get('view', 0)))
        cam.location = (0, -math.cos(view) * dist, PIVOT_Z + math.sin(view) * dist)
    for b in pose_bones:
        b.keyframe_insert(ds_map.rotation_path(b), frame=f, group=b.name)
        b.keyframe_insert('location', frame=f, group=b.name)
        b.keyframe_insert('scale', frame=f, group=b.name)
    fb = arm.pose.bones['face']
    for k in ('expression', 'gaze', 'speech_mouth', 'blink'):
        fb.keyframe_insert(f'["{k}"]', frame=f, group='face')
    if 'leg_reach' in arm:
        arm.keyframe_insert('["leg_reach"]', frame=f)
    settings.keyframe_insert('["boil"]', frame=f)
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.keyframe_insert('ortho_scale' if cam.data.type == 'ORTHO' else 'lens', frame=f)
    if cam.data.dof.use_dof or 'cam' in vals:
        cam.data.dof.keyframe_insert('use_dof', frame=f)
        cam.data.dof.keyframe_insert('focus_distance', frame=f)
        cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

# props in hand, scenery, effects and storytime pieces, keyed at their frames
stage.place(stage_items, lambda m: print(m, flush=True))

# a cut is a cut: hold every key up to the cut so motion blur never smears across it
cut_frames = {int(round(t * fps)) + 1 for t in shot.get('cuts', [])}
for idb in (arm, cam, cam.data):
    for fc in compat.fcurves(idb):
        for kp in fc.keyframe_points:
            if int(kp.co.x) + 1 in cut_frames:
                kp.interpolation = 'CONSTANT'

# stepped face states (no in-betweens between drawings)
for fc in compat.fcurves(arm):
    if fc.data_path.startswith('pose.bones["face"]'):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'

if not flag('--no-springs') and n > 1:
    dynamics.bake_springs(arm, 1, n, fps=fps)

cloth_mods = [(ob, m) for ob in bpy.data.objects for m in ob.modifiers if m.type == 'CLOTH']
for ob, m in cloth_mods:
    m.show_render = m.show_viewport = not flag('--no-cloth')
    m.point_cache.frame_start = 1
    m.point_cache.frame_end = n
if not flag('--no-cloth') and cloth_mods and n > 1:
    for ob, m in cloth_mods:
        with bpy.context.temp_override(scene=sc, active_object=ob, point_cache=m.point_cache):
            bpy.ops.ptcache.bake(bake=True)

json.dump(fixes, open(os.path.join(out_dir, 'collision.json'), 'w'), indent=1)
report = []
if flag('--check'):
    rng = [still] if still else range(1, n + 1)
    for f in rng:
        sc.frame_set(f)
        r = rules3d.check_frame(objs, arm, ear_sets)
        r['frame'] = f
        report.append(r)
    bad = [r for r in report if r['arm_head_clip'] or r['below_floor'] or r['ears_touch']]
    json.dump({'frames': report, 'violations': len(bad)}, open(os.path.join(out_dir, 'rules.json'), 'w'), indent=1)
    print('RULES', 'PASS' if not bad else f'FAIL ({len(bad)} frames)')

if save:
    bpy.ops.wm.save_as_mainfile(filepath=save, copy=True)

if previz:
    sc.render.engine = 'BLENDER_WORKBENCH'   # the stage may have switched engines
rng = opts[opts.index('--range') + 1:opts.index('--range') + 3] if '--range' in opts else None
if '--scale' in opts:
    sc.render.resolution_percentage = int(opts[opts.index('--scale') + 1])
if rng:
    sc.frame_start, sc.frame_end = int(rng[0]), int(rng[1])
if '--frames' in opts:
    for fr in [int(x) for x in opts[opts.index('--frames') + 1].split(',')]:
        sc.frame_set(fr)
        sc.render.filepath = os.path.join(out_dir, f'still_{fr:04d}.png')
        bpy.ops.render.render(write_still=True)
    print('done', out_dir)
    sys.exit(0)
if still:
    sc.frame_set(still)
    sc.render.filepath = os.path.join(out_dir, 'still.png')
    bpy.ops.render.render(write_still=True)
else:
    video = opts[opts.index('--video') + 1] if '--video' in opts else None
    if video:
        r = sc.render
        compat.video_output(r)
        r.ffmpeg.format = 'MPEG4'
        r.ffmpeg.codec = 'H264'
        r.ffmpeg.constant_rate_factor = 'HIGH'
        r.ffmpeg.ffmpeg_preset = 'GOOD'
        r.ffmpeg.gopsize = fps
        audio = opts[opts.index('--audio') + 1] if '--audio' in opts else None
        if audio and os.path.exists(audio):
            sc.sequence_editor_create()
            compat.strips(sc.sequence_editor).new_sound('voice', audio, 1, 1)
            r.ffmpeg.audio_codec = 'AAC'
            r.ffmpeg.audio_bitrate = 192
        elif sc.sequence_editor and any(st.type == 'SOUND' for st in compat.strips(sc.sequence_editor)):
            # story sounds and auto foley placed by the stage
            r.ffmpeg.audio_codec = 'AAC'
            r.ffmpeg.audio_bitrate = 192
        else:
            r.ffmpeg.audio_codec = 'NONE'
        r.filepath = video
    else:
        sc.render.filepath = os.path.join(out_dir, 'frame_')
    bpy.ops.render.render(animation=True)
print('done', out_dir)
if flag('--check') and any(r['arm_head_clip'] or r['below_floor'] or r['ears_touch'] for r in report):
    sys.exit(1)
