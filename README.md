# Doodle Companion (Bunny Pet for Windows)

Update channel for Bunny Pet. The app reads `app/manifest.json`, downloads only the files whose hashes changed, and restarts itself.

## Doodle Studio

`doodle-studio/` is the update channel for the Doodle Studio Windows app. Its window (`desktop/resources/app/updater.cjs`) checks `doodle-studio/manifest.json` 45 seconds after opening and every hour, downloads the changed files (gzip'd, named by SHA-256), swaps them in and offers a restart. Projects in AppData are never touched.

Every replaced file is kept in the hidden `.update/previous` folder (one version back), so an update can be rolled back on the PC; older versions stay in this repo's history. Builds installed by hand are no longer stamped with the published version: publish every build here so the app and the update channel never drift apart.

To publish a build: `node doodle-studio/publish.js "<build folder>" <version> "what changed"`, then commit and push to `main`. The bundled Electron runtime is not published; if a build needs a different runtime, the app asks for a full download instead.

## Doodle Studio 3D

`doodle-studio-3d/` is the update channel for Doodle Studio 3D, a separate Windows app (its own window, profile and local port 54190) that never touches the 2D app's MCP config, ports or Assistant switch. It checks `doodle-studio-3d/manifest.json` 45 seconds after opening and every hour, the same way the 2D app does, and keeps one version back in `.update/previous`.

The install folder (`Documents\DeepInDoodles\Doodle Studio 3D`) holds a copy of the 2D app's Electron runtime with `Doodle Studio Window.exe` renamed to `Doodle Studio 3D.exe`; only `resources/app/*` is published. To publish: `node doodle-studio-3d/publish.js <resources/app folder> <version> "notes" <runtime>`. The editor, host and tool sources are in `doodle-studio-3d/source/` (`node source/tools/package.cjs OUT` assembles resources/app; it needs `bunny3d.json` from `export_viewport.py` and the Blender rig from `Talking Character App\blender-bunny`).
