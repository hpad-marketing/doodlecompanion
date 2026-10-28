# 360° prop library for Doodle Studio

`prop-library-360.js` is a Doodle Studio source module. It adds **Animate › Hold a 360° prop…** with the 89 props
the user approved on 2026-10-28 (`picks.json`). Each prop has 24 eye-level views drawn from its own 3D model. Clicking
one puts it in Bunny's hand at the playhead, keys the holding pose, and swaps views as Bunny turns.

Install on the PC from the Talking Character App folder:

```
python <this folder>/install_prop360.py .
python tools/build_candidate.py
```

The full library (models, all 168 views per prop), generator and review pages are in props-360-package.zip
(Talking Character App\props-360). Regenerate the module with `engine/make_module.py picks.json out.js` from that package.
