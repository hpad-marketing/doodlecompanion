#!/bin/bash
# Blender 5.x stand-in for test_scene50: the same as fakeblender.sh, run with a Python that has
# bpy 5.x when DS3D_BPY50 is set (pip install 'bpy==5.*' on Python 3.13), otherwise DS3D_BPY.
export DS3D_BPY=${DS3D_BPY50:-${DS3D_BPY:-python3}}
exec "$(dirname "$0")/fakeblender.sh" "$@"
