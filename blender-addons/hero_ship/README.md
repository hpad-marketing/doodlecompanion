# Hero Ship

Exterior hero ship for the droid spaceship sitcom, with flight presets. Plain Python
package (no UI); the sitcom add-on imports it and shows it in its preview pane.

```python
import hero_ship
root = hero_ship.build()                     # root empty is named "Hero Ship"
hero_ship.presets.apply(root, "planet_landing", frame_start=1)   # also builds the backdrop
```

## The ship
About 47 m long, built like a working freighter: rounded, panelled blocks (cab, fore
body, aft body, engine block) with an open spine between fore and aft where the keel,
tanks, pipes and cables show. Every panel seam is real geometry. Weathering is
procedural (chipped edges, cavity grime, grime and rust streaks, exhaust soot, dust,
replaced primer panels, per-panel tone drift), so no image files are needed.
UVs: hull blocks are unwrapped by arc length x length (no stretch, one texel density:
1 UV unit = 4 m); every other part uses world-scale box projection at the same density.

## Moving parts (custom properties on the root)
| property | what moves |
|---|---|
| `gear` 0..1 | gear doors open (0-0.35), struts swing down from their bays (0.25-0.95) |
| `gear_compress` m | shock struts slide up; presets dip the body by the same amount so feet stay planted |
| `ramp` 0..1 | belly ramp lowers until its lip meets the ground (lit cargo bay behind it) |
| `nacelle_tilt` 0..1 | engine pods rotate on their collars from cruise to exhaust-down hover |
| `radiators` 0..1 | spine radiator panels fold flat over the tanks or stand up |
| `dish_rpm`, `scan_deg` | comms dish spin, chin scanner yaw |
| `engine`, `hyper`, `lights` | engine glow and plume length, hyperdrive charge glow, nav lights/beacons |

## Presets
`idle_drift`, `cruise`, `hyperdrive_jump`, `planet_landing` (see `presets.PRESETS`).
Backdrops: `stage.build("space")` and `stage.build("planet")` (landing pad top at z = 0).

## Checks
- `tests/build_test.py -- /tmp/hs "" --audit` sweeps every moving part through its range
  and runs the ship_builder collision audit (`tests/sb_collide.py`, copied from
  `ship_builder/collide.py`). Must report `AUDIT TOTAL 0`.
- `tests/preset_test.py -- /tmp/hp` applies every preset and audits sampled frames,
  plus a ground check (nothing below the pad, feet planted through touchdown).
- `tests/sushi_render.py` is the GPU job for Sushi: .blend files, stills, thumbnails,
  preview MP4s and `previews/hero_ship/manifest.json`.
