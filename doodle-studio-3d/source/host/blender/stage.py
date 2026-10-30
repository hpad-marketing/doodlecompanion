"""Stage for a Doodle Studio 3D shot: the room set, light, outfit, accessories,
mouth set and the library items placed in the shot (props in hand, scenery,
effects, storytime pieces). Everything comes from the Doodle Library through its
own API, so the 3D app and the Blender add-on always build the same thing.

shot['stage'] = {"set": "bedroom", "setProps": {"rug": false, "books": true}, "time": "golden", "sky": "sunset",
                 "shadows": false, "outfit": "raincoat", "accessories": ["bowtie"],
                 "mouthSet": "mouths-bouncy"}
shot['items'] = [{"id": "prop-mug", "frame": 0, "hold": "R"},
                 {"id": "fx:rain", "frame": 0}, {"id": "react:heart", "frame": 40},
                 {"id": "story:time_skip", "frame": 0, "text": "3 hours later"}]
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))


def _library():
    """The Doodle Library add-on: the copy installed in Blender first (it matches the
    library on disk), then the copy that ships with Doodle Studio 3D."""
    try:
        import doodle_library.api as dl
        return dl
    except ImportError:
        pass
    import addon_utils
    for p in addon_utils.paths():
        if os.path.isdir(os.path.join(p, 'doodle_library')):
            sys.path.insert(0, p)
            break
    else:
        sys.path.insert(0, os.path.join(HERE, 'addons'))
    import doodle_library.api as dl
    return dl


def needed(shot):
    st = shot.get('stage') or {}
    return bool(shot.get('items') or any(st.get(k) for k in ('set', 'time', 'sky', 'shadows', 'outfit', 'accessories', 'mouthSet')))


def setup(shot, log):
    """Build the stage before the pose is keyed (outfits re-bind to the rig, sets load
    their sit spots). Returns the items to place after keying."""
    st = shot.get('stage') or {}
    if not needed(shot):
        return []
    dl = _library()
    done = []
    if st.get('set'):
        cam = bpy.context.scene.camera
        if cam is not None and cam.data.type != 'PERSP':
            cam.data.type = 'PERSP'  # the set inks itself for this camera instead of adding its own
        dl.switch_set(st['set'], keep_choices=False)
        for pid, on in (st.get('setProps') or {}).items():
            try:
                dl.set_prop(pid, bool(on))
            except Exception as e:  # a piece renamed in a library update must not stop the render
                log(f'stage: no piece {pid!r} in {st["set"]}: {e}')
        done.append('set ' + st['set'])
    if st.get('time'):
        dl.set_time(st['time'])
    if st.get('sky'):
        dl.sky(st['sky'])
    dl.set_shadows(bool(st.get('shadows')))
    if st.get('outfit'):
        dl.insert('outfit-' + st['outfit'])
        done.append('outfit ' + st['outfit'])
    for acc in st.get('accessories') or []:
        dl.insert('accessory-' + acc)
    if st.get('mouthSet'):
        # a set from mouths/mouth_sets.json by its id (mouths-bouncy, ...)
        from doodle_library import faces
        faces.use_mouth_set({'id': 'mouthset-' + st['mouthSet'], 'data': {'set': st['mouthSet']}})
        done.append('mouths ' + st['mouthSet'])
    log('stage: ' + (', '.join(done) or 'light only'))
    return [dict(i) for i in shot.get('items') or []]


def place(items, log):
    """Library items, keyed at their frame (1-based in Blender)."""
    if not items:
        return
    dl = _library()
    for it in items:
        f = int(it.get('frame', 0)) + 1
        kind, _, name = it['id'].partition(':')
        try:
            if kind == 'fx':
                dl.add_effect(name, frame=f, amount=float(it.get('amount', 1.0)))
            elif kind == 'react':
                dl.react(name, f)
            elif kind == 'story':
                fn = {'time_skip': lambda: dl.time_skip(it.get('text') or 'Later', f),
                      'chat': lambda: dl.chat([tuple(m) for m in it.get('messages') or [('them', it.get('text') or 'hi')]], f),
                      'label': lambda: dl.pin_label(bpy.data.objects.get(it.get('target') or '') or bpy.data.objects['BUNNY_head'], it.get('text') or 'Label', frame=f),
                      'journey': lambda: dl.journey(it.get('stops') or ['Home', 'There'], f),
                      'end_screen': lambda: dl.end_screen(f),
                      'horror': lambda: dl.horror(True)}[name]
                fn()
            elif kind == 'sound':
                dl.story_sound(name, f, volume=float(it.get('volume', 0.8)))
            elif kind == 'text':
                # a 3D headline in chunky doodle lettering, above and behind the character unless placed
                ob = dl.add_text(it.get('text') or 'Text', location=it.get('at') or (0.0, 0.8, 1.25))
            else:
                hold = it.get('hold')
                ob = dl.insert(it['id'], frame=f, hold=bool(hold), side=hold if hold in ('L', 'R') else None,
                               location=it.get('at'))
                if it.get('text') and hasattr(dl, 'set_label'):
                    try:
                        dl.set_label(ob, it['text'])
                    except Exception:
                        pass
            log(f'item {it["id"]} at frame {f}')
        except Exception as e:
            log(f'item {it["id"]} skipped: {e}')
