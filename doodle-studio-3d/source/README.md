# Doodle Studio 3D source

Everything needed to build and test the app from a fresh clone: the editor (`app/`), the
Electron host and Blender scripts (`host/`, including the Bunny, Koala and Frog .blend files
and the Doodle Library add-on snapshot), and the tests (`tools/`).

```
npm install            # three
npm install -g playwright electron   # or use the ones already on the machine
node tools/test_batch1.cjs           # ... test_batch12, test_library, test_update_safety
```

The library tests need the Doodle Library folder: set `DSL_LIBRARY` to it (default `../lib`).

Blender tests (`test_render`, `test_scene`, `test_stage`, ...) call `tools/fakeblender.sh`,
which runs the Blender scripts with a Python that has `bpy` (`pip install bpy`). Point
`DS3D_BPY` at that Python. Test audio is in `tools/fixtures/` and is copied to `devout/`
on first use. Builds are published with `doodle-studio-3d/publish.js`, never hand-installed.
