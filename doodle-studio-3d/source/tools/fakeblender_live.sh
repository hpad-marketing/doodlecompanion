#!/bin/bash
# Test stand-in for a Blender window: blender BLEND --python ds_bridge.py -- args
# runs live_harness.py with a Python that has bpy (DS3D_BPY). bpy has no event loop, so the
# harness ticks the live link itself and runs test commands dropped into OUT_DIR/cmd.json.
PY=${DS3D_BPY:-python3}
HERE="$(cd "$(dirname "$0")" && pwd)"
BLEND=$1; SCRIPT=$3; shift 4
cd /tmp && exec "$PY" -I "$HERE/live_harness.py" "$BLEND" "$SCRIPT" -- "$@"
