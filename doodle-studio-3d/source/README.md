# Doodle Studio 3D source

Everything needed to build and test the app from a fresh clone: the editor (`app/`), the
Electron host and Blender scripts (`host/`, including the Bunny, Koala and Frog .blend files
and the Doodle Library add-on snapshot), and the tests (`tools/`).

```
npm install            # three
npm install -g playwright electron   # or use the ones already on the machine
node tools/run_tests.cjs             # every suite this machine can run, one summary
node tools/run_tests.cjs --only=mcp_survival,package   # just these
```

Every pull request runs the same suites on GitHub (`.github/workflows/doodle-studio-3d-tests.yml`):
the MCP survival check (port 54190, `/mcp`, no tool removed or given a new required argument, the
update safety probe, clear errors for bad calls), the packaged file-path check, every suite over three
machines with bpy standing in for Blender, and a smoke test of the packaged app in the real Electron
runtime (including a killed editor page coming back). Suites that need the Doodle Library are skipped
there because the library is not in this repository; run them on the PC with `DSL_LIBRARY` set.
When a new MCP tool ships, add it to `tools/mcp_tools_baseline.json`.

The library tests need the Doodle Library folder: set `DSL_LIBRARY` to it (default `../lib`).

Blender tests (`test_render`, `test_scene`, `test_stage`, ...) call `tools/fakeblender.sh`,
which runs the Blender scripts with a Python that has `bpy` (`pip install bpy`). Point
`DS3D_BPY` at that Python. Test audio is in `tools/fixtures/` and is copied to `devout/`
on first use. Builds are published with `doodle-studio-3d/publish.js`, never hand-installed.
