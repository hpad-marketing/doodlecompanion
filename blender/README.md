# Doodle Library (Blender 4.5 add-on)

Bunny's shared asset library for Blender and Doodle Studio 3D. Everything is drawn with the 3D Bunny's own look:
flat mustard `#E0A64B`, ink `#1F1F1D`, one screen-constant stroke weight (`BUNNY_settings.ink_px`).

## What's in the library

| Section | Contents | Stored as |
|---|---|---|
| Motions | 408 Doodle Studio motions with their face beats, plus your own | `motions/doodle_studio.json` (native track values), `motions/user/*.blend` (actions) |
| Faces | 42 expressions, winks and blinks, 8 gazes, 18 mouth shapes, plus your own | rows in `library.json` |
| Mouths | Doodle Studio's built-in mouths + the 14 approved mouth sets | `mouths/mouth_sets.json` |
| Props | The 90 approved 360° props as real 3D models, grip at the origin, researched hold | `props/props.blend` |
| Scenery | 90 hand-modelled set pieces | `scenery/scenery.blend` |
| Background sets | 17 closed room blocks at real scale to Bunny: living room, bedroom, kitchen, bathroom, creator desk, office, cafe, restaurant, classroom, meeting room, gym, grocery, airport, train station, park, street, beach | `sets/sets.blend` (one collection per set) |

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
3. `build_sets.py OUT` – scenery models (`models.py`) and room sets (`rooms.py`)
4. `build_previews.py OUT props/props.blend prop` and `... scenery/scenery.blend scenery`
5. `build_bunny_previews.py faces|mouths|motions|sets`
6. `merge_index.py OUT` – writes `library.json`, keeping user-saved items and usage counts

The add-on imports `look.py`, `ds_map.py`, `collision.py` and `face.py` from `blender-bunny/lib` at runtime, so it
always matches the current rig.
