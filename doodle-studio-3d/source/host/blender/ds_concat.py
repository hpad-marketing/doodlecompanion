"""Join rendered shots into one scene video, in order, in Blender's video editor.

blender -b --factory-startup --python ds_concat.py -- OUT.mp4 FPS WIDTH HEIGHT [--audio FILE] -- SHOT1.mp4 SHOT2.mp4 ...

Each shot keeps its own sound (per-shot voice clips). --audio lays one scene-wide
track (a song) under the whole scene from the first frame."""
import bpy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import compat  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:]
split = argv.index('--')
head, shots = argv[:split], argv[split + 1:]
out, fps, width, height = head[0], int(head[1]), int(head[2]), int(head[3])
audio = head[head.index('--audio') + 1] if '--audio' in head else None

sc = bpy.context.scene
sc.render.fps = fps
sc.render.resolution_x, sc.render.resolution_y = width, height
sc.render.resolution_percentage = 100
# pass the shots' pixels through untouched (factory settings would add a film look)
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0
sc.view_settings.gamma = 1
se = sc.sequence_editor_create()
strips = compat.strips(se)

start = 1
for i, f in enumerate(shots):
    mv = strips.new_movie(f'shot{i}', f, 2, start, fit_method='FIT')
    # a shot's own sound, if it has one, sits right under its picture
    try:
        snd = strips.new_sound(f'shot{i}_sound', f, 1, start)
        if snd.frame_final_duration <= 0:
            strips.remove(snd)
    except (RuntimeError, TypeError):
        pass
    start += mv.frame_final_duration
    print(f'shot {i + 1}/{len(shots)} {os.path.basename(f)} {mv.frame_final_duration} frames', flush=True)

if audio and os.path.exists(audio):
    music = strips.new_sound('scene_audio', audio, 3, 1)
    if music.frame_final_end > start:
        music.frame_final_end = start

sc.frame_start, sc.frame_end = 1, start - 1
r = sc.render
compat.video_output(r)
r.ffmpeg.format = 'MPEG4'
r.ffmpeg.codec = 'H264'
r.ffmpeg.constant_rate_factor = 'HIGH'
r.ffmpeg.ffmpeg_preset = 'GOOD'
r.ffmpeg.gopsize = fps
r.ffmpeg.audio_codec = 'AAC'
r.ffmpeg.audio_bitrate = 192
r.use_sequencer = True
r.filepath = out
bpy.ops.render.render(animation=True)
print('done', out, flush=True)
