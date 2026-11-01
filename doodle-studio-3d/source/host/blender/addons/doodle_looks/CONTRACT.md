# Look add-on contract (Doodle Studio 3D › Materials)

Any Blender add-on can show up in Doodle Studio 3D's Materials tab, ClayDoh included. It needs
two things next to its `__init__.py`: a `doodle_look.json` manifest and a `material()` function.
Everything else in the add-on (panels, operators, its own UI in Blender) keeps working as usual.

## 1. The manifest: `doodle_look.json`

```json
{
  "contract": 1,
  "name": "ClayDoh",
  "module": "claydoh",
  "material": "material",
  "looks": [
    {
      "id": "clay-soft",
      "name": "Soft clay",
      "about": "Matte modelling clay with thumb dents",
      "flat": false,
      "preview": "previews/clay-soft.png",
      "params": [
        { "id": "roughness", "label": "Roughness", "type": "float", "min": 0, "max": 1, "default": 0.7 },
        { "id": "dents",     "label": "Dents",     "type": "float", "min": 0, "max": 1, "default": 0.4 },
        { "id": "grain",     "label": "Grain",     "type": "bool",  "default": true },
        { "id": "rim",       "label": "Rim colour","type": "color", "default": "#E0A64B" }
      ]
    }
  ]
}
```

| key | meaning |
|---|---|
| `contract` | always `1` for now |
| `name` | what the tab shows as the add-on's name |
| `module` | the Python package name. **Must equal the folder name**, because that's what Blender imports |
| `material` | the name of the function to call (default `material`) |
| `looks[].id` | stable id, saved in projects. Don't rename it once shipped |
| `looks[].flat` | `true` = unlit flat repaint (the studio paints it itself and never calls you) |
| `looks[].fur` | `true` = the studio grows short fur strands on characters wearing this look, kept clear of the face. The params `furLength` (cm), `furDensity` (0..1) and `furTilt` (0..1) steer it when present |
| `looks[].preview` | optional picture for the look card (png/jpg/webp, under 1.5 MB; 200×300 looks best). With no picture, the card shows the test frame instead |
| `params[].type` | `float`, `int`, `bool` or `color` (`"#RRGGBB"`). Each one becomes a slider, a switch or a swatch in the tab |

## 2. The function

```python
def material(look_id: str, rgb: tuple, params: dict) -> bpy.types.Material:
    ...
```

- `rgb` is the **linear** 0..1 `(r, g, b)` colour the palette wants on this surface (one call for
  Bunny, one for the walls, one for the floor, and so on).
- `params` holds the slider values keyed by `params[].id`. A key can be missing, so fill it in
  from your defaults.
- Return a `bpy.types.Material`. Cache it, because the same look and colour is asked for many times.
  The built-in add-on keys the cache on a hash of `(look, rgb, params)`.
- Build the material with nodes only. Don't add lights, change the world or touch objects;
  the studio owns the lighting rig, the ink outline and the faces.
- Never raise for a normal input. A raise marks the look as **failed** in the tab and the
  shot falls back to Ink & Mustard for that target.

`register()` and `unregister()` can stay as they are, because the studio imports the package
and calls `material()` directly, without enabling the add-on.

The reference implementation is `doodle_looks/__init__.py`, which contains clay, cel, vinyl,
felt, paper and ceramic.

## 3. Where to put it

Doodle Studio 3D looks in, in this order (first match wins for a module name):

1. the built-in folder, `blender/addons/` inside the app
2. `<Doodle Library>\looks\`: drop the add-on folder **or its .zip** here (a zip is unpacked once)
3. Blender's own add-on folders on the PC:
   `%APPDATA%\Blender Foundation\Blender\<ver>\scripts\addons\` and `...\extensions\<repo>\`,
   so an add-on you installed in Blender shows up by itself

Press **Look again for add-ons** in the Materials tab after adding one.

## 4. The test frame

An add-on that isn't built in gets one test render before its looks can be picked. Bunny is
rendered close up, 400×600, wearing the look. If Blender errors, renders nothing or the look
changes nothing, the card shows **Failed** with the error, and you can retry. A pass is
remembered (in `<app data>\looks\status.json`) and its frame becomes the card's picture if the
manifest has none.

## 5. What the studio keeps for itself

- The body outline (the DS Ink / DSL Ink hull and lines) is off for textured looks unless the
  user switches it on. Face lines always stay. Fill slots get your material, and slots that are
  already near-black ink stay ink.
- Faces (eyes, mouth) are never repainted.
- Lights: one soft key sun and one fill. Cast shadows are off unless the shot turns them on.
- A look only changes what Blender renders. The live 3D view keeps the ink style, so editing
  stays fast.
