"""Deliver panel: format presets, project folders, versioned renders, preview/final quality,
colour (sRGB, HDR, ACES), MP4 with audio, a render queue and a 'final to top level' step."""
import json
import os
import re
import shutil
import subprocess
import threading
import bpy
from . import _util

LABEL, ICON, GROUP = 'Deliver + render queue', 'RENDER_ANIMATION', 'Output'

FORMATS = {
    'Reel 9:16 (1080x1920)': (1080, 1920, 30),
    'Feed 4:5 (1080x1350)': (1080, 1350, 30),
    'Square (1080x1080)': (1080, 1080, 30),
    'YouTube (1920x1080)': (1920, 1080, 30),
    '4K (3840x2160)': (3840, 2160, 30),
    '4K vertical (2160x3840)': (2160, 3840, 30),
    'Cinema 24 fps (1920x1080)': (1920, 1080, 24),
}
COLOURS = [
    ('SRGB', 'Normal (sRGB, AgX)', 'Best for Instagram and most screens'),
    ('SRGB_STD', 'Flat colours (sRGB, Standard)', 'Exact brand colours: doodles, flat and toon looks'),
    ('HDR_PQ', 'HDR YouTube (Rec.2100 PQ, 10-bit)', 'Blender 5.x: HDR video for YouTube'),
    ('HDR_HLG', 'HDR broadcast (Rec.2100 HLG, 10-bit)', 'Blender 5.x'),
    ('ACES', 'Client work (ACES 2.0, ACEScg)', 'Blender 5.x: ACES working space and view'),
    ('P3', 'Apple screens (Display P3)', 'Wide colour for Mac/iPhone viewing'),
]


class CTK_DeliverProps(bpy.types.PropertyGroup):
    project: bpy.props.StringProperty(name='Project', default='')
    fmt: bpy.props.EnumProperty(name='Format', items=[(k, k, '') for k in FORMATS])
    colour: bpy.props.EnumProperty(name='Colour', items=COLOURS)
    output: bpy.props.EnumProperty(name='Output', items=[('MP4', 'MP4 video (with sound)', ''),
                                                         ('PNG', 'PNG frames', ''), ('EXR', 'EXR frames (compositing)', '')])
    preview: bpy.props.BoolProperty(name='Preview quality', default=False,
                                    description='Half size, fewer samples, every frame. Switch off for the final')


def project_dir(scene):
    p = _util.addon_prefs()
    root = bpy.path.abspath(p.deliver_root) if p and p.deliver_root else (os.environ.get('CTK_DELIVER_ROOT') or os.path.join(
        os.path.expanduser('~'), 'Documents', 'Renders'))
    name = scene.ctk_deliver.project or bpy.path.display_name_from_filepath(bpy.data.filepath) or 'Untitled'
    name = re.sub(r'[\\/:*?"<>|]+', '_', name).strip() or 'Untitled'
    return os.path.join(root, name), name


def next_version(folder, name):
    os.makedirs(folder, exist_ok=True)
    vs = [int(m.group(1)) for f in os.listdir(folder) for m in [re.search(re.escape(name) + r'_v(\d{3})', f)] if m]
    return max(vs, default=0) + 1


def _set_video(scene):
    im = scene.render.image_settings
    if hasattr(im, 'media_type'):
        im.media_type = 'VIDEO'
    im.file_format = 'FFMPEG'
    ff = scene.render.ffmpeg
    ff.format = 'MPEG4'
    ff.codec = 'H264'
    ff.constant_rate_factor = 'HIGH'
    ff.ffmpeg_preset = 'GOOD'
    has_sound = bool(scene.sequence_editor and any(s.type == 'SOUND' for s in _all_strips(scene))) \
        or any(o.type == 'SPEAKER' for o in scene.objects)
    ff.audio_codec = 'AAC' if has_sound else 'NONE'
    ff.audio_bitrate = 256
    ff.audio_mixrate = 48000


def _all_strips(scene):
    from ..compat import strips_all
    return strips_all(scene)


def _set_frames(scene, fmt):
    im = scene.render.image_settings
    if hasattr(im, 'media_type'):
        im.media_type = 'MULTI_LAYER_IMAGE' if fmt == 'EXR' else 'IMAGE'
    im.file_format = 'OPEN_EXR_MULTILAYER' if fmt == 'EXR' else 'PNG'
    im.color_mode = 'RGBA'
    if fmt == 'PNG':
        im.color_depth = '8'


def _try(obj, prop, values):
    for v in values:
        try:
            setattr(obj, prop, v)
            return v
        except (TypeError, ValueError):
            continue
    return None


