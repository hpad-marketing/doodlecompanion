# Doodle Library (Blender 4.5 add-on)

Bunny's shared asset library for Blender and Doodle Studio 3D. Everything is drawn with the 3D Bunny's own look:
flat mustard `#E0A64B`, ink `#1F1F1D`, one screen-constant stroke weight (`BUNNY_settings.ink_px`).

## What's in the library

| Section | Contents | Stored as |
|---|---|---|
| Motions | 408 Doodle Studio motions with their face beats, plus your own | `motions/doodle_studio.json` (native track values), `motions/user/*.blend` (actions) |
| Faces | 42 expressions, winks and blinks, 8 gazes, 18 mouth shapes, 52 story-beat faces (Bunny, Koala, Frog, by name), plus your own | rows in `library.json` |
| Mouths | Doodle Studio's built-in mouths + the 14 approved mouth sets + Through teeth | `mouths/mouth_sets.json` |
| Props | The 90 approved 360° props as real 3D models, grip at the origin, researched hold | `props/props.blend` |
| Scenery | 282 hand-modelled set pieces | `scenery/scenery.blend` |
| Asset packs | 124 pieces from the 38 approved packs: reveal props that open, explainer boards, signs and placards with typed words, 3D speech bubbles, 12 reactions, screens and frames that show your own clip, rain / snow / party / impact / smoke / magic pieces, practical lights, crowd extras, critters, talking objects, rides with turning wheels, food / festival / music / creator / sports kits, foreground framing, backdrops, skies, skylines; 16 of them are hand props with a researched grip | `packs/packs.blend` |
| Storytime kit | Patrick Hand, Gochi Hand and Bangers (SIL Open Font License) and 12 sounds made for the library (CC0) | `storytime/fonts`, `storytime/sounds` |
| Background sets | 83 sets at real scale to Bunny: the 17 rooms (living room ... beach), 42 approved locations (open-sky meadow, hill, cliff, lake, highway, campsite, sea, clouds, space, dreamscape, farm, funfair, chai stall, ghat, balcony, salon, bank, museum, attic, train, plane, lab, cave, castle, spaceship, inside a box and more) and 24 world-pack sets (haunted room, foggy forest, creaky hallway, moon base, underwater, jungle, desert, snowy peak, space station, podcast desk, news desk, concert stage, game show, curved rap studio, inside a car, inside a bus, lift, hospital, library, cinema, rooftop, mustard / ink backdrop, half-room corner). Open-sky sets have no edges and use flat far cards, so they stay light to render | `sets/sets.blend` (one collection per set) |

The library folder is `Documents/Talking Character App/blender-library/` and is also registered as a Blender asset
library ("Doodle Library"), so props and scenery can be dragged in from the Asset Browser.

## Panels (3D View › Sidebar › Doodle)

- **Doodle Library**: section tabs, search, group filter, sort (A–Z, most used, recent), preview, Insert.
  Motions insert at the playhead through the rig's own `ds_map` and clipping solver (Mirror and Camera moves optional).
  Props can go straight into Bunny's hand with their researched grip. Save motion / Save face / Save selection.
- **Background**: pick a set and the room swaps at once. Tick pieces on and off (things standing on a piece follow it);
  choices are remembered per room in the file. All on, All off, Declutter. Shadows (off = flat Doodle Studio look),
  shade strength, form shading, sun angle. Eye-level camera and eased parallax moves (Orbit, Slide, Push in).
- **Look**: ink width, line boil, re-aim ink after a camera change, "Add to library" collection, open folder.

## Holding, placing, colliding

- **Holding**: every prop has a grip from how the real thing is held (fist, hook, pinch, palm, two hands, worn).
  Put in hand searches the hand spot, turn, lean and slide so the prop touches the mitten at the right point and stays
  out of his head, body and sleeves; limits keep G / R inside what the grip allows. Gloves and mittens go over the hand.
  Full test: 85 of 90 props clean (cake, lantern, light bulb, skateboard and flask still graze his sleeve or shirt).
- **Placing**: Place (click in the view) snaps a piece onto floor, table, wall or free air; wheel turns, Ctrl+wheel
  raises, Tab switches mode. Bunny is locked while you place so the rig can't be grabbed.
- **Collisions**: Bake collisions keys fixes so no prop or text ever sits inside Bunny, the Koala or the Frog; Live guard
  fixes the current frame while you scrub.
- **Text**: Add 3D text (and every sign, placard, bubble, neon sign) is typed text you can edit in the panel. `|` = new line.

## Scene life panel

Time of day (Day, Golden, Night: lamps switch on and light pools), Sky (day, sunset, stars, storm), Lightning, Add effect
(rain, downpour, splashes, snow, leaves, petals, wind, speed lines, steam, smoke, sparkles, confetti, streamers,
fireworks, dust, poof, sparkle burst), Reaction (pops over Bunny's head), Sit on nearest seat (every chair, couch, bench,
bed, counter and table gets sit / lie / lean / grab spots when a set loads). Storytime: Chat, Label + arrow, Journey map,
Time skip, Horror (off unless you turn it on), End screen. Selected pieces show Open / Close, Show my clip, Frame the shot,
Sit Bunny here, Words, Physics (ball, paper, pillow, book, beanbag).

## Saved as you use it

With *Auto-save to library* on (preferences), every file save stores Bunny's new animation as a motion, any new face
combination, and anything in the "Add to Doodle Library" collection. Every insert counts a use, so *Most used* and
*Recent* sorting work.

## Scripting / Doodle Studio 3D

```python
import doodle_library.api as dl
dl.items('motion'); dl.insert('motion-wave-hello', frame=1)
dl.insert('prop-mug', hold=True)
dl.switch_set('bedroom'); dl.set_prop('rug', False); dl.set_state()
dl.use_mouth_set('mouthset-toothy'); dl.set_shadows(True); dl.parallax_camera('orbit', 72)
dl.save_motion('My wave', (1, 48)); dl.save_expression('Smirk')
```

## Rebuilding the library (`build/`)

Run with Blender 4.5 (`blender -b --python X -- args`) or the `bpy==4.5.3` module, with `DSL_BUNNY` pointing at
`blender-bunny/`:

1. `build_data.py SRC_DIR face_library.json OUT` – motions, faces, mouth sets
2. `build_props.py props-360/library picks.json OUT`
3. `build_sets.py OUT` – scenery models (`models.py`, `models2.py`, `models4.py`) and sets (`rooms.py`, `rooms2.py`, `rooms3.py`)
4. `build_previews.py OUT props/props.blend prop` and `... scenery/scenery.blend scenery`
5. `build_bunny_previews.py faces|mouths|motions|sets`
6. `build_packs.py OUT` – asset packs (`models3.py`); `make_sounds.py OUT/storytime/sounds`; copy `library_extra/storytime`
7. `merge_index.py OUT` – writes `library.json`, keeping user-saved items and usage counts (the add-on also does this by
   itself when an update brings newer `index_parts`)

The add-on imports `look.py`, `ds_map.py`, `collision.py` and `face.py` from `blender-bunny/lib` at runtime, so it
always matches the current rig.
