#!/bin/bash
set -e
# run from the droid work folder (writes out/):  bash <path>/pipeline.sh
S=$(cd "$(dirname "$0")" && pwd)
K=${DROID_KIT:-$(cd "$S/../.." && pwd)}; [ -d "$K/kit" ] || K=/home/user/doodlecompanion/blender-toolkit/droid-kit; export DROID=tracker DROID_OUT=out
python3 $S/build_tracker.py out/p1_build.blend | grep -E "saved|NON_SIMPLE"
python3 $S/tune_tr.py out/p1_build.blend out/p2_tune.blend | grep -E "^REST |REST_OTHER"
python3 $K/kit/uv.py out/p2_tune.blend out/p3_uv.blend | grep -o 'RB_paint": {[^}]*}'
python3 $K/kit/weather.py out/p3_uv.blend out/p4_w.blend | grep WEATHER
python3 $S/polymer_map.py out/p4_w.blend out/p4_w.blend | grep POLY
python3 $K/kit/edges.py out/p4_w.blend out/p5_e.blend | grep EDGES
python3 $K/kit/wear.py out/p5_e.blend out/p6_wear.blend | grep WEAR
python3 $K/kit/decals.py out/p6_wear.blend out/p7_dec.blend out/decals | grep -c "DECAL OK"
python3 $S/stickers.py out/p7_dec.blend out/p7s.blend out/stickers | grep -c "STICKER OK"
python3 $K/kit/softbevel.py out/p7s.blend out/p8_model.blend | grep SOFT
python3 $S/features.py out/p8_model.blend out/p8f.blend out/screen | grep FEATURES
echo MODEL_DONE
python3 $S/tr_library.py out/p8f.blend out/p9_lib.blend | grep -E "LIBRARY|clashes [1-9]"
python3 $S/add_ui.py out/p9_lib.blend out/p10_ui.blend | grep -E "UI added|POSE PRESETS"
python3 $S/drive_test_tr.py out/p10_ui.blend | grep DRIVETEST
python3 $K/tools/collision_check.py out/p10_ui.blend out/collision_report.json 2 | grep CHECK_SUMMARY
echo ALL_DONE
