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
  --live URL TOKEN [--frame N] [--save-live FILE]
                   open the shot for hand work in a Blender window, live-linked to Doodle
                   Studio 3D (mirror.py): no render, no physics bakes and no rule nudges, so
                   what Blender shows is exactly what the app has; renders still do all of it

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
import powers  # noqa: E402
import drawings  # noqa: E402
import cast as costars  # noqa: E402
import rules_scene  # noqa: E402
import constraints  # noqa: E402
import materials  # noqa: E402
import lights  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
if argv and argv[0].endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=argv[0])
    argv = argv[1:]
shot_path, out_dir = argv[0], argv[1]
opts = argv[2:]
flag = lambda f: f in opts
LIVE = flag('--live')
SOURCE_BLEND = bpy.data.filepath
if LIVE:
    opts += ['--no-collide', '--no-springs', '--no-cloth']
still = int(opts[opts.index('--still') + 1]) if '--still' in opts else None
save = opts[opts.index('--save') + 1] if '--save' in opts else None
os.makedirs(out_dir, exist_ok=True)

shot = json.load(open(shot_path))
if LIVE:
    shot['floorCollision'] = False   # the live view keeps every value as the app has it
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
INK_BASE = float(settings['ink_px']) if 'ink_px' in settings.keys() else 12.73
INK_FOLLOW = bool((shot.get('settings') or {}).get('ink_follow', 1))


def ink_for_camera():
    """Ink like a drawing, as in Doodle Studio: it grows when the camera moves in on Bunny and
    thins when it pulls back (zoom 1 = the 2D default framing, where ink is INK_BASE)."""
    from mathutils import Vector
    fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    P = arm.matrix_world @ arm.pose.bones['root'].head + Vector((0, 0, PIVOT_Z))
    depth = max(0.05, (P - cam.matrix_world.translation).dot(fwd))
    zoom = BASE_ORTHO / (depth * 36.0 / max(1.0, cam.data.lens))
    return INK_BASE * max(0.4, min(3.5, zoom))
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

# the animation rules as always-on defaults (lib/constraints.py); shot['rules'] turns any off
RULES = constraints.configure(shot, cam)
log = lambda m: print(m, flush=True)

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
# co-stars come in after the lead's collision objects are taken, so those stay the lead's own
cast = costars.setup(shot, cam, HERE, lambda m: print(m, flush=True))
fixes = []
lifts = []
FLOOR = shot.get('floorCollision', True) is not False
rep = None
if FLOOR:
    # the outline shell never sinks through the floor, whatever the camera (high shots push it down)
    collision.bind_shell_floor()