def apply_colour(scene, kind):
    """Returns a short note of what was applied (some need Blender 5.x)."""
    ds, vs = scene.display_settings, scene.view_settings
    note = ''
    if kind == 'SRGB':
        _try(ds, 'display_device', ['sRGB']); _try(vs, 'view_transform', ['AgX'])
        _try(vs, 'look', ['None', 'AgX - Base Contrast'])
    elif kind == 'SRGB_STD':
        _try(ds, 'display_device', ['sRGB']); _try(vs, 'view_transform', ['Standard'])
    elif kind == 'P3':
        _try(ds, 'display_device', ['Display P3']); _try(vs, 'view_transform', ['AgX', 'Standard'])
    elif kind in ('HDR_PQ', 'HDR_HLG'):
        disp = 'Rec.2100-PQ' if kind == 'HDR_PQ' else 'Rec.2100-HLG'
        if _try(ds, 'display_device', [disp]) is None:
            return 'HDR video needs Blender 5.0 or newer'
        _try(vs, 'view_transform', ['AgX HDR', 'AgX', 'Standard'])
        ff = scene.render.ffmpeg
        ff.codec = 'H265'
        _try(scene.render.image_settings, 'color_depth', ['10'])
        note = 'HDR: H.265 10-bit'
    elif kind == 'ACES':
        if hasattr(bpy.ops.wm, 'set_working_color_space') and hasattr(bpy.data, 'colorspace'):
            try:
                bpy.ops.wm.set_working_color_space(working_space='ACEScg', convert_colors=True)
            except Exception:
                pass
        _try(ds, 'display_device', ['sRGB'])
        if _try(vs, 'view_transform', ['ACES 2.0', 'ACES 1.3']) is None:
            return 'ACES views need Blender 5.0 or newer'
        note = 'ACEScg working space'
    return note or 'Colour set'


def apply_quality(scene, preview):
    keep = scene.get('ctk_final')
    r = scene.render
    if preview:
        if not keep:
            scene['ctk_final'] = {'pct': r.resolution_percentage, 'cy': scene.cycles.samples if hasattr(scene, 'cycles') else 0,
                                  'ev': scene.eevee.taa_render_samples, 'simp': r.use_simplify}
        r.resolution_percentage = 50
        if hasattr(scene, 'cycles'):
            scene.cycles.samples = min(scene.cycles.samples, 32)
        scene.eevee.taa_render_samples = min(scene.eevee.taa_render_samples, 16)
    elif keep:
        r.resolution_percentage = keep['pct']
        if hasattr(scene, 'cycles') and keep['cy']:
            scene.cycles.samples = keep['cy']
        scene.eevee.taa_render_samples = keep['ev']
        del scene['ctk_final']


def setup(scene):
    d = scene.ctk_deliver
    folder, name = project_dir(scene)
    work = os.path.join(folder, 'work', 'renders')
    os.makedirs(work, exist_ok=True)
    w, h, fps = FORMATS[d.fmt]
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps, r.fps_base = fps, 1.0
    if d.output == 'MP4':
        _set_video(scene)
    else:
        _set_frames(scene, d.output)
    note = apply_colour(scene, d.colour)
    apply_quality(scene, d.preview)
    v = next_version(work, name)
    tag = '_preview' if d.preview else ''
    if d.output == 'MP4':
        r.filepath = os.path.join(work, '%s_v%03d%s' % (name, v, tag))
        r.use_file_extension = True
    else:
        sub = os.path.join(work, '%s_v%03d%s' % (name, v, tag))
        os.makedirs(sub, exist_ok=True)
        r.filepath = os.path.join(sub, name + '_')
    return folder, r.filepath, note


def latest_render(scene):
    folder, name = project_dir(scene)
    work = os.path.join(folder, 'work', 'renders')
    if not os.path.isdir(work):
        return None
    files = [os.path.join(work, f) for f in os.listdir(work) if f.startswith(name + '_v') and '_preview' not in f
             and os.path.isfile(os.path.join(work, f))]
    return max(files, key=os.path.getmtime) if files else None


# ---------------------------------------------------------- queue

def queue():
    return _util.load_json('render_queue.json', [])


def save_queue(q):
    _util.save_json('render_queue.json', q)


def command(job, blender=None):
    exe = blender or bpy.app.binary_path or 'blender'
    cmd = [exe, '-b', job['file']]
    if job.get('scene'):
        cmd += ['-S', job['scene']]
    if job.get('start') and job.get('end'):
        cmd += ['-s', str(job['start']), '-e', str(job['end'])]
    cmd += ['-a']
    return cmd


RUN = {'busy': False, 'log': ''}


def run_queue(on_done=None):
    q = [j for j in queue() if j.get('status') != 'done']
    if not q:
        return False

    def work():
        RUN['busy'] = True
        for job in q:
            RUN['log'] = 'Rendering ' + os.path.basename(job['file'])
            try:
                res = subprocess.run(command(job), capture_output=True, text=True)
                job['status'] = 'done' if res.returncode == 0 else 'failed'
            except Exception as e:
                job['status'] = 'failed: %s' % e
            allq = queue()
            for j in allq:
                if j['id'] == job['id']:
                    j['status'] = job['status']
            save_queue(allq)
        RUN['busy'] = False
        RUN['log'] = 'Queue finished: %d jobs' % len(q)
        if on_done:
            on_done()
    threading.Thread(target=work, daemon=True).start()
    return True


# ---------------------------------------------------------- operators

