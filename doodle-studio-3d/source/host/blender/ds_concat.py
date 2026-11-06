"""Join rendered shots into one scene video, in order, in Blender's video editor.

blender -b --factory-startup --python ds_concat.py -- OUT.mp4 FPS WIDTH HEIGHT [--audio FILE] -- SHOT1.mp4 SHOT2.mp4 ...

Each shot keeps its own sound (per-shot voice clips). --audio lays one scene-wide
track (a song) under the whole scene from the first frame.

--post POST.json (storytime, made by the editor) lays more on top and underneath:
  looks    [{shot, saturation, overlays: [{path, blend, alpha}]}]   flashback / VHS
  drawings [{path, start, length}]   the screen drawings layer (full-frame PNGs), under the overlays
  overlays [{path, start, length}]   full-frame PNGs: photos, outlines, captions, bubbles
  movies   [{path, start, length, rect: {cx, cy, w}}]   picture-in-picture clips
  music    {path, keys: [[frame, volume]]}   a music bed that ducks under the voice
  bleeps   [[from, to]]   the voice drops out and a tone plays
  voice    path   the scene audio with character voices applied (replaces --audio)
  bleep    path   the tone (written by the host)
  paper    {path, alpha}   paper grain over the whole scene
  transitions [{at, kind, frames, color}]   dip to ink or a mustard flash across a cut
Frames are 0-based scene frames."""
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
post = {}
if '--post' in head:
    import json
    with open(head[head.index('--post') + 1], encoding='utf-8') as fh:
        post = json.load(fh)
if post.get('voice') and os.path.exists(post['voice']):
    audio = post['voice']

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
movies = []
for i, f in enumerate(shots):
    mv = strips.new_movie(f'shot{i}', f, 2, start, fit_method='FIT')
    movies.append(mv)
    # a shot's own sound, if it has one, sits right under its picture
    try:
        snd = strips.new_sound(f'shot{i}_sound', f, 1, start)
        if snd.frame_final_duration <= 0:
            strips.remove(snd)
    except (RuntimeError, TypeError):
        pass
    start += mv.frame_final_duration
    print(f'shot {i + 1}/{len(shots)} {os.path.basename(f)} {mv.frame_final_duration} frames', flush=True)

voice = None
if audio and os.path.exists(audio):
    voice = music = strips.new_sound('scene_audio', audio, 3, 1)
    if music.frame_final_end > start:
        music.frame_final_end = start

# ---------------------------------------------------------------- storytime post (--post)
taken = {}


def lane(base, a, b):
    """Lowest free channel from `base` for frames a..b (strips may not overlap in a channel)."""
    ch = base
    while any(not (b <= x or a >= y) for x, y in taken.get(ch, [])):
        ch += 1
    taken.setdefault(ch, []).append((a, b))
    return ch


def clip(st, length):
    if length and st.frame_final_duration > length:
        st.frame_final_duration = int(length)


def image(path, a, length, base, blend='ALPHA_OVER', alpha=1.0):
    if not os.path.exists(path):
        print('post: missing', path, flush=True)
        return None
    ch = lane(base, a, a + length)
    st = strips.new_image(os.path.basename(path), path, ch, a, fit_method='FIT')
    st.frame_final_duration = int(length)
    st.blend_type = blend
    st.blend_alpha = alpha
    return st


for lk in post.get('looks', []):
    i = int(lk['shot'])
    if i >= len(movies):
        continue
    mv = movies[i]
    mv.color_saturation = float(lk.get('saturation', 1.0))
    for ov in lk.get('overlays', []):
        image(ov['path'], mv.frame_final_start, mv.frame_final_duration, 6, ov.get('blend', 'ALPHA_OVER'), float(ov.get('alpha', 1.0)))
W, H = sc.render.resolution_x, sc.render.resolution_y
for m in post.get('movies', []):
    p = m.get('path')
    if not p or not os.path.exists(p):
        print('post: no clip for', m.get('shotRef') or p, flush=True)
        continue
    a = 1 + int(m['start'])
    ch = lane(12, a, a + int(m['length']))
    st = strips.new_movie('clip%d' % a, p, ch, a, fit_method='ORIGINAL')
    clip(st, int(m['length']))
    r = m['rect']
    el = st.elements[0] if len(st.elements) else None
    ow = (el.orig_width if el and el.orig_width else 1920) or 1920
    k = float(r['w']) * W / ow
    st.transform.scale_x = st.transform.scale_y = k
    st.transform.offset_x = (float(r['cx']) - 0.5) * W
    st.transform.offset_y = (0.5 - float(r['cy'])) * H
    st.blend_type = 'ALPHA_OVER'
# screen drawings first, so captions and cut-ins stay on top of them
for ov in post.get('drawings', []):
    image(ov['path'], 1 + int(ov['start']), int(ov['length']), 19)
for ov in post.get('overlays', []):
    image(ov['path'], 1 + int(ov['start']), int(ov['length']), 20)
for t in post.get('transitions', []):
    # the colour fills in up to the cut, then clears: half the frames on each side
    n = max(2, int(t.get('frames', 12)))
    cut = 1 + int(t['at'])
    a, b = max(1, cut - n // 2), min(start, cut + (n - n // 2))
    if b <= a:
        continue
    col = t.get('color', '#1F1F1D').lstrip('#')
    ch = lane(26, a, b)
    try:   # 5.x takes a length, 4.x an end frame
        st = strips.new_effect('trans%d' % cut, 'COLOR', ch, frame_start=a, length=b - a)
    except TypeError:
        st = strips.new_effect('trans%d' % cut, 'COLOR', ch, frame_start=a, frame_end=b)
    st.color = tuple(int(col[i:i + 2], 16) / 255 for i in (0, 2, 4))
    st.blend_type = 'ALPHA_OVER'
    for f, v in ((a, 0.0), (cut, 1.0), (b, 0.0)):
        st.blend_alpha = v
        st.keyframe_insert('blend_alpha', frame=f)
    print(f"post: {t.get('kind')} at frame {cut}", flush=True)
pp = post.get('paper')
if pp and pp.get('path'):
    image(pp['path'], 1, start - 1, 40, 'ALPHA_OVER', float(pp.get('alpha', 0.6)))
if post.get('music', {}).get('path') and os.path.exists(post['music']['path']):
    bed = strips.new_sound('music_bed', post['music']['path'], lane(30, 1, start), 1)
    if bed.frame_final_end > start:
        bed.frame_final_end = start
    for f, v in post['music'].get('keys') or [[0, 0.35]]:
        bed.volume = float(v)
        bed.keyframe_insert('volume', frame=1 + int(f))
bleep = post.get('bleep')
for a, b in post.get('bleeps', []):
    a, b = 1 + int(a), 1 + int(b)
    if voice is not None:
        for f, v in ((a - 1, 1.0), (a, 0.0), (b, 0.0), (b + 1, 1.0)):
            voice.volume = v
            voice.keyframe_insert('volume', frame=f)
        voice.volume = 1.0
    if bleep and os.path.exists(bleep):
        t = strips.new_sound('bleep%d' % a, bleep, lane(32, a, b), a)
        t.frame_final_end = b
        t.volume = 0.5

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