unhold_bias = collision.hold_depth_bias() if FLOOR else (lambda: None)
arm_fixes, solved, ahint = {}, [], None
for i, vals in enumerate(frames):
    f = i + 1
    vals = constraints.prepare(vals, arm)
    if flag('--no-collide'):
        apply(vals)
    else:
        vals, rep = collision.solve_frame(apply, vals, objs, ear_sets, hint=rep)
        if rep['arm_fix'] or rep['ear_fix'] is not None:
            fixes.append({'frame': f, **rep})
    if 'cam' in vals:
        camera_3d(vals['cam'], i / fps)
        if INK_FOLLOW and 'ink_px' in settings.keys():
            bpy.context.view_layer.update()
            settings['ink_px'] = ink_for_camera()
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
    # arm in front of the face (as this frame's camera sees it), before the floor is measured
    if not flag('--no-collide'):
        bpy.context.view_layer.update()
        vals, afix = constraints.arm_in_front(apply, vals, objs, cam, hint=ahint)
        ahint = afix or None
        if afix:
            arm_fixes[f] = afix
    solved.append(vals)
    if FLOOR:
        # floor collision (no stroke under the floor), measured after the camera so the ink
        # width is this frame's
        up = collision.floor_lift(arm, objs)
        arm.keyframe_insert('["ds_floor_up"]', frame=f)
        collision.set_floor_z(arm, arm.get('ds_floor_target', collision.FLOOR_OFF), frame=f)
        if up:
            lifts.append({'frame': f, 'cm': round(up * 100, 2)})
    for b in pose_bones:
        b.keyframe_insert(ds_map.rotation_path(b), frame=f, group=b.name)
        b.keyframe_insert('location', frame=f, group=b.name)
        b.keyframe_insert('scale', frame=f, group=b.name)
    fb = arm.pose.bones['face']
    for k in ('expression', 'gaze', 'speech_mouth', 'blink'):
        fb.keyframe_insert(f'["{k}"]', frame=f, group='face')
    if 'leg_reach' in arm:
        arm.keyframe_insert('["leg_reach"]', frame=f)
    for c in cast:
        costars.pose_frame(c, i, f, settings, collide=not flag('--no-collide'), floor=FLOOR)
    if cast:
        costars.keep_apart(objs, arm, cast, f, lambda m: print(m, flush=True))
    settings.keyframe_insert('["boil"]', frame=f)
    if 'ink_px' in settings.keys():
        settings.keyframe_insert('["ink_px"]', frame=f)
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.keyframe_insert('ortho_scale' if cam.data.type == 'ORTHO' else 'lens', frame=f)
    if cam.data.dof.use_dof or 'cam' in vals:
        cam.data.dof.keyframe_insert('use_dof', frame=f)
        cam.data.dof.keyframe_insert('focus_distance', frame=f)
        cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

unhold_bias()
if arm_fixes:
    print(f"rules: arm brought clear of the head on {len(arm_fixes)} frames", flush=True)
    try:
        constraints.ease_fixes(arm, apply, solved, arm_fixes, objs, log)
    except Exception as e:
        print('rules: arm easing skipped:', e, flush=True)
ups = [x for x in lifts if x['cm'] > 0.05]
if ups:
    print(f"floor: lifted out of the floor on {len(ups)} frames (up to {max(x['cm'] for x in ups)} cm)", flush=True)
if cast:
    costars.finish(cast, n)
    for c in cast:
        if c['pushes']:
            print(f"cast: {c['name']} kept clear on {len(c['pushes'])} frames (up to {max(p['cm'] for p in c['pushes'])} cm)", flush=True)

# gaps between a character's timeline blocks: everything on that rig is hidden there
def key_hidden(rig, spans):
    kids = set(rig.children_recursive)
    obs = [o for o in bpy.data.objects if o.type != 'ARMATURE' and (o in kids or any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers))]
    marks = {1: False}
    for a, b in spans:
        marks[b + 1] = False
    for a, b in spans:
        marks[a + 1] = True
    for o in obs:
        for f, off in sorted(marks.items()):
            o.hide_render = off
            o.keyframe_insert('hide_render', frame=f)
        o.hide_render = False
if shot.get('hide'):
    key_hidden(arm, shot['hide'])
for c in cast:
    if c.get('hide'):
        key_hidden(c['rig'], c['hide'])

# props in hand, scenery, effects and storytime pieces, keyed at their frames
stage.place(stage_items, lambda m: print(m, flush=True))

# props and set pieces standing on the floor rest their stroke just above it, like the characters
if stage_items is not None and not LIVE:
    try:
        sc.frame_set(1)
        _scenery, _ = rules_scene.classify(arm, cast, objs.values())
        constraints.props_on_floor([o for o in _scenery if o.dimensions.z >= 0.08], arm.matrix_world.translation.z, log)
    except Exception as e:
        print('rules: props on floor skipped:', e, flush=True)

# the set keeps a clear zone round the characters and drops pieces the camera cuts to slivers
if stage_items is not None and not LIVE and shot.get('stage', {}).get('set') and not (shot.get('stage') or {}).get('keepLayout'):
    try:
        rules_scene.tidy_set(arm, cast, objs.values(), cam, n, lambda m: print(m, flush=True), str(shot['stage']['set']))
    except Exception as e:
        print('set tidy skipped:', e, flush=True)

