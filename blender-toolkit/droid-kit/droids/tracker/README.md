# Tracked porter droid (droid 5)

The ship's porter and scrap collector. It runs on rubber-padded tracks and carries a front scoop, a scrap bin with a lid and a tow hook. Its face is a dark-glass screen, and two telescoping sensor stalks act as ears. It has no arms. Every planet it visits adds a souvenir sticker. Paint is worn deep teal, with orange reserved for warning accents and stickers. Settings live in `../tracker.json`.

## Build

Run it from the droid's work folder, which gets `out/`:

```
bash <kit>/droids/tracker/pipeline.sh
```

The pipeline runs these steps in order:

1. `build_tracker.py`: model and rig (`TrackerRig`, 60 bones). Tread links follow a path per side, driven by `track_L` / `track_R` in metres.
2. `tune_tr.py`: per-joint sweeps and rest contacts.
3. Kit passes: uv, weather, `polymer_map.py`, edges, wear, decals, `stickers.py`, softbevel.
4. `features.py`: screen modes, scanner beams, work lights and vent dust.
5. `tr_library.py`: the motion library, 26 motions and 8 poses baked from `tr_physics.py`, with every frame checked.
6. `add_ui.py`: puts the Tracker panel and Drive mode into the file as a text block. It also measures the scoop floor table, adds pose presets in kit format, wires the voice slot and sets the foley tags.
7. `drive_test_tr.py`: scripted Drive-mode run with every tick checked.
8. `tools/collision_check.py`: the kit's full collision test.

`random_tr.py` checks 1000 random mixed poses. `preview.py` renders quick stills (`ACTION=` and `FRAME=` pick a motion frame). `lock_prep.py` adds the look-dev studio before running `tools/lock_sheet.py`.

## Physics (`tr_physics.py`)

The same model bakes the library and runs Drive mode live, at 240 Hz:

The porter is dense and heavy for its size: 283 kg with a 0.30 m centre of gravity. The shells are 4 mm steel. Inside sit a 38 kg battery pack, two 12 kg drive motors with gearboxes, a 14 kg cast-iron counterweight, the scoop pump, the waist slewing drive and the electronics, all listed under `physics.internal` in `../tracker.json`. The motors are the same as before, so it now pulls away, stops and turns more slowly, and it settles longer on its struts.

- **Tracks.** Each track is a motor with speed lag. Acceleration is capped by motor torque and by traction (mu × g × that track's share of the weight), and braking is stronger. When the tracks counter-rotate, skid-steer scrub eats some of the turn.
- **Chassis.** It rides on four coil-over struts, with pitch, roll and heave as damped springs. It squats when accelerating, dives when braking, rolls out in turns and dips its nose when the scoop is loaded.
- **Body.** It sits on stiff but not rigid lean and sway motors, so it lags behind the chassis and then settles.
- **Stalk caps and tow hook.** The caps are springs and the hook is a pendulum, both driven by the real acceleration where they hang.
- **Servos.** All servos follow trapezoid speed profiles and slow down under load. Each frame's speeds are saved in every motion's `whirr` property for the servo sounds.

## Drive mode

Open it from N-panel > Tracker > Drive. It works with a DualSense or Xbox pad, or with the keyboard.

- The left stick drives the tracks.
- The right stick turns the waist and makes the droid look up or down.
- R2 and L2 lower and raise the scoop. R1 and L1 tilt it.
- To pick up scrap, lower the scoop and drive forward. That adds 4 kg and the droid gets heavier. Triangle tips the scrap into the bin.
- A load-cell end stop keeps the scoop teeth off the floor, even when the chassis dives.
- Each servo group gets a synthesized whirr whose pitch and volume follow its real speed.
- Create, or R on the keyboard, records a take into the motion library.

## Voice slot

Droid Voice (`blender-addons/droid_voice`) keys `dv_level` and `dv_accent` on the rig. The mouth opens with the level and the screen brightens on accents. The cast entry is stored on the rig as `voice_cast` (crush chain, Kokoro `am_puck`).

## Sounds

Each bone carries a `foley_mech` tag for ship_foley. The tread links and pins are tagged `none`, because the sprocket spinners carry the tread clatter.