class CTK_OT_deliver_setup(bpy.types.Operator):
    """Make the project folders and set size, fps, colour, quality and the versioned file name"""
    bl_idname = 'ctk.deliver_setup'
    bl_label = 'Set up render'

    def execute(self, context):
        folder, path, note = setup(context.scene)
        self.report({'INFO'}, f'{note}. Renders go to {path}')
        return {'FINISHED'}


class CTK_OT_deliver_render(bpy.types.Operator):
    """Set up, then render the animation"""
    bl_idname = 'ctk.deliver_render'
    bl_label = 'Render now'

    def execute(self, context):
        setup(context.scene)
        bpy.ops.render.render('INVOKE_DEFAULT', animation=True)
        return {'FINISHED'}


class CTK_OT_deliver_final(bpy.types.Operator):
    """Copy the newest final render to the top of the project folder"""
    bl_idname = 'ctk.deliver_final'
    bl_label = 'Make it the final'

    def execute(self, context):
        src = latest_render(context.scene)
        if not src:
            self.report({'WARNING'}, 'No final render found yet (preview renders are skipped)')
            return {'CANCELLED'}
        folder, name = project_dir(context.scene)
        dst = os.path.join(folder, name + os.path.splitext(src)[1])
        shutil.copy2(src, dst)
        self.report({'INFO'}, 'Final: ' + dst)
        return {'FINISHED'}


class CTK_OT_deliver_open(bpy.types.Operator):
    """Open the project folder"""
    bl_idname = 'ctk.deliver_open'
    bl_label = 'Open folder'

    def execute(self, context):
        folder, _ = project_dir(context.scene)
        os.makedirs(folder, exist_ok=True)
        bpy.ops.wm.path_open(filepath=folder)
        return {'FINISHED'}


class CTK_OT_queue_add(bpy.types.Operator):
    """Save this file and add it to the render queue"""
    bl_idname = 'ctk.queue_add'
    bl_label = 'Add to queue'

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({'ERROR'}, 'Save the file first')
            return {'CANCELLED'}
        setup(context.scene)
        bpy.ops.wm.save_mainfile()
        sc = context.scene
        q = queue()
        q.append({'id': '%d' % (max([int(j['id']) for j in q], default=0) + 1), 'file': bpy.data.filepath,
                  'scene': sc.name, 'start': sc.frame_start, 'end': sc.frame_end, 'status': 'waiting'})
        save_queue(q)
        self.report({'INFO'}, f'{len(q)} in the queue')
        return {'FINISHED'}


class CTK_OT_queue_run(bpy.types.Operator):
    """Render every waiting job in the background, one after another. You can keep working"""
    bl_idname = 'ctk.queue_run'
    bl_label = 'Run queue'

    def execute(self, context):
        if RUN['busy']:
            self.report({'INFO'}, 'The queue is already running')
            return {'CANCELLED'}
        if not run_queue():
            self.report({'INFO'}, 'Nothing waiting in the queue')
            return {'CANCELLED'}
        return {'FINISHED'}


class CTK_OT_queue_clear(bpy.types.Operator):
    """Remove finished jobs (or everything) from the queue"""
    bl_idname = 'ctk.queue_clear'
    bl_label = 'Clear queue'
    everything: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        save_queue([] if self.everything else [j for j in queue() if j.get('status') != 'done'])
        return {'FINISHED'}


CLASSES = (CTK_DeliverProps, CTK_OT_deliver_setup, CTK_OT_deliver_render, CTK_OT_deliver_final, CTK_OT_deliver_open,
           CTK_OT_queue_add, CTK_OT_queue_run, CTK_OT_queue_clear)


def register_extra():
    bpy.types.Scene.ctk_deliver = bpy.props.PointerProperty(type=CTK_DeliverProps)


def unregister_extra():
    del bpy.types.Scene.ctk_deliver


def draw(layout, context):
    d = context.scene.ctk_deliver
    row = layout.row(align=True)
    row.prop(d, 'project')
    row.prop(d, 'preview', toggle=True)
    row = layout.row(align=True)
    row.prop(d, 'fmt', text='')
    row.prop(d, 'colour', text='')
    row.prop(d, 'output', text='')
    row = layout.row(align=True)
    row.operator('ctk.deliver_setup', icon='PREFERENCES')
    row.operator('ctk.deliver_render', icon='RENDER_ANIMATION')
    row = layout.row(align=True)
    row.operator('ctk.deliver_final', icon='CHECKMARK')
    row.operator('ctk.deliver_open', icon='FILE_FOLDER')
    box = layout.box()
    q = queue()
    box.label(text=f'Render queue: {len(q)} jobs', icon='SEQ_STRIP_DUPLICATE')
    for j in q[-6:]:
        box.label(text=f"{os.path.basename(j['file'])} · {j['scene']} · {j['status']}")
    row = box.row(align=True)
    row.operator('ctk.queue_add', icon='ADD')
    row.operator('ctk.queue_run', icon='PLAY')
    row.operator('ctk.queue_clear', text='', icon='TRASH')
    if RUN['log']:
        box.label(text=RUN['log'])
