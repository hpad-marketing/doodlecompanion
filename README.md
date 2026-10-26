# Doodle Companion (Bunny Pet for Windows)

Update channel for Bunny Pet. The app reads `app/manifest.json`, downloads only the files whose hashes changed, and restarts itself.

## Doodle Studio

`doodle-studio/` is the update channel for the Doodle Studio Windows app. Its window (`desktop/resources/app/updater.cjs`) checks `doodle-studio/manifest.json` 45 seconds after opening and every 3 hours, downloads the changed files (gzip'd, named by SHA-256), swaps them in and offers a restart. Projects in AppData are never touched.

To publish a build: `node doodle-studio/publish.js "<build folder>" <version> "what changed"`, then commit and push to `main`. The bundled Electron runtime is not published; if a build needs a different runtime, the app asks for a full download instead.
