"""Shared helpers for the library builders (run inside Blender 4.5 / bpy 4.5)."""
import json
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # the add-on package lives next to build/

INK = (0.0137, 0.0137, 0.0122, 1)       # #1F1F1D linear
MUSTARD = (0.7454, 0.3813, 0.0685, 1)   # #E0A64B linear


def placeholder_materials():
    """Plain flat materials saved with library assets; the add-on swaps in the real ones."""
    out = {}
    for name, col in (('DSL_mustard', MUSTARD), ('DS_ink', INK)):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        o = nt.nodes.new('ShaderNodeOutputMaterial')
        e = nt.nodes.new('ShaderNodeEmission')
        e.inputs['Color'].default_value = col
        nt.links.new(e.outputs[0], o.inputs['Surface'])
        m.diffuse_color = col
        out[name] = m
    return out


def finish_mesh(me, merge=0.0004, sharp_deg=32.0):
    bm = bmesh.new()
    bm.from_mesh(me)
    if merge:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=sharp_deg * 3.14159 / 180)
    except Exception:
        pass
    from doodle_library import style
    style.compute_creases(me, sharp_deg)


def write_part(out, name, rows):
    os.makedirs(os.path.join(out, 'index_parts'), exist_ok=True)
    json.dump(rows, open(os.path.join(out, 'index_parts', name + '.json'), 'w'), indent=0)


def save_blend(path, objs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.data.libraries.write(path, set(objs), fake_user=True, compress=True)