# nothing stands between the camera and a face (set pieces and placed props slide aside)
if stage_items is not None and not LIVE:
    try:
        sc.frame_set(1)
        _scenery, _ = rules_scene.classify(arm, cast, objs.values())
        room = str((shot.get('stage') or {}).get('set') or '') or None
        constraints.face_clear(_scenery, [objs] + [c['objs'] for c in cast], cam, n, room, log)
    except Exception as e:
        print('rules: face clear skipped:', e, flush=True)

# held props: each frame turns the prop clear of his head and body inside its grip, since the
# shot's own pose can move the hand after the grip was found (B14)
held_props = [o for o in bpy.data.objects if o.get('dsl_held_side') and o.get('dsl_grip_kind') not in ('wear', 'two')]
if held_props and not flag('--no-collide'):
    try:
        from doodle_library import collide as held_collide
        for i in range(n):
            sc.frame_set(i + 1)
            for ob in held_props:
                left = held_collide.resolve(ob, key=True, frame=i + 1)
                if left > 2:
                    print(f'held {ob.name} frame {i + 1}: {left:.0f} mm still inside him', flush=True)
        sc.frame_set(1)
    except Exception as e:
        print('held props: could not keep them clear:', e, flush=True)

# Blender powers: doodles in 3D, auto-ink, scatter, crowds, toon liquids, fisheye, 360 video
powers.apply(shot, cam, lambda m: print(m, flush=True))
# scene drawings: imported SVGs standing in the 3D world, drawn on and boiling (drawings.py)
drawings.apply(shot, cam, lambda m: print(m, flush=True))
# Materials tab: a look (clay, cel, felt... or an add-on's) on the scene, characters, set or props
try:
    materials.apply(shot, cam, lambda m: print(m, flush=True), out_dir)
except Exception as e:   # a material never stops a render: the shot stays Ink & Mustard
    print('materials: skipped:', e, flush=True)
# shadows, 3-point light and each object's own outline, on whatever the looks left
try:
    lights.apply(shot, cam, arm, lambda m: print(m, flush=True), out_dir)
except Exception as e:   # nor does a light
    print('lights: skipped:', e, flush=True)

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
    for c in cast:
        dynamics.bake_springs(c['rig'], 1, n, fps=fps)

if FLOOR:
    # one last look at every frame as it will render: no stroke under the floor
    fix = collision.floor_settle(arm, objs, range(1, n + 1))
    for c in cast:
        fix = max(fix, collision.floor_settle(c['rig'], c['objs'], range(1, n + 1)))
    if fix > 0.002:
        print(f'floor: settled by up to {fix * 100:.1f} cm after the bake', flush=True)
    sc.frame_set(1)

cloth_mods = [(ob, m) for ob in bpy.data.objects for m in ob.modifiers if m.type == 'CLOTH']
for ob, m in cloth_mods:
    m.show_render = m.show_viewport = not flag('--no-cloth')
    m.point_cache.frame_start = 1
    m.point_cache.frame_end = n
if not flag('--no-cloth') and cloth_mods and n > 1:
    for ob, m in cloth_mods:
        with bpy.context.temp_override(scene=sc, active_object=ob, point_cache=m.point_cache):
            bpy.ops.ptcache.bake(bake=True)

json.dump({'lead': lifts, 'costars': [{'character': c['name'], 'lifts': c.get('lifts', [])} for c in cast]},
          open(os.path.join(out_dir, 'floor.json'), 'w'), indent=1)
json.dump(fixes if not cast else {'lead': fixes, 'costars': [{'character': c['name'], 'pushes': c['pushes']} for c in cast]},
          open(os.path.join(out_dir, 'collision.json'), 'w'), indent=1)
