"""Hoodie behaviour that isn't cloth: sleeves bunch into creases as the arms rise
or the elbows bend, and the open hem has a winter-hoodie thickness."""
import math
import bpy
from mathutils import Vector


def _drive_key(key, arm, bone_a, bone_b, lo, hi):
    """Key value 0..1 as the angle between two bones goes from lo to hi (radians)."""
    fc = key.driver_add('value')
    d = fc.driver
    d.type = 'SCRIPTED'
    v = d.variables.new()
    v.name = 'a'
    v.type = 'ROTATION_DIFF'
    v.targets[0].id = arm
    v.targets[0].bone_target = bone_a
    v.targets[1].id = arm
    v.targets[1].bone_target = bone_b
    d.expression = f'min(1, max(0, (a - {lo:.4f}) / {hi - lo:.4f}))'


def sleeve_bunch(ob, arm, bone, toward_head=True, squash=0.16, bulge=0.09, ridges=3):
    """Shape key: the sleeve slides up the arm and gathers into soft ridges."""
    b = arm.data.bones[bone]
    h, t = arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local
    ax = (t - h).normalized()
    L = (t - h).length
    mwi = ob.matrix_world.inverted()
    if not ob.data.shape_keys:
        ob.shape_key_add(name='Basis')
    key = ob.shape_key_add(name='Bunch')
    for v, kv in zip(ob.data.vertices, key.data):
        w = ob.matrix_world @ v.co
        rel = w - h
        s = max(0.0, min(1.0, rel.dot(ax) / L))
        radial = rel - ax * rel.dot(ax)
        # gather toward the anchored end, with ridges that fade out at the cuff
        along = -ax * L * squash * (s if toward_head else (s - 1))
        ridge = 0.5 + 0.5 * math.cos(2 * math.pi * ridges * s)
        out = radial * (bulge * (0.4 + 0.6 * ridge))
        kv.co = mwi @ (w + along + out)
    return key


def setup(objs, arm, S):
    for side in 'LR':
        k = sleeve_bunch(objs[f'sleeve_up.{side}'], arm, f'DEF-upper_arm.{side}')
        _drive_key(k, arm, f'DEF-upper_arm.{side}', f'MCH-arm_rest.{side}', math.radians(30), math.radians(130))
        k = sleeve_bunch(objs[f'sleeve_fore.{side}'], arm, f'DEF-forearm.{side}', toward_head=True, squash=0.12, bulge=0.07)
        _drive_key(k, arm, f'DEF-forearm.{side}', f'DEF-upper_arm.{side}', math.radians(35), math.radians(130))
    # winter-weight fabric: the open hem shows a real edge thickness
    sh = objs['shirt']
    so = sh.modifiers.new('Fabric thickness', 'SOLIDIFY')
    so.thickness = 0.022 * S * 8
    so.offset = -1.0
    so.use_rim = True
    so.use_even_offset = False   # 'even' thickness spikes wherever the hem folds over a raised knee
    so.thickness_clamp = 1.0     # never thicker than the local edge length
    order = [m.name for m in sh.modifiers]
    target = order.index('Subdivision') if 'Subdivision' in order else len(order) - 1
    while sh.modifiers.find(so.name) > target:
        bpy.context.view_layer.objects.active = sh
        bpy.ops.object.modifier_move_up(modifier=so.name)
