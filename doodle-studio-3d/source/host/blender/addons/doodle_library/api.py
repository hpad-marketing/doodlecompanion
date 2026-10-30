"""Doodle Library API for Doodle Studio 3D, scripts and MCP tools.

    import doodle_library.api as dl
    dl.items('motion')                    # library rows
    dl.insert('motion-wave-hello')        # key a motion at the playhead
    dl.insert('face-01')                  # key an expression
    dl.insert('prop-mug', hold=True)      # add a prop, put it in Bunny's hand (real grip)
    dl.add_text('Dell well'); dl.set_text(ob, 'New|line')
    dl.switch_set('bedroom'); dl.set_prop('rug', False)
    dl.save_motion('My wave', (1, 48)); dl.save_expression('Smirk')
"""
from . import (assets, collide, faces, fx, grips, index, interact, lighting, motions, outfits, packs, placement, sets, storytime,
               style, text3d)

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
        r = faces.apply_expression(it, frame=frame, key=opts.get('key', True))
        if opts.get('key', True):
            faces.fit_speech()  # the new face may talk differently (pucker, teeth, no talking)
        return r
    if cat == 'mouth_set':
        return faces.use_mouth_set(it if it['data'].get('set') else None)
    if cat == 'outfit':
        return outfits.dress(it)
    if cat == 'accessory':
        return outfits.wear(it)
    if cat == 'set':
        return sets.switch_set(it['data']['room'])
    ob = assets.insert_object(it, opts.get('location'))
    if cat == 'prop' and opts.get('hold'):
        grips.attach(ob, side=opts.get('side'), frame=frame)
    return ob


undress = outfits.undress
take_off = lambda item_id: outfits.take_off(index.get(item_id))
worn_accessories = outfits.worn_accessories
save_motion = lambda name, frame_range=None, **kw: motions.save_action(name, frame_range, **kw)
save_expression = faces.save_expression
save_objects = assets.save_objects
attach_prop = grips.attach
release_prop = grips.release
check_grip = grips.check_contact
add_text = text3d.add_text
set_text = text3d.set_text
get_text = text3d.get_text
place = placement.place
drop = placement.drop
lock_bunny = placement.lock_bunny
resolve_collision = collide.resolve
bake_collisions = collide.bake
collision_guard = collide.set_guard
fit_lip_sync = faces.fit_speech  # re-fit keyed speech mouths to the faces on screen
# asset packs
set_open = packs.set_open              # lids, doors, curtains: set_open(ob, 1.0, frame)
set_label = packs.set_label            # type new words on a sign, placard or bubble
set_screen = packs.set_screen          # your image or MP4 on a screen, frame or poster
react = packs.react                    # react('heart', frame): pops over Bunny's head
frame_shot = packs.frame_shot          # foreground framing piece onto a third
add_effect = fx.add_effect             # rain, snow, leaves, confetti, dust, smoke ...
set_effect_amount = fx.set_amount
set_time = lighting.set_time           # day, golden, night (lamps switch on)
sky = lighting.sky                     # day, sunset, stars, storm
lightning = lighting.lightning
flicker = lighting.flicker
sit = interact.sit                     # Bunny sits on the nearest (or given) sit spot
put_on = interact.put_on               # a prop rests on a table's grab spot
add_spots = interact.auto_anchors
physics = interact.physics             # ball, paper, pillow, book, beanbag
simulate = interact.simulate
squish = interact.squish
# storytime kit (open-source fonts, CC0 sounds, all local)
chat = storytime.chat                  # chat([('them', 'you up?'), ('me', 'no')], frame)
pin_label = storytime.label            # label + arrow pointing at an object
journey = storytime.journey            # map with a path drawing itself between stops
time_skip = storytime.time_skip        # '3 hours later' card
horror = storytime.horror              # opt-in horror light kit (off by default)
end_screen = storytime.end_screen      # end screen + subscribe press
story_sound = storytime.sound
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