report = []
if flag('--check'):
    rng = [still] if still else range(1, n + 1)
    sc.frame_set(rng[0])
    scenery, held_props = rules_scene.classify(arm, cast, objs.values())
    shot_report = {'scenery': [o.name for o in scenery], 'held': [o.name for o in held_props],
                   'see_through': rules_scene.see_through(scenery), 'horizon': []}
    for f in rng:
        sc.frame_set(f)
        r = rules3d.check_frame(objs, arm, ear_sets)
        # scenery, held props and framing (contact every 3rd frame and the last: the slowest check)
        if f == rng[0] or f == rng[-1] or (f - rng[0]) % 3 == 0:
            r.update(rules_scene.contact(scenery, held_props, objs.values(), cast))
        r.update(rules_scene.framing(scenery, sc.camera))
        r.update(rules_scene.costar_framing(cast, sc.camera, objs.values()))
        hz = rules_scene.horizon(sc.camera)
        if hz is not None:
            shot_report['horizon'].append(hz)
        # co-stars obey the same rules; their findings are named after them
        for k, c in enumerate(cast):
            rc = rules3d.check_frame(c['objs'], c['rig'], c['ears'])
            r['arm_head_clip'] = r['arm_head_clip'] + [f"{c['name']}{k + 1}:{x}" for x in rc['arm_head_clip']]
            r['below_floor'] = r['below_floor'] or rc['below_floor']
            r['stroke_in_floor'] = r['stroke_in_floor'] or rc['stroke_in_floor']
            r['floating'] = r.get('floating') or rc.get('floating')
            r.setdefault('costar_floor_gap', []).append(rc.get('floor_gap'))
            r.setdefault('costar_floor_low', []).append(rc['floor_low'])
            r['ears_touch'] = r['ears_touch'] or rc['ears_touch']
            if rc['below_floor']:
                r.setdefault('costar_below_floor', []).append(c['name'])
        if len(cast):
            r['bodies_touch'] = costars.touching(objs, cast)
        r['frame'] = f
        report.append(r)
    bad = [r for r in report if rules_scene.frame_bad(r)]
    hz = shot_report.pop('horizon')
    shot_report['horizon_y'] = round(sum(hz) / len(hz), 4) if hz else None
    shot_report['horizon_range'] = [min(hz), max(hz)] if hz else None
    viol = len(bad) + (1 if shot_report['see_through'] else 0)
    json.dump({'frames': report, 'shot': shot_report, 'violations': viol}, open(os.path.join(out_dir, 'rules.json'), 'w'), indent=1)
    print('RULES', 'PASS' if not viol else f'FAIL ({len(bad)} frames' + (', see-through pieces' if shot_report['see_through'] else '') + ')')

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
if LIVE:
    import mirror
    live_blend = opts[opts.index('--save-live') + 1] if '--save-live' in opts else None
    if live_blend:
        # Blender's own Save goes to this copy in the scene's work folder, never the app's file
        try:
            bpy.ops.wm.save_as_mainfile(filepath=live_blend)
        except Exception as e:
            print('live: could not save the working copy:', e, flush=True)
    i = opts.index('--live')
    mirror.start({'url': opts[i + 1], 'token': opts[i + 2], 'shot': shot, 'shot_path': shot_path, 'out_dir': out_dir,
                  'argv_rest': [o for o in argv[2:]], 'bridge_path': os.path.abspath(__file__), 'source_blend': SOURCE_BLEND,
                  'frame': int(opts[opts.index('--frame') + 1]) if '--frame' in opts else None,
                  'arm': arm, 'cam': cam, 'settings': settings, 'meta': meta, 'S': S, 'pose_bones': pose_bones,
                  'apply': lambda v: apply(constraints.prepare(v, arm)), 'camera_3d': camera_3d,
                  'ink_follow': INK_FOLLOW, 'ink_base': INK_BASE, 'pivot_z': PIVOT_Z, 'base_ortho': BASE_ORTHO})
elif still:
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
if flag('--check') and (any(rules_scene.frame_bad(r) for r in report) or shot_report['see_through']):
    sys.exit(1)
