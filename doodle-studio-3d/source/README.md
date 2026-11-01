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

Blender versions: `tools/test_blender5.py` runs the API spots that moved between Blender 4.5, 5.0
and 5.1 (layered actions, sequencer strips, video output, the compositor) in real bpy. Run it with
each version's Python, then the render suites (`test_render`, `test_scene`, `test_stage`,
`test_looks`) with `DS3D_BPY` pointed at each:

```
uv venv -p 3.11 /tmp/bpy45 && uv pip install -p /tmp/bpy45 "bpy==4.5.*"   # 5.0 also runs on 3.11
uv venv -p 3.13 /tmp/bpy51 && uv pip install -p /tmp/bpy51 "bpy==5.1.*"
/tmp/bpy51/bin/python -I tools/test_blender5.py          # ends with BLENDER5 PASS
```

A Linux box needs `libegl1` for bpy to start. The library tests also need `library.json`; build it
from the library's `index_parts` with the add-on's `index.merge_parts(<library folder>)`.

Headless bench for assistants: `node tools/bench.cjs [port]` (with `DS3D_BPY` and `DSL_LIBRARY`)
runs the real editor in headless Chromium with its MCP on `http://127.0.0.1:54250/mcp` and real
renders through the bpy stand-in, into `devout/bench/DeepInDoodles`. Use it to test the guide or a
skill from a fresh start without the PC.
