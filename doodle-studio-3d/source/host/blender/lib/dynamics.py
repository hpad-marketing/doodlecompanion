"""Spring (jiggle) bake for the ears and other soft parts.

Each spring bone's tail is a damped mass pulled toward where the animation
puts it. The lag is written back as a small rotation on the DEF bone, so the
ears follow through, overshoot and settle. Baked to keyframes, so renders
are repeatable and nothing needs Python at render time.
"""
import bpy
import compat
import math
from mathutils import Vector, Quaternion

DEFAULT_CHAINS = [
    # (bone, stiffness, damping, max angle deg)
    # ear roots are anchored in the skull: stiff, short travel. Tips are loose and swing further.
    ('DEF-ear.L', 170.0, 15.0, 7.0), ('DEF-ear_tip.L', 55.0, 5.5, 28.0),
    ('DEF-ear.R', 170.0, 15.0, 7.0), ('DEF-ear_tip.R', 55.0, 5.5, 28.0),
    # upper body carries a little weight: overlap on starts and stops
    ('chest', 150.0, 14.0, 3.0),
    ('DEF-tail', 85.0, 5.0, 22.0),
]


def bake_springs(arm, frame_start, frame_end, fps=30, chains=None, amount=1.0, substeps=6):
    if chains is None:
        chains = list(DEFAULT_CHAINS)
        over = arm.get('spring_overrides')  # species variants (JSON list of [bone, stiffness, damping, max_deg])
        if over:
            import json
            over = {c[0]: tuple(c) for c in json.loads(over)}
            chains = [over.get(c[0], c) for c in chains]
        chains = [c for c in chains if c[3] > 0]  # max angle 0 = no spring (Frog eye bumps)
        if 'DEF-tail' in arm.pose.bones and not bpy.data.objects.get('BUNNY_tail'):
            chains = [c for c in chains if c[0] != 'DEF-tail']
    sc = bpy.context.scene
    pb = arm.pose.bones
    mw = arm.matrix_world
    for name, *_ in chains:
        b = pb[name]
        b.rotation_mode = 'QUATERNION'
        b.rotation_quaternion = (1, 0, 0, 0)
        curves = compat.fcurves(arm)
        for fc in list(curves):
            if fc.data_path.startswith(f'pose.bones["{name}"]'):
                curves.remove(fc)
    state = {}
    dt = 1.0 / fps / substeps
    for f in range(frame_start, frame_end + 1):
        sc.frame_set(f)
        for name, k, c, max_deg in chains:
            b = pb[name]
            b.rotation_quaternion = (1, 0, 0, 0)
            bpy.context.view_layer.update()
            head = mw @ b.head
            tail = mw @ b.tail
            L = (tail - head).length
            if name not in state:
                state[name] = [tail.copy(), Vector((0, 0, 0))]
            p, v = state[name]
            for _ in range(substeps):
                a = (tail - p) * k - v * c
                v = v + a * dt
                p = p + v * dt
                d = p - head
                if d.length > 1e-9:
                    p = head + d.normalized() * L
            state[name] = [p, v]
            want = (tail - head).normalized()
            got = (p - head).normalized()
            q = want.rotation_difference(got)
            ang = q.angle
            lim = math.radians(max_deg)
            if ang > lim:
                q = Quaternion(q.axis, lim)
            q = Quaternion(q.axis, q.angle * amount) if q.angle > 1e-9 else Quaternion()
            W0 = (mw @ b.matrix).to_quaternion()
            local = W0.inverted() @ q @ W0
            b.rotation_quaternion = local
            b.keyframe_insert('rotation_quaternion', frame=f, group='Dynamics')
            bpy.context.view_layer.update()
