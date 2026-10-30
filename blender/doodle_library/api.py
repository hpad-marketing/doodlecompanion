"""Doodle Library API for Doodle Studio 3D, scripts and MCP tools.

    import doodle_library.api as dl
    dl.items('motion')                    # library rows
    dl.insert('motion-wave-hello')        # key a motion at the playhead
    dl.insert('face-01')                  # key an expression
    dl.insert('prop-mug', hold=True)      # add a prop, put it in Bunny's hand
    dl.switch_set('bedroom'); dl.set_prop('rug', False)
    dl.save_motion('My wave', (1, 48)); dl.save_expression('Smirk')
"""
from . import assets, faces, index, motions, sets, style

items = index.items
get = index.get
categories = [c[0] for c in index.CATEGORIES]
reload = lambda: index.load(force=True)


def insert(item_id, frame=None, **opts):
    """Insert any library item at the playhead (or `frame`)."""
    it = index.get(item_id)
    if not it:
        raise KeyError(item_id)
    cat = it['category']
    if cat == 'motion':
        if it['kind'] == 'ds':
            return motions.insert_ds(item_id, start=frame, include_camera=opts.get('include_camera', False),
                                     fix_clipping=opts.get('fix_clipping', True), mirror=opts.get('mirror', False))
        return motions.insert_action(it, start=frame)
    if cat == 'expression':
        return faces.apply_expression(it, frame=frame, key=opts.get('key', True))
    if cat == 'mouth_set':
        return faces.use_mouth_set(it if it['data'].get('set') else None)
    if cat == 'set':
        return sets.switch_set(it['data']['room'])
    ob = assets.insert_object(it, opts.get('location'))
    if cat == 'prop' and opts.get('hold'):
        assets.attach_prop(ob, side=opts.get('side'))
    return ob


save_motion = lambda name, frame_range=None, **kw: motions.save_action(name, frame_range, **kw)
save_expression = faces.save_expression
save_objects = assets.save_objects
attach_prop = assets.attach_prop
use_mouth_set = lambda item_id=None: faces.use_mouth_set(index.get(item_id) if item_id else None)
sets_list = sets.sets
switch_set = sets.switch_set
set_prop = sets.set_prop
set_state = sets.set_state
declutter = sets.declutter
parallax_camera = sets.parallax_camera
setup_camera = sets.setup_camera
set_shadows = style.set_shadows
apply_style = style.apply_style
retarget_camera = style.retarget_camera
