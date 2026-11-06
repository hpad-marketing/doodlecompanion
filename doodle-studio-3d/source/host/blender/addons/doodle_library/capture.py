"""Save as you use: when the file is saved, new work goes into the library automatically.

- Bunny's animation, if it has keys that did not come from the library, is stored
  as a motion (one per saved file, updated on every save).
- Objects you put in the "Add to Doodle Library" collection are stored as props
  (or scenery if they are bigger than Bunny).
- The face Bunny ends on, if it is a combination not in the library yet, is stored.
Turn it off in the add-on preferences (Auto-save to library).
"""
import os

import bpy
from bpy.app.handlers import persistent

from . import assets, faces, index, motions, paths

INBOX = 'Add to Doodle Library'


def _prefs():
    a = bpy.context.preferences.addons.get(paths.ADDON)
    return a.preferences if a else None


@persistent
def on_save(_dummy=None):
    p = _prefs()
    if not p or not p.auto_capture or not os.path.isdir(paths.library_root()):
        return
    name = bpy.path.display_name_from_filepath(bpy.data.filepath) or 'Untitled'
    try:
        _capture_motion(name)
    except Exception as e:
        print('Doodle Library: motion not captured:', e)
    try:
        _capture_inbox()
    except Exception as e:
        print('Doodle Library: objects not captured:', e)
    try:
        _capture_face(name)
    except Exception as e:
        print('Doodle Library: face not captured:', e)


def _capture_motion(name):
    arm = bpy.data.objects.get('BUNNY_rig')
    act = arm and arm.animation_data and arm.animation_data.action
    if not act:
        return
    fr = act.frame_range
    if fr[1] - fr[0] < 2:
        return
    sig = '%s:%d:%d:%d' % (act.name, fr[0], fr[1], sum(len(fc.keyframe_points) for fc in motions._fcurves(arm)))
    if act.get('dsl_capture_sig') == sig:
        return
    old = act.get('dsl_id')
    item = motions.save_action('%s (auto)' % name, category='Auto-saved')
    if old and old != item['id'] and (index.get(old) or {}).get('sub') == 'Auto-saved':
        data = index.load(force=True)
        data['items'] = [i for i in data['items'] if i['id'] != old]
        index.save(data)
    act['dsl_capture_sig'] = sig


def _capture_inbox():
    coll = bpy.data.collections.get(INBOX)
    if not coll:
        return
    for ob in list(coll.objects):
        if ob.type != 'MESH' or ob.get('dsl_captured'):
            continue
        big = max(ob.dimensions) > 1.2
        assets.save_objects([ob], ob.name, 'scenery' if big else 'prop', sub='Auto-saved')
        ob['dsl_captured'] = 1


def _capture_face(name):
    try:
        arm, fb = faces.face_bone()
    except RuntimeError:
        return
    state = {k: int(fb.get(k, 0)) for k in faces.FACE_PROPS}
    if state['expression'] == 0 and state['gaze'] == 0:
        return
    for it in index.items('expression'):
        d = it.get('data') or {}
        if all(int(d.get(k, 0)) == v for k, v in state.items()):
            return
    faces.save_expression('%s face' % name)


def ensure_inbox():
    coll = bpy.data.collections.get(INBOX)
    if not coll:
        coll = bpy.data.collections.new(INBOX)
        bpy.context.scene.collection.children.link(coll)
    return coll


@persistent
def on_depsgraph(scene, depsgraph=None):
    """Library objects dragged in from Blender's Asset Browser get Bunny's ink automatically."""
    if not depsgraph:
        return
    for u in depsgraph.updates:
        ob = u.id if isinstance(u.id, bpy.types.Object) else None
        if ob and ob.get('dsl_id') and ob.type == 'MESH' and not ob.modifiers.get('DSL Ink') \
                and not ob.library and ob.name in scene.objects:
            try:
                from . import style
                bpy.app.timers.register(lambda o=ob.name: _style_later(o), first_interval=0.01)
            except Exception:
                pass


def _style_later(name):
    from . import style
    ob = bpy.data.objects.get(name)
    if ob and not ob.modifiers.get('DSL Ink'):
        try:
            style.apply_style(ob)
        except Exception as e:
            print('Doodle Library: could not style', name, e)
    return None


def register():
    if on_save not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(on_save)
    if on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph)


def unregister():
    for h, f in ((bpy.app.handlers.save_post, on_save), (bpy.app.handlers.depsgraph_update_post, on_depsgraph)):
        if f in h:
            h.remove(f)
