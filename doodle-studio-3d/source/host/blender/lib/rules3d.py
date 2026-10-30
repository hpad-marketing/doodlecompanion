"""Per-frame rule checks on the real 3D geometry (ANIMATION-RULES.md, 3D edition).

1. Hands and arms never clip into the head  (mesh-vs-mesh, not joint points)
2. Grounding: lowest foot point sits on the floor (or above it, never below)
3. Ears never touch/merge with each other
Stroke weight is one ink width for every Bunny part by construction.
Uses the same cage meshes as the collision solver, so a solved pose passes.
"""
import bpy
import bmesh
import collision


def _zmin(ob):
    """Lowest point of the body surface itself. The ink outline shell is left out:
    its size follows the camera (screen-constant ink), so it can't define the floor."""
    ink = [m for m in ob.modifiers if m.type == 'NODES' and m.show_viewport]
    for m in ink:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    z = min(((ob.matrix_world @ v.co).z for v in me.vertices), default=0.0)
    ev.to_mesh_clear()
    for m in ink:
        m.show_viewport = True
    return z


def check_frame(objs, arm, ear_sets=None, tol=0.0015):
    out = {}
    hb = collision._cage_bvh(objs['head'])
    clips = []
    for side in 'LR':
        for part in collision.ARM_PARTS:
            ob = objs.get(f'{part}.{side}')
            if ob and hb.overlap(collision._cage_bvh(ob)):
                clips.append(f'{part}.{side}')
    out['arm_head_clip'] = clips
    root_z = (arm.matrix_world @ arm.pose.bones['root'].head).z + arm.get('floor_z', 0.0)
    lows = [_zmin(objs[f'leg.{s}']) - root_z for s in 'LR']
    out['foot_low'] = [round(z, 4) for z in lows]
    out['grounded'] = -tol < min(lows) < 0.02
    out['below_floor'] = min(lows) < -tol
    if arm.get('ear_width_lock'):
        # Frog: the 'ears' are rigid eye bumps that sit ~1 mm apart by design and never move apart or fold
        out['ears_touch'] = False
        out['ears_touch_note'] = 'rigid eye bumps (ear_width_lock): not checked'
        return out
    if ear_sets is None:
        ear_sets = collision.ear_vertex_sets(objs['head'])
    out['ears_touch'] = collision.ears_touch(objs['head'], ear_sets)
    return out
