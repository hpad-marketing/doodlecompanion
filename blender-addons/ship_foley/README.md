# Ship Foley

Contact sounds for the droid sitcom. Every time a droid or a prop touches something, you hear it: steps on the deck, fingers closing on a toolbox, a crate landing, a mug set down, a crate dragged across the floor.

## How the sound follows the action

| What changes | What you hear | Why |
|---|---|---|
| Faster, harder contact | Louder and brighter | Loudness follows the energy of the hit (½·m·v²). A fast strike is short, so it excites the high ring. |
| Slow, careful pickup | A soft, dull clink | Low energy and a long, gentle strike. |
| Heavier droid | Louder and deeper, with a deck thud | More mass behind the foot. The deck flexes lower and longer. |
| Bigger object | Lower ring | Modal pitch falls with size. |
| Hollow object (crate, can, locker) | Longer, boomier ring | Thin shells ring longer and lower. |
| Material | Metal rings, polymer knocks, rubber thumps, rug muffles | Each material has its own ring time, stiffness and grit. |
| Heavy droid lands | Deep thud and frame boom, loose armour rattling, a hydraulic hiss and creak as the leg takes the weight | Weight has to go somewhere |
| Joints turning | Motor whir and whine that rise in pitch with turning speed, gear buzz, grind under load, hiss on fast starts and stops, a clunk when a joint stops dead | Each part-carrying bone is a motor. Heavy droids have low, slow motors and the drone has thin, quick servos |

Weights (editable per droid in the panel): RX-07 240 kg, hazard droid 85 kg, hover drone 9 kg, ship's computer 400 kg (fixed mount).

## Sources and licence

All sounds come from physics in code (`synth.py`, numpy only): modal synthesis, Hertz contact and a small steel-room tail. No recordings or sample packs are used, so nothing needs clearing for commercial use.

## Use

*N panel › Foley* in the 3D View or the Sequencer:

- **Bake contact sounds** scans the frame range and puts "FX" sound strips on VSE channels 24–27 (feet, hands, props, scrapes). Each strip is panned to where the contact sits in the camera frame and turned down with distance.
- **Clear** removes only the FX strips.
- **Mixdown** writes the shot's audio to `<blend>_foley.wav`.
- With a droid's armature selected, you can pick its profile, set its weight, and hear a soft step, a walk and a stomp.

**Walk mode.** When Ship Builder is enabled, each foot plant plays its step live through `ship_builder.feet.ON_PLANT`.

**Hold / Release.** The droid kit's keys on `["hold_L"]` / `["hold_R"]` set the grab and release moments. While a prop is held, fingertip contact stays quiet. For props parented by hand, fingertip contact is the fallback.

**Surface tags.** Ship Builder can stamp `sb_surface` (deck, grate, metal, metal_thin, polymer, rubber, fabric, glass, ceramic, wood, stone) and `foley_hollow` (0–1). Without tags, the material comes from the material name.

Scripting:

```python
import ship_foley
events, strips, json_path = ship_foley.bake_scene(bpy.context.scene)
ship_foley.live.contact(armature, "foot.L", speed=0.5, surface=floor)
```

Objects tagged `foley_ignore` are skipped, and so are VFX meshes (dust, smoke, sparks, haze).

## Tests

```
python ship_foley/tests/test_rules.py                       # physics rules, no Blender
python ship_foley/tests/scan_blend.py -- droid.blend RM_walk_loop out/
python ship_foley/tests/grab_scene.py -- droid.blend RM_grab_lift out/ hold
```

The last two run with `pip install bpy==5.2.3` or with `blender -b --python`.
