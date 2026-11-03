# Creator Toolkit (Blender add-on)

One add-on with all the everyday tools for design, animation and motion work. It runs on its own, with no Claude, no MCP and no credits needed. It works in Blender 4.2 to 5.2. The tools marked **5.2** need Blender 5.2 and show a short note in older versions.

## Install

1. In Blender, open Edit › Preferences › Get Extensions, then use the ▾ menu › Install from Disk.
2. Pick `creator_toolkit-1.0.0.zip`.
3. The tools appear in the **Toolkit** tab of the 3D View sidebar (N). With the Master Launcher installed, they also show up there as eight groups.
4. Updates: Toolkit › Setup › Updates checks this repository for a newer build and installs it.

## What's inside

| Group | Tools |
|---|---|
| Assets | Asset Vault (save, browse, **online Vault** 5.2), Clean Import, Doodle Library browser (sets, props, faces, motions as pictures) |
| Look | Master Material, Style Switcher, Palette Painter, Light rigs, **Raycast ink + radial backdrops** (5.2) |
| Rigging | Simple Rig Builder, Rig a Thing, Spring bones, Mocap + pose library |
| Animation | Motion presets, Tween + ease, **anim offset**, **silhouette view**, Playback helpers, Lip sync, **Stop-motion mode**, Ropes/cloth/hair (5.2), Speed lines from bones (5.2) |
| Motion design | Kinetic type, **Procedural text** (types itself, counter with commas, along a curve, wave, word pop), Camera moves + shake + pin to camera, Music visualizer + react to music (5.2) |
| Procedural & 2D | Geometry Nodes kit, Blobs/toon smoke/soft toys (5.2), Grease Pencil kit (fills, onion presets, boil), Node tidy |
| Output | Deliver + render queue (incl. HDR and wide colour on 5.x), **Bake for export**, **Captions + video looks** (5.2 looks), Starter templates, Turntable + portfolio |
| Setup | Heavy scene switch, Pie menu (Shift+Q) + Keydial sheet, Updates |

## Bake on Export

Live effects such as spring bones, camera shake, stop-motion stepping, jitter, light flicker and simulations are baked to plain keys and caches before an export, so the file gets exactly what you saw. **Unbake** puts the live setup back.

- The Master Launcher's Export button does this automatically through `DOODLE_MASTER['bake']`.
- You can also do it by hand from Output › Bake for export.

## Honest limits

- Toon smoke swirls with noise rather than a full fluid solve.
- Stop-motion mode steps keyframed animation, which covers characters, props, the camera and lights. Simulations and procedural Geometry Nodes still follow scene time and stay smooth.
- The online Vault needs a folder on a static web host that you choose.
- Several tools are our own take on the core idea of well-known free add-ons, not full copies of them.

## Tests

```
python3.13 -I tests/run.py   # bpy 5.2.3
python3.11 -I tests/run.py   # bpy 4.5.4
```
