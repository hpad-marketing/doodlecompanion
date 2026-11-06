#!/bin/bash
# Test stand-in for blender.exe: blender -b [BLEND|--factory-startup] --python SCRIPT -- args
# runs SCRIPT with a Python that has the bpy module (pip install bpy). Set DS3D_BPY to it.
PY=${DS3D_BPY:-python3}
if [ "$2" = "--factory-startup" ]; then SCRIPT=$4; shift 4; cd /tmp && exec "$PY" -I "$SCRIPT" "$@"; fi
BLEND=$2; SCRIPT=$4; shift 5
cd /tmp && exec "$PY" -I "$SCRIPT" -- "$BLEND" "$@"
