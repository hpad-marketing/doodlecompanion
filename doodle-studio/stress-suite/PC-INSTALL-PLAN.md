# One combined rebuild and install (2026-10-28)

The user has closed Doodle Studio. Keep it closed until the install finishes, and don't control the screen.

- Source: `C:\Users\Sushant\Documents\Talking Character App`
- Installed app: `C:\Users\Sushant\Documents\DeepInDoodles\Doodle Studio`
- Files: this folder (`doodle-studio/stress-suite/` on branch `claude/project-thread-h4b3qj` of hpad-marketing/doodlecompanion)

## Rules from the other threads (must hold)

- `.update\state.json` stays at `20261027-084419`.
- Keep `.update\backup-20261027-ux-overhaul` as the rollback.
- Don't touch anything under `Doodle Studio Exports\Backup`.
- Don't revert or overwrite `src\prop-library-360.js` or `tools\build_complete.py`. The build list already includes `'prop-library-360'` before `'ux-overhaul'`.

## Steps

1. Back up `src\` and `tools\` to `backups\stress-20261028-<time>\`.

2. Apply each patch with `python fixes\<name>.py src`, in this order. Every script is idempotent: "already patched" is fine. If an anchor assert fails, stop and report the script name and the error. Don't hand-edit around it.
   1. patch_pointer_guards
   2. patch_draw_scrub_copy
   3. patch_depth_ray_reuse
   4. patch_depth_skip_hidden
   5. patch_library_preview_pause
   6. patch_close_guard_settle
   7. patch_action_pads_entry
   8. patch_draw_fits_1080
   9. patch_voice_takes_empty
   10. patch_detached_ux
   11. patch_loop_stop_visible
   12. patch_detached_narrow_boot
   13. patch_draw_prop_drag
   14. patch_gaze_respects_markers
   15. patch_cube_fits_short_canvas
   16. patch_draw_fits_1032
   17. patch_draw_layer_column
   18. patch_project_limits
   19. patch_audition_return_visible
   20. patch_queue_follows_format

   Some scripts patch a single src file and others patch `ux-overhaul.css`. Each one finds its own file when given the src folder.

3. Apply the motion-library add-ons (the user approved all of them), in this order, to the src lib folder (motion-templates.json, motion-face-profiles.json, motion-props.json):
   1. addons\delta-chinup.json.xz with tools\motion-install\apply_moves_only.py (decompress first). Check: "chin-up-proud" appears exactly once.
   2. addons\delta-set8.json.xz the same way. Check: motion-templates.json gains the 40 ids listed in addons\approved8.txt.
   3. Last: `python addons\patch_eye_size.py <lib folder>`. Check: no "00 Neutral" left in motion-face-profiles.json, and a before-and-after face render shows the same eye size.

4. Copy `updated-checks\*.cjs` over `tools\` (these are the old checks updated for the UX pass). Copy `engineer-suite.cjs` to `tools\stress\`.

5. Rebuild with `tools\build_candidate.py`, the normal way. The candidate `index.studio.html` must contain:
   - `DoodlePropLibrary360`
   - `/*settle-baseline*/`
   - `/*loop-stop-visible*/`
   - `/*draw-prop-drag*/`

6. Test the candidate. Write everything to `qa\stress-final-2\`:
   - `node tools\stress\engineer-suite.cjs <candidate html>` (full run). Golden frames must match, because Bunny's rendering must not change. On the real GPU, use `PERF_ABS=1`.
   - Every `tools\check_*.cjs` except the `*_android*` and `*phone*` ones. They now run on the desktop by default; phone sections only run with `QA_PHONE=1`, which we don't use (the APK is retired).
   - The two add-on checks: Animate › "Hold a 360° prop…" opens with 89 cards and no JS errors, and `chin-up-proud` is in the motion library.
   - Write `SUMMARY.md` (pass/fail per check, with the first error of each failure) and `REPORT.json`.

7. Install only if there are no real failures:
   - Use the usual activate route.
   - Back up the current install to `.update\backup-20261028-stress` first.
   - Follow the rules above.
   - If something fails, don't install. Report it.

8. If `ui-port.txt` in the app data folder isn't 54183, mention it in the report.
