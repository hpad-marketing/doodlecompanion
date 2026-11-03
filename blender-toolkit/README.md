# Creator Toolkit (Blender add-on)

One add-on with all the everyday tools for design, animation and motion work. It runs on its own, with no Claude, no MCP and no credits needed. It works in Blender 4.2 to 5.2. The tools marked **5.2** need Blender 5.2 and show a short note in older versions.

## Install

1. In Blender, open Edit › Preferences › Get Extensions, then use the ▾ menu › Install from Disk.
2. Pick `creator_toolkit-1.1.0.zip`.
3. The tools appear in the **Toolkit** tab of the 3D View sidebar (N). With the Master Launcher installed, they also show up there as eight groups. The Doodle Library gets its own **Doodle** tab.
4. Updates: Toolkit › Setup › Updates checks this repository for a newer build and installs it.

## What's inside

| Group | Tools |
|---|---|
| Assets | Asset Vault (save, browse, **online Vault** 5.2), Clean Import, Doodle Library browser (sets, props, faces, motions as pictures) |
| Look | Master Material, Style Switcher, Palette Painter, Light rigs, **Raycast ink + radial backdrops** (5.2) |
| Rigging | Simple Rig Builder, Rig a Thing, Spring bones, Mocap + pose library |
| Animation | Motion presets, Tween + ease, **anim offset**, **silhouette view**, Playback helpers, Lip sync, **Stop-motion mode** (now steps procedural animation and boils models too), Ropes/cloth/hair (5.2), Speed lines from bones (5.2) |
| Motion design | Kinetic type, **Word cloud**, **Procedural text** (types itself, counter with commas, along a curve, wave, word pop), Camera moves + shake + pin to camera, Music visualizer + react to music (5.2) |
| Procedural & 2D | Geometry Nodes kit, Blobs/toon smoke/soft toys (5.2), Grease Pencil kit (fills, onion presets, boil), **Boil + hold for 3D models**, **Doodle powers** (auto-ink, jelly, crowd, scatter, toon liquids, fisheye, 360 video), Node tidy |
| Output | Deliver + render queue (incl. HDR and wide colour on 5.x), **Bake for export**, **Captions + video looks** (5.2 looks), Starter templates, Turntable + portfolio |
| Setup | Heavy scene switch, Pie menu (Shift+Q) + Keydial sheet, Updates |

## Doodle tab (from Doodle Studio 3D)

The whole Doodle Library add-on now comes inside the Toolkit:
- library browser for motions, faces, mouths, outfits, props, scenery and cards
- sets with declutter and parallax moves
- weather and party effects
- time of day, sky and lightning
- storytime: chats, labels, journey maps, time skip, horror and end screen
- placement, grips and collision guard
- 3D text and auto-save to the library

It reads the library folder set in Preferences (default `Documents/Talking Character App/blender-library`). If the standalone Doodle Library add-on is switched on, that one stays in charge and the Toolkit's copy stays quiet. Bunny's own helper code ships inside the Toolkit, so effects and storytime work in any file. Motions and faces still need Bunny3D.blend open.

## Bake on Export

Live effects such as spring bones, camera shake, stop-motion stepping, jitter, light flicker and simulations are baked to plain keys and caches before an export, so the file gets exactly what you saw. **Unbake** puts the live setup back.

- The Master Launcher's Export button does this automatically through `DOODLE_MASTER['bake']`.
- You can also do it by hand from Output › Bake for export.

## Honest limits

- Toon smoke swirls with noise rather than a full fluid solve.
- Stop-motion mode holds procedural animation and simulations with a small simulation-zone modifier, so play from the first frame once (or bake) before scrubbing.
- The online Vault needs a folder on a static web host that you choose.
- Several tools are our own take on the core idea of well-known free add-ons, not full copies of them.

## Tests

```
python3.13 -I tests/run.py   # bpy 5.2.3
python3.11 -I tests/run.py   # bpy 4.5.4
```
