# Final fixes: one rebuild and install (fixes 21–26)

Run only after the user's typed approval line in the thread. Keep Doodle Studio closed during the install and don't control the screen.

- Source: `C:\Users\Sushant\Documents\Talking Character App` (currently matches installed build 20261028-134244, EXE cbaa1186)
- Installed app: `C:\Users\Sushant\Documents\DeepInDoodles\Doodle Studio`
- Files: `doodle-studio/stress-suite/` on branch `claude/project-thread-h4b3qj`

## Rules
- `.update\state.json` stays at `20261027-084419`.
- Keep rollbacks `.update\backup-20261027-ux-overhaul`, `backup-20261028-stress`, `backup-20261028-use-space`.
- Never touch anything under `Doodle Studio Exports\Backup`.
- Don't revert `tools\build_complete.py` or `src\prop-library-360.js`.
- Windows EXE only. No APK build or test.

## Steps
1. Back up `src\`, `windows\` and `tools\` to `backups\final-fixes-20261028-<time>\`.
2. Apply in this order (idempotent; on an anchor assert, stop and report):
   - `python fixes\patch_shelf_focus_pointer.py src` (21)
   - `python fixes\patch_fbf_fits_panel.py src` (22)
   - `python fixes\patch_settle_keeps_edits.py src` (23, needs the fix 6 /*settle-baseline*/ marker)
   - `python fixes\patch_hold_from_model.py src` (24)
   - `python fixes\patch_clip_redraw.py src` (25, editor.template.html)
   - `python fixes\patch_relaunch_reuses_host.py windows` (26, Bunny.cs)
3. Copy `guarded-checks\*.cjs` over `tools\` (includes qa-home-guard.cjs).
4. Rebuild the normal way (build_candidate.py, with the launcher compiled by tools\build_windows.ps1). The candidate HTML must contain `/*shelf-focus-pointer*/` (or that patch's marker), `/*fbf-fits-panel*/`, `/*settle-keeps-edits*/`, `/*hold-from-model*/`, `/*clip-redraw*/`; the compiled Bunny.cs must contain `/*relaunch-reuses-host*/`. The candidate folder needs `windows\.update\state.json` pinned to the installed version before any window opens.
5. Test the candidate into `qa\stress-final-5\`: engineer suite (goldens must match), every `tools\check_*.cjs` except android/phone ones, preview_equivalence vs 123318, windows_startup against the candidate EXE.
6. If everything passes: install over the app with a rollback `.update\backup-20261028-final-fixes`, state.json unchanged. Then rerun the golden frames and windows_startup against the installed app and report EXE + HTML sha.
