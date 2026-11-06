# Droid Kit

One versioned kit for building, finishing and checking the droid cast (RX-07, the hazard droid, the hover drone and every droid after them). The scripts stay the same for every droid. What makes each droid different lives in one settings file, `droids/<id>.json`.

Version: see `VERSION`. Bump it and add a line to the change log in the PR whenever a script changes.

## Layout

| Folder | What is in it |
|---|---|
| `kit/` | Pipeline scripts: rig UI, tune, finish, poses, motions, library, weathering, edges, UVs, wear, decals, details, soft bevel, weight/springs, emotive hooks, world, floor, stage, DualSense drive test, PC paths |
| `droids/` | One settings file per droid, plus `_template.json` with every required key |
| `materials/` | `build_library.py` makes the shared material library, `link_library.py` links a droid to it |
| `tools/` | `new_droid.py`, `check_names.py`, `lock_sheet.py`, `overlay.py`, `status.py`, `palette_renders.py` |

## Running a script

Every script runs headless, either with the bpy 5.2 wheel or with Blender:

```
DROID=rx07 python3 kit/weather.py in.blend out.blend
DROID=rx07 blender -b --python kit/weather.py -- in.blend out.blend
```

`DROID=<id>` picks `droids/<id>.json`. `DROID_SETTINGS=<path>` points at a settings file somewhere else. `DROID_OUT` sets where renders and reports go (default `out/`).

## Pipeline order

1. Model and rig (`droids/<id>/build.py`, then `kit/tune.py`, `kit/finish.py`)
2. Poses and motions (`kit/poses.py`, `kit/anim.py`, `kit/library.py`)
3. UVs (`kit/uv.py`), then surfaces (`kit/weather.py`, `kit/edges.py`, `kit/wear.py`)
4. Detail (`kit/decals.py`, `kit/detail.py`, `kit/softbevel.py`), checked with `kit/detail_check.py`
5. Weight and springs (`kit/weight.py`), emotive hooks (`kit/emotive.py`)
6. World and stage (`kit/world.py`, `kit/scanfloor.py`, `kit/stage.py`)
7. Link the shared library (`materials/link_library.py`), then make the PC copy (`kit/pc_paths.py`): scans load from `//../_shared/textures/` instead of being packed, and `DROID_LIB=//../_shared/RB_Materials.blend` keeps the library path relative

## Hook contract

Other add-ons (the spaceship sitcom add-on first) drive a droid through these names only, so every droid must have them. `tools/check_names.py` fails the build if one is missing.

- `hooks.leds`: emissive LED objects, named `RB_LED_<colour>`, each with its own material
- `hooks.glow_materials` and `hooks.glow_node`: materials with an Emission node called `Glow` (strength 0 at rest)
- `hooks.antenna_chains`, `hooks.eye`: bones the voice and emote tools animate
- `hooks.controls`: plain names (look_pan, turn_waist, crouch, grip, elbow, step...) mapped to `bone:channel`. `{S}` means L and R.

## Axes and rules

- Droids face -Y. The droid's left side is +X. Local Z is up on every part.
- Nothing intersects and nothing floats. `tools/collision_check.py` must report 0 intersecting pairs before anything is shown. It tests every droid part against every other part and against everything in the scene, and scene parts against each other, in every pose preset and every library motion. Resting contact (a foot on the floor) up to `collision.touch_mm` (0.5 mm) is allowed; designed joint contacts, bolts on their own part and hose ends in their hooked parts are skipped.
- If a motion sinks a foot into the floor, `tools/floor_clamp.py in.blend out.blend` lifts that foot's IK control by exactly the dip on those frames.
- Physics is real (user rule, every droid): motion follows mass, centre of gravity, momentum and balance, and every part works as a real hinge or motor. `kit/physics.py` gives each part a mass from its shape and material (steel shells, polymer, glass, plus internal equipment in settings `physics.internal`). `tools/physics_audit.py in.blend report.json` plays every motion and reports total mass, where the centre of mass and the ZMP (where the floor must push) sit against the feet, and the torque and speed of every joint. `tools/balance_fix.py in.blend out.blend all` re-times the body (COG) so the ZMP stays over the feet: sideways sway over the planted foot in walks, a small forward/back brace on fast moves. `tools/limit_order_fix.py` moves joint limits that sat above a copy constraint (and so did nothing) below it. Order after any motion change: balance_fix, then floor_clamp, then collision_check, then physics_audit.
- Show stills before any full render. Don't change a droid's look after it locks (`"locked": true` in its settings).

## Shared material library and texture shelf

- Shelf: `DeepInDoodles\_shared\textures\<asset>\<file>_2k.jpg`
- Library: `DeepInDoodles\_shared\RB_Materials.blend`, built with `python3 materials/build_library.py <shelf> RB_Materials.blend`. Its images use paths relative to the library, so the folder can move as one piece.
- Each droid links the node groups `RB Weathered Metal` and `RB Black Polymer` with `python3 materials/link_library.py <library> in.blend out.blend`. Each droid keeps its own thin materials, so its paint palette stays its own while the shader is shared.

## Small droids

Settings that scale the finish for droids much smaller than RX-07: `weather_scale` (wear pattern size, e.g. 2.6), `uv_smooth_deg` (UV region angle, e.g. 42), `bevel` ([big, small, small-below] in m, e.g. [0.0016, 0.0009, 0.03]). Lock sheet: `lock_sheet.state_framing: "full"` keeps round droids whole in the light-state panels; close-ups walk round a part until nothing blocks it, or take `{"object": ..., "view": [x, y, z]}`.

## Starting a new droid

```
python3 tools/new_droid.py --id hazard --name "Hazard Droid" --folder HazardDroid --root C:/Users/Sushant/Documents/DeepInDoodles --ref photo.jpg
```

This makes the droid folder (`ref/`, `work/`, `work/versions/`, `work/stills/`), `droids/hazard.json` from the template, a look-dev stage at `work/lookdev.blend` (lights, floor, turntable camera, shared groups linked) and `STATUS.md`.

## Model-lock checks

- `tools/lock_sheet.py in.blend outdir [samples]`: turntable, hero poses, light states and close-ups as one sheet plus `manifest.json`, for the Approve/Fix page
- `tools/fit_camera.py in.blend photo.jpg [pose]`: finds the camera that matches the reference photo and stores it in `reference.camera`
- `tools/overlay.py in.blend photo.jpg out.png`: model at 50% over the reference photo, from `reference.camera`
- `DROID=<id> python3 tools/status.py <droid_folder> --version vNN --note "what changed"`: rewrites `STATUS.md` and adds a line to `work/versions/CHANGES.md`

One current file sits at the top of each droid folder. Older versions go to `work/versions/` with a one-line note.

## GPU renders and nightly checks on Sushi

Renders and tests go through the render queue at `DeepInDoodles\_queue` (format in its README): drop a job JSON with `blend`, `script`, `args`, `label` and `thread` into `jobs\`. Each droid with a check script gets a line in `_queue\nightly.json`. The kit is mirrored on Sushi at `DeepInDoodles\_shared\droid-kit`; point a droid's nightly line at `_shared\droid-kit\tools\collision_check.py` (it finds the droid's settings from the open file's name). RX-07's current file is `DeepInDoodles\Robot\Robot_RX07.blend`.
