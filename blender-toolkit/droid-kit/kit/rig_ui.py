"""Robot rig panel: N-panel > Robot. IK/FK switches, snapping, layer toggles, reset pose."""
import bpy, math

RIG = 'RobotRig'
LIMBS = {
    'Arm': dict(sw='IK_hand', fk=['FK-upper_arm', 'FK-forearm', 'FK-hand'], deff=['DEF-upper_arm', 'DEF-forearm', 'DEF-hand'],
                ik='IK_hand', pole='pole_elbow', mid='DEF-forearm'),
    'Leg': dict(sw='IK_foot', fk=['FK-thigh', 'FK-shin', 'FK-foot', 'FK-toe'], deff=['DEF-thigh', 'DEF-shin', 'DEF-foot', 'DEF-toe'],
                ik='IK_foot', pole='pole_knee', mid='DEF-shin'),
}


def rig(ctx):
    ob = ctx.active_object
    return ob if ob and ob.type == 'ARMATURE' and 'rig_spec' in ob else bpy.data.objects.get(RIG)


class ROBOT_OT_snap(bpy.types.Operator):
    """Match one mode to the other so switching does not pop"""
    bl_idname = 'robot.snap'; bl_label = 'Snap'; bl_options = {'REGISTER', 'UNDO'}
    limb: bpy.props.StringProperty(); side: bpy.props.StringProperty(); to: bpy.props.StringProperty()

    def execute(self, ctx):
        ob = rig(ctx); pb = ob.pose.bones; L = LIMBS[self.limb]; S = self.side
        ctx.view_layer.update()
        if self.to == 'FK':
            mats = [pb[f'{d}.{S}'].matrix.copy() for d in L['deff']]
            for f, m in zip(L['fk'], mats):
                pb[f'{f}.{S}'].matrix = m; ctx.view_layer.update()
            pb[f'{L["sw"]}.{S}']['ik_fk'] = 0.0
        else:
            if self.limb == 'Arm':
                pb[f'{L["ik"]}.{S}'].matrix = pb[f'DEF-hand.{S}'].matrix.copy()
            else:
                ctrl = pb[f'{L["ik"]}.{S}']
                foot = pb[f'DEF-foot.{S}']; rest_c = ob.data.bones[ctrl.name].matrix_local
                rest_f = ob.data.bones[foot.name].matrix_local
                ctrl.matrix = foot.matrix @ rest_f.inverted() @ rest_c
                for r in ('roll_heel', 'roll_toe', 'roll_ball'):
                    pb[f'{r}.{S}'].rotation_euler = (0, 0, 0)
            ctx.view_layer.update()
            mid = pb[f'{L["mid"]}.{S}']
            pole = pb[f'{L["pole"]}.{S}']
            m = pole.matrix.copy(); m.translation = mid.head + (mid.head - (pb[f'{L["deff"][0]}.{S}'].head + mid.tail) / 2).normalized() * 0.8
            pole.matrix = m
            pb[f'{L["sw"]}.{S}']['ik_fk'] = 1.0
        ob.update_tag(); return {'FINISHED'}


class ROBOT_OT_reset(bpy.types.Operator):
    """Clear the pose of every control"""
    bl_idname = 'robot.reset'; bl_label = 'Reset pose'; bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        for p in rig(ctx).pose.bones:
            p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0); p.scale = (1, 1, 1)
        return {'FINISHED'}



def find_contacts(ob, ctx):
    """Parts that intersect in the current pose, ignoring the designed joint contacts."""
    import json
    from mathutils.bvhtree import BVHTree
    skip = {tuple(p) for p in json.loads(ob.get('rest_contacts', '[]'))}
    dg = ctx.evaluated_depsgraph_get()
    parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and o.parent == ob]
    data = []
    for o in parts:
        M = o.evaluated_get(dg).matrix_world
        vs = [M @ v.co for v in o.data.vertices]
        mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
        data.append((o, vs, mn, mx))
    hits = []; trees = {}
    for i, (a, va, amn, amx) in enumerate(data):
        for b, vb, bmn, bmx in data[i + 1:]:
            if a['rig_bone'] == b['rig_bone'] or (a.name, b.name) in skip or (b.name, a.name) in skip:
                continue
            if any(amx[k] < bmn[k] or bmx[k] < amn[k] for k in range(3)):
                continue
            ta = trees.setdefault(a.name, BVHTree.FromPolygons(va, [tuple(p.vertices) for p in a.data.polygons]))
            tb = trees.setdefault(b.name, BVHTree.FromPolygons(vb, [tuple(p.vertices) for p in b.data.polygons]))
            if ta.overlap(tb):
                hits.append((a.name, b.name))
    return hits


class ROBOT_OT_check(bpy.types.Operator):
    """Report any parts passing through each other in this pose (or across the frame range)"""
    bl_idname = 'robot.check'; bl_label = 'Check collisions'
    all_frames: bpy.props.BoolProperty(default=False)

    def execute(self, ctx):
        ob = rig(ctx); sc = ctx.scene; found = {}
        frames = range(sc.frame_start, sc.frame_end + 1) if self.all_frames else [sc.frame_current]
        cur = sc.frame_current
        for f in frames:
            if self.all_frames: sc.frame_set(f)
            for h in find_contacts(ob, ctx):
                found.setdefault(h, f)
        if self.all_frames: sc.frame_set(cur)
        for o in bpy.data.objects:
            if 'rig_bone' in o: o.select_set(False)
        if not found:
            self.report({'INFO'}, 'Clean: no parts pass through each other'); return {'FINISHED'}
        for (a, b), f in found.items():
            bpy.data.objects[a].select_set(True); bpy.data.objects[b].select_set(True)
        msg = '; '.join(f'{a} x {b} (frame {f})' for (a, b), f in list(found.items())[:6])
        self.report({'WARNING'}, f'{len(found)} clash(es), parts selected: {msg}')
        return {'FINISHED'}


# ------------------------------------------------------------------ springs (secondary motion)
import json
from mathutils import Vector, Quaternion
_STATE = {}

def spring_step(scene, depsgraph=None):
    ob = bpy.data.objects.get(RIG)
    if not ob or not ob.get('springs_on', 1) or 'springs' not in ob: return
    f = scene.frame_current
    if _STATE.get('frame') == f and not _STATE.get('force'): return
    _STATE['force'] = False
    reset = _STATE.get('frame') is None or f != _STATE['frame'] + 1 or f <= scene.frame_start
    for ch in json.loads(ob['springs']):
        for bn, tn in zip(ch['bones'], ch['targets']):
            pb, tb = ob.pose.bones[bn], ob.pose.bones[tn]
            bone = ob.data.bones[bn]; par = pb.parent
            rest_rel = ob.data.bones[par.name].matrix_local.inverted() @ bone.matrix_local
            M = par.matrix @ rest_rel
            head = M.translation.copy(); tail = M @ Vector((0, bone.length, 0))
            if reset or bn not in _STATE: _STATE[bn] = [tail.copy(), Vector()]
            p, v = _STATE[bn]
            v = v + (tail - p) * ch['k'] - v * ch['damp'] + Vector((0, 0, -ch['grav']))
            p = p + v
            rd, d = tail - head, p - head
            if d.length > 1e-6:
                ang = rd.angle(d)
                lim = math.radians(ch['max_deg'])
                if ang > lim:
                    q = rd.rotation_difference(d)
                    d = Quaternion(q.axis, lim) @ rd
                p = head + d.normalized() * rd.length
            _STATE[bn] = [p, v]
            m = tb.matrix.copy(); m.translation = p; tb.matrix = m
            bpy.context.view_layer.update()
    _STATE['frame'] = f


class ROBOT_OT_bake_springs(bpy.types.Operator):
    """Run the springs over the frame range and keyframe them, so renders are identical every time"""
    bl_idname = 'robot.bake_springs'; bl_label = 'Bake springs'; bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        ob = rig(ctx); sc = ctx.scene; _STATE.clear()
        tg = [t for ch in json.loads(ob['springs']) for t in ch['targets']]
        for f in range(sc.frame_start, sc.frame_end + 1):
            sc.frame_set(f); spring_step(sc)
            for t in tg: ob.pose.bones[t].keyframe_insert('location', frame=f, group='springs')
        ob['springs_on'] = 0
        self.report({'INFO'}, 'Springs baked to keys; live springs switched off'); return {'FINISHED'}


class ROBOT_OT_clear_springs(bpy.types.Operator):
    """Remove baked spring keys and switch live springs back on"""
    bl_idname = 'robot.clear_springs'; bl_label = 'Clear bake'; bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        ob = rig(ctx); sc = ctx.scene
        tg = [t for ch in json.loads(ob['springs']) for t in ch['targets']]
        for t in tg:
            for f in range(sc.frame_start, sc.frame_end + 1):
                try: ob.keyframe_delete(f'pose.bones["{t}"].location', frame=f)
                except RuntimeError: pass
        for t in tg: ob.pose.bones[t].location = (0, 0, 0)
        ob['springs_on'] = 1; _STATE.clear(); return {'FINISHED'}


class ROBOT_PT_panel(bpy.types.Panel):
    bl_label = 'Robot Rig'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Robot'

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        ob = rig(ctx); pb = ob.pose.bones; lay = self.layout
        for limb, L in LIMBS.items():
            box = lay.box(); box.label(text=f'{limb}s  (0 = FK, 1 = IK)')
            row = box.row()
            for S in ('R', 'L'):
                col = row.column(align=True)
                col.prop(pb[f'{L["sw"]}.{S}'], '["ik_fk"]', text=f'{limb} {S}', slider=True)
                r = col.row(align=True)
                o = r.operator('robot.snap', text='to FK'); o.limb, o.side, o.to = limb, S, 'FK'
                o = r.operator('robot.snap', text='to IK'); o.limb, o.side, o.to = limb, S, 'IK'
        box = lay.box(); box.label(text='Controls')
        grid = box.grid_flow(columns=2, align=True)
        for c in ob.data.collections:
            grid.prop(c, 'is_visible', text=c.name, toggle=True)
        row = lay.row(align=True)
        row.operator('robot.check', icon='MOD_PHYSICS').all_frames = False
        row.operator('robot.check', text='Check all frames').all_frames = True
        box = lay.box(); box.label(text='Secondary motion (antennas, cable)')
        box.prop(ob, '["springs_on"]', text='Live springs')
        r = box.row(align=True); r.operator('robot.bake_springs', icon='REC'); r.operator('robot.clear_springs', icon='X')
        lay.operator('robot.reset', icon='LOOP_BACK')
        lay.label(text='Joint limits are on every control', icon='INFO')


# ------------------------------------------------------------------ easy controls
# (label, bone, channel, axis index) - plain names for every motor; the joint limits clamp each slider
EASY = [
    ('Head & body', 'BODY', [
        ('Look left / right', 'sensor', 'rotation_euler', 1), ('Look up / down', 'sensor', 'rotation_euler', 0),
        ('Turn waist', 'waist', 'rotation_euler', 1), ('Lean forward / back', 'hips', 'rotation_euler', 0),
        ('Crouch / rise', 'COG', 'location', 2), ('Shift weight', 'COG', 'location', 0),
        ('Back hatch', 'hatch', 'rotation_euler', 0)]),
    ('Arm', 'ARM', [
        ('Swing forward / back', 'FK-upper_arm', 'rotation_euler', 0), ('Raise out to the side', 'FK-upper_arm', 'rotation_euler', 2),
        ('Twist upper arm', 'FK-upper_arm', 'rotation_euler', 1), ('Bend elbow', 'FK-forearm', 'rotation_euler', 0),
        ('Wrist roll', 'FK-hand', 'rotation_euler', 1), ('Wrist up / down', 'FK-hand', 'rotation_euler', 0),
        ('Wrist side to side', 'FK-hand', 'rotation_euler', 2), ('Grip (open / close)', 'grip', 'rotation_euler', 0),
        ('Thumb swivel', 'f_thumb_0', 'rotation_euler', 1)]),
    ('Leg', 'LEG', [
        ('Foot forward / back', 'IK_foot', 'location', 1), ('Lift foot', 'IK_foot', 'location', 2),
        ('Foot in / out', 'IK_foot', 'location', 0), ('Turn foot', 'IK_foot', 'rotation_euler', 2),
        ('Heel lift (tip-toe)', 'roll_ball', 'rotation_euler', 0), ('Toe lift', 'roll_heel', 'rotation_euler', 0)]),
]


def easy_bones(ob):
    out = set()
    for _, kind, rows in EASY:
        for _, b, ch, i in rows:
            for S in (('L', 'R') if kind != 'BODY' else ('',)):
                out.add(f'{b}.{S}' if S else b)
    return [b for b in out if b in ob.pose.bones]


class ROBOT_OT_key_pose(bpy.types.Operator):
    """Keyframe every easy control at the current frame"""
    bl_idname = 'robot.key_pose'; bl_label = 'Key pose'; bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        ob = rig(ctx); f = ctx.scene.frame_current
        for b in easy_bones(ob):
            pb = ob.pose.bones[b]
            pb.keyframe_insert('rotation_euler', frame=f); pb.keyframe_insert('location', frame=f)
        self.report({'INFO'}, f'Pose keyed at frame {f}'); return {'FINISHED'}


class ROBOT_OT_mirror(bpy.types.Operator):
    """Copy one arm or leg onto the other side, mirrored"""
    bl_idname = 'robot.mirror'; bl_label = 'Mirror'; bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.StringProperty(); src: bpy.props.StringProperty(default='L')

    def execute(self, ctx):
        ob = rig(ctx); pb = ob.pose.bones; dst = 'R' if self.src == 'L' else 'L'
        rows = next(r for _, k, r in EASY if k == self.kind)
        for b in {r[1] for r in rows} | ({'f_thumb_0'} if self.kind == 'ARM' else set()):
            a, c = pb[f'{b}.{self.src}'], pb[f'{b}.{dst}']
            c.rotation_euler = (a.rotation_euler.x, -a.rotation_euler.y, -a.rotation_euler.z)
            c.location = (-a.location.x, a.location.y, a.location.z)
        return {'FINISHED'}


class ROBOT_OT_pose_preset(bpy.types.Operator):
    """Put the robot in a ready-made pose (every preset is collision-checked)"""
    bl_idname = 'robot.pose_preset'; bl_label = 'Pose'; bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    def execute(self, ctx):
        ob = rig(ctx); P = json.loads(ob['pose_presets'])[self.name]
        for p in ob.pose.bones:
            if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')):
                p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
        for b, (rot, loc) in P.items():
            ob.pose.bones[b].rotation_euler = [math.radians(v) for v in rot]; ob.pose.bones[b].location = loc
        return {'FINISHED'}


class ROBOT_PT_easy(bpy.types.Panel):
    bl_label = 'Easy controls'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Robot'

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        ob = rig(ctx); pb = ob.pose.bones; lay = self.layout
        if 'pose_presets' in ob:
            box = lay.box(); box.label(text='One-click poses', icon='ARMATURE_DATA')
            g = box.grid_flow(columns=3, align=True)
            for n in json.loads(ob['pose_presets']):
                g.operator('robot.pose_preset', text=n).name = n
        for title, kind, rows in EASY:
            box = lay.box()
            if kind == 'BODY':
                box.label(text=title)
                col = box.column(align=True)
                for lab, b, ch, i in rows:
                    col.prop(pb[b], ch, index=i, text=lab)
                continue
            head = box.row(); head.label(text=f'{title}s   (right = screen left)')
            r = head.row(align=True)
            o = r.operator('robot.mirror', text='L to R'); o.kind, o.src = kind, 'L'
            o = r.operator('robot.mirror', text='R to L'); o.kind, o.src = kind, 'R'
            if kind == 'ARM':
                box.label(text='Arms move in FK. Use the Arms slider below to switch to IK.', icon='INFO')
            split = box.row()
            for S in ('R', 'L'):
                col = split.column(align=True); col.label(text=f'{title} {S}')
                for lab, b, ch, i in rows:
                    col.prop(pb[f'{b}.{S}'], ch, index=i, text=lab)
        if 'hold.R' in pb:
            box = lay.box(); box.label(text='Hold a prop: select it, then press Hold', icon='HAND')
            r = box.row(align=True)
            for S, lab in (('R', 'Right'), ('L', 'Left')):
                o = r.operator('robot.hold', text=f'Hold {lab}'); o.side, o.release = S, False
                o = r.operator('robot.hold', text=f'Release {lab}'); o.side, o.release = S, True
        lay.operator('robot.key_pose', icon='KEY_HLT')


# ------------------------------------------------------------------ hold a prop
# The prop is centred on the hand's hold.<S> bone (its longest side along the knuckle line), slid against the palm,
# parented to that bone, then the grip closes until the first finger touches and every other finger (and the thumb)
# curls on by itself until it touches too. "Touch" = sinks in no more than HOLD_TOL (the collision rule's 0.5 mm).
HOLD_TOL = 0.0004
HOLD_FINGERS = ('index', 'middle', 'ring', 'thumb')


def _mesh_tree(o, dg):
    from mathutils.bvhtree import BVHTree
    e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
    vs = [M @ v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]; e.to_mesh_clear()
    return vs, BVHTree.FromPolygons(vs, fs)


def _depth(a, b):
    """deepest point of mesh a inside closed mesh b, and of b inside a (0 if they don't overlap)"""
    (va, ta), (vb, tb) = a, b
    if not ta.overlap(tb): return 0.0
    m = 1e-6   # overlapping surfaces count as a touch even when no vertex is inside
    for vs, t in ((va, tb), (vb, ta)):
        for v in vs:
            loc, nrm, _, d = t.find_nearest(v)
            if loc is not None and d < 0.1 and (v - loc).dot(nrm) < 0: m = max(m, d)
    return m


def _parts(ob, test):
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == ob and test(o.get('rig_bone', ''))]


def _deepest(parts, prop_t, dg):
    return max([_depth(_mesh_tree(o, dg), prop_t) for o in parts] or [0.0])


def hold_prop(ob, S, prop, ctx):
    from mathutils import Matrix, Vector
    release_prop(ob, S, ctx)
    pb = ob.pose.bones; hb = pb[f'hold.{S}']; grip = pb[f'grip.{S}']
    grip.rotation_euler.x = 0.0
    for fn in HOLD_FINGERS: pb[f'f_{fn}_1.{S}'].rotation_euler.x = 0.0
    ctx.view_layer.update()
    H = ob.matrix_world @ hb.matrix                      # hold frame: y along the knuckle line
    # turn the prop so its longest side runs along the knuckle line, then centre it on the hold point
    dims = prop.dimensions; k = max(range(3), key=lambda i: dims[i])
    order = {0: (1, 0, 2), 1: (0, 1, 2), 2: (0, 2, 1)}[k]   # which prop axis goes on hold x, y, z
    R = Matrix([[1.0 if order[c] == r else 0.0 for c in range(3)] for r in range(3)]).transposed()
    if R.determinant() < 0: R[2] = -R[2]
    rot = H.to_3x3().normalized() @ R
    prop.matrix_world = Matrix.Translation(H.translation) @ rot.to_4x4() @ Matrix.Diagonal(prop.matrix_world.to_scale()).to_4x4()
    ctx.view_layer.update()
    dg = ctx.evaluated_depsgraph_get()
    c = sum((prop.matrix_world @ Vector(v) for v in prop.bound_box), Vector()) / 8
    prop.matrix_world.translation += H.translation - c
    # slide it straight into the palm until it touches the palm or a finger, then settle on the touch
    palm = _parts(ob, lambda b: b == f'DEF-hand.{S}' or (b.startswith('f_') and b.endswith(f'.{S}')))
    po = bpy.data.objects.get(f'palm.{S}') or palm[0]   # geometric centre (part origins can sit anywhere)
    pc = sum((po.matrix_world @ Vector(v) for v in po.bound_box), Vector()) / 8
    d = H.to_3x3().col[0].normalized()   # straight into the palm face (across the knuckle line), not toward its centre
    d = d if d.dot(pc - H.translation) > 0 else -d
    def palm_depth():
        ctx.view_layer.update(); dg = ctx.evaluated_depsgraph_get()
        return _deepest(palm, _mesh_tree(prop, dg), dg)
    step = 0.002
    if palm_depth() > HOLD_TOL:
        for _ in range(60):
            prop.matrix_world.translation -= d * step
            if palm_depth() <= HOLD_TOL: break
        lo, hi = 0.0, step
    else:
        for _ in range(60):
            prop.matrix_world.translation += d * step
            if palm_depth() > HOLD_TOL: break
        lo, hi = -step, 0.0
    base = prop.matrix_world.translation.copy()
    for _ in range(8):   # fine approach: largest move along d that stays within the touch tolerance
        mid = (lo + hi) / 2; prop.matrix_world.translation = base + d * mid
        if palm_depth() > HOLD_TOL: hi = mid
        else: lo = mid
    prop.matrix_world.translation = base + d * lo
    ctx.view_layer.update()
    W = prop.matrix_world.copy()
    prop.parent = ob; prop.parent_type = 'BONE'; prop.parent_bone = f'hold.{S}'
    prop.matrix_world = W; prop['held_by'] = f'{ob.name}:{S}'
    ctx.view_layer.update()

    def close(set_angle, parts, limit, others=()):
        """largest angle (degrees, 0..limit) where parts sink no deeper than HOLD_TOL into the prop
        (or into the other fingers' parts, so the thumb never closes through a finger)"""
        def deep(a):
            set_angle(a); ctx.view_layer.update(); dg = ctx.evaluated_depsgraph_get()
            d = _deepest(parts, _mesh_tree(prop, dg), dg)
            if others and d <= HOLD_TOL:
                ot = [_mesh_tree(o, dg) for o in others]
                for o in parts:
                    t = _mesh_tree(o, dg)
                    if any(_depth(t, x) > HOLD_TOL for x in ot): return 1.0
            return d
        prev = 0.0
        for a in range(3, int(limit) + 1, 3):
            if deep(a) > HOLD_TOL:
                lo, hi = prev, float(a)
                for _ in range(6):
                    mid = (lo + hi) / 2
                    if deep(mid) > HOLD_TOL: hi = mid
                    else: lo = mid
                set_angle(lo); ctx.view_layer.update(); return lo, True
            prev = float(a)
        set_angle(limit); ctx.view_layer.update(); return float(limit), False
    hand = _parts(ob, lambda b: b.startswith('f_') and b.endswith(f'.{S}'))
    lim = [c for c in grip.constraints if c.type == 'LIMIT_ROTATION']
    gmax = math.degrees(lim[0].max_x) if lim else 90.0
    g, _ = close(lambda a: setattr(grip.rotation_euler, 'x', math.radians(a)), hand, gmax)
    touched = {}

    def seg_lim(b):
        c = [c for c in b.constraints if c.type == 'LIMIT_ROTATION']
        return math.degrees(c[0].max_x) if c else 90.0

    def close_finger(fn, parts):
        """bend the base joint, then the middle and tip joints, each until the finger touches; (touching, extra)"""
        extra = 0.0
        for i in (1, 2, 3):   # start open: an earlier try (another thumb turret angle) may have left joints bent
            if pb.get(f'f_{fn}_{i}.{S}'): pb[f'f_{fn}_{i}.{S}'].rotation_euler.x = 0.0
        for i in (1, 2, 3):
            b = pb.get(f'f_{fn}_{i}.{S}')
            if b is None: continue
            room = max(0.0, seg_lim(b) - math.degrees(b.matrix_basis.to_euler().x) - (g if i == 1 else 0.0))
            others = [o for o in hand if o not in parts]
            a, hit = close(lambda a, b=b: setattr(b.rotation_euler, 'x', math.radians(a)), parts, room, others)
            if not hit: b.rotation_euler.x = 0.0 if i == 1 else math.radians(a)
            extra += a
            if hit: return True, extra
        for i in (1, 2, 3):   # never reached the prop: back to where the grip put it, instead of clenching on air
            if pb.get(f'f_{fn}_{i}.{S}'): pb[f'f_{fn}_{i}.{S}'].rotation_euler.x = 0.0
        ctx.view_layer.update(); return False, 0.0

    for fn in HOLD_FINGERS:   # each finger closes on by itself until it touches
        parts = [o for o in hand if o['rig_bone'].startswith(f'f_{fn}_')]
        t0 = pb.get(f'f_thumb_0.{S}')
        if fn == 'thumb' and t0 is not None:   # swivel the thumb turret to where the thumb meets the prop with least bend
            tl = [c for c in t0.constraints if c.type == 'LIMIT_ROTATION']
            ymax = math.degrees(tl[0].max_y) if tl else 75.0
            best = None
            for ty in range(int(-ymax), int(ymax) + 1, 15):
                t0.rotation_euler.y = math.radians(ty)
                hit, e = close_finger(fn, parts)
                if hit and (best is None or e < best[1]): best = (ty, e)
            t0.rotation_euler.y = math.radians(best[0]) if best else 0.0
        hit, _ = close_finger(fn, parts)
        dg = ctx.evaluated_depsgraph_get()
        touched[fn] = hit or _deepest(parts, _mesh_tree(prop, dg), dg) > 0
    lock_hand(ob, S)
    mark_hold(ob, S, 1.0, ctx)
    return g, touched


def mark_hold(ob, S, v, ctx):
    """rig property hold_<S> (1 holding, 0 empty hand), keyed on the current frame when the rig is animated,
    so other tools (contact sounds, the timeline) see the exact grab / release frame"""
    ob[f'hold_{S}'] = float(v)
    if ob.animation_data and ob.animation_data.action:
        ob.keyframe_insert(f'["hold_{S}"]', frame=ctx.scene.frame_current)
        for fc in getattr(ob.animation_data.action, 'fcurves', []) or []:
            if fc.data_path == f'["hold_{S}"]':
                for k in fc.keyframe_points: k.interpolation = 'CONSTANT'


def lock_hand(ob, S):
    """keep the fingers closed on the prop whatever a motion or pose preset does to the grip: a 'hold lock' limit
    at the end of each finger joint's stack pins it to the angle it closed to"""
    bpy.context.view_layer.update()
    for pb in ob.pose.bones:
        if not (pb.name.endswith('.' + S) and pb.name.startswith('f_')): continue
        L = ob.convert_space(pose_bone=pb, matrix=pb.matrix, from_space='POSE', to_space='LOCAL').to_euler(pb.rotation_mode if len(pb.rotation_mode) == 3 else 'XYZ')
        c = pb.constraints.get('hold lock') or pb.constraints.new('LIMIT_ROTATION')
        c.name = 'hold lock'; c.owner_space = 'LOCAL'
        for i, a in enumerate('xyz'):
            setattr(c, f'use_limit_{a}', True); setattr(c, f'min_{a}', L[i]); setattr(c, f'max_{a}', L[i])


def unlock_hand(ob, S):
    for pb in ob.pose.bones:
        if pb.name.endswith('.' + S) and 'hold lock' in pb.constraints: pb.constraints.remove(pb.constraints['hold lock'])


def release_prop(ob, S, ctx):
    pb = ob.pose.bones
    if ob.get(f'hold_{S}'): mark_hold(ob, S, 0.0, ctx)
    unlock_hand(ob, S)
    for o in bpy.data.objects:
        if o.get('held_by') == f'{ob.name}:{S}':
            W = o.matrix_world.copy(); o.parent = None; o.matrix_world = W; del o['held_by']
    if f'grip.{S}' in pb:
        pb[f'grip.{S}'].rotation_euler.x = 0.0
        for fn in HOLD_FINGERS:
            if f'f_{fn}_1.{S}' in pb: pb[f'f_{fn}_1.{S}'].rotation_euler.x = 0.0
        if f'f_thumb_0.{S}' in pb: pb[f'f_thumb_0.{S}'].rotation_euler.y = 0.0
    ctx.view_layer.update()


class ROBOT_OT_hold(bpy.types.Operator):
    """Put the selected prop in this hand: it sits against the palm and every finger closes until it touches"""
    bl_idname = 'robot.hold'; bl_label = 'Hold'; bl_options = {'REGISTER', 'UNDO'}
    side: bpy.props.StringProperty(default='R')
    release: bpy.props.BoolProperty(default=False)

    def execute(self, ctx):
        ob = rig(ctx)
        if self.release:
            release_prop(ob, self.side, ctx); return {'FINISHED'}
        props = [o for o in ctx.selected_objects if o.type == 'MESH' and o.parent != ob and 'rig_bone' not in o]
        if not props:
            self.report({'WARNING'}, 'Select the prop first (a mesh that is not part of the robot)'); return {'CANCELLED'}
        g, touched = hold_prop(ob, self.side, props[0], ctx)
        miss = [f for f, t in touched.items() if not t]
        self.report({'INFO'}, f'Holding {props[0].name}: grip {g:.0f} deg' + (f'; not touching: {", ".join(miss)} (prop too small for them)' if miss else '; every finger touching'))
        return {'FINISHED'}


# ------------------------------------------------------------------ look (weathering)
class ROBOT_PT_look(bpy.types.Panel):
    bl_label = 'Look: weathered metal + polymer'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Robot'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        ob = rig(ctx); col = self.layout.column(align=True)
        for k, lab in (('look_wear', 'Chipped paint'), ('look_rust', 'Rust'), ('look_grime', 'Dirt and streaks'),
                       ('look_scuffs', 'Polymer scuffs')):
            if k in ob: col.prop(ob, f'["{k}"]', text=lab, slider=True)
        if 'palettes' in ob:   # colour schemes: every RB_metal_<role> paint colour at once
            self.layout.label(text='Colour scheme' + (f"  (now: {ob.get('palette', '')})" if ob.get('palette') else ''))
            g = self.layout.grid_flow(columns=3, align=True)
            for n in json.loads(ob['palettes']): g.operator('robot.palette', text=n.title()).name = n


class ROBOT_OT_palette(bpy.types.Operator):
    """Repaint the robot in this colour scheme (wear, rust and dirt stay as they are)"""
    bl_idname = 'robot.palette'; bl_label = 'Colour scheme'; bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    def execute(self, ctx):
        ob = rig(ctx); pal = json.loads(ob['palettes'])[self.name]
        for role, hx in pal.items():
            m = bpy.data.materials.get('RB_metal_' + role)
            if not m or not m.node_tree or 'Look' not in m.node_tree.nodes: continue
            h = hx.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            lin = [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c]
            m.node_tree.nodes['Look'].inputs['Paint Colour'].default_value = lin + [1]; m.diffuse_color = lin + [1]
        ob['palette'] = self.name
        return {'FINISHED'}


# ------------------------------------------------------------------ motion library
def motions():
    return sorted((a for a in bpy.data.actions if a.get('robot_motion')), key=lambda a: a.get('order', 99))


class ROBOT_OT_motion(bpy.types.Operator):
    """Put a library motion on the robot"""
    bl_idname = 'robot.motion'; bl_label = 'Use motion'; bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.StringProperty()
    mode: bpy.props.EnumProperty(items=[('REPLACE', 'Play', 'Make this the robot\'s animation and fit the timeline to it'),
                                        ('INSERT', 'Add at playhead', 'Add it as a clip at the current frame, on top of what is there')])

    def execute(self, ctx):
        ob = rig(ctx); sc = ctx.scene; act = bpy.data.actions[self.action]
        ad = ob.animation_data or ob.animation_data_create()
        n = int(act.frame_range[1] - act.frame_range[0])
        if self.mode == 'REPLACE':
            for p in ob.pose.bones:
                if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')):
                    p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
            ad.action = act
            if hasattr(ad, 'action_slot') and act.slots: ad.action_slot = act.slots[0]
            sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
            sc.frame_set(sc.frame_start)
        else:
            if ad.action:   # keep what is there as the bottom clip
                tr0 = ad.nla_tracks.new(); tr0.name = 'Base'
                tr0.strips.new(ad.action.name, int(ad.action.frame_range[0]), ad.action); ad.action = None
            tr = ad.nla_tracks.new(); tr.name = act.get('label', act.name)
            st = tr.strips.new(act.name, sc.frame_current, act)
            st.blend_in = st.blend_out = min(6, n // 4); st.use_auto_blend = False
            sc.frame_end = max(sc.frame_end, int(st.frame_end))
        _STATE.clear()
        self.report({'INFO'}, f'{act.get("label", act.name)}: {n} frames'); return {'FINISHED'}


class ROBOT_PT_motions(bpy.types.Panel):
    bl_label = 'Motion library'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Robot'

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        lay = self.layout
        g = lay.grid_flow(columns=2, even_columns=True, align=False)
        for a in motions():
            box = g.box(); col = box.column(align=True)
            if a.preview: col.template_icon(icon_value=a.preview.icon_id, scale=6)
            col.label(text=a.get('label', a.name))
            col.label(text=f'{int(a.frame_range[1] - a.frame_range[0])} frames' + ('  loop' if a.get('loop') else ''))
            r = col.row(align=True)
            o = r.operator('robot.motion', text='Play', icon='PLAY'); o.action, o.mode = a.name, 'REPLACE'
            o = r.operator('robot.motion', text='Add', icon='ADD'); o.action, o.mode = a.name, 'INSERT'
        lay.label(text='Also in the Asset Browser (Robot Motions)', icon='ASSET_MANAGER')



# ================================================================== DRIVE MODE (gamepad / keyboard puppeteering)
# Xbox-style pads are read straight from Windows (XInput, no install). PlayStation pads work through Steam or DS4Windows.
import ctypes, re, sys as _sys
from mathutils import Matrix

_XI = {'dll': None, 'tried': False}

class _XPad(ctypes.Structure):
    _fields_ = [('wButtons', ctypes.c_ushort), ('bLeftTrigger', ctypes.c_ubyte), ('bRightTrigger', ctypes.c_ubyte),
                ('sThumbLX', ctypes.c_short), ('sThumbLY', ctypes.c_short), ('sThumbRX', ctypes.c_short), ('sThumbRY', ctypes.c_short)]

class _XState(ctypes.Structure):
    _fields_ = [('dwPacketNumber', ctypes.c_uint), ('Gamepad', _XPad)]

XB = dict(UP=0x1, DOWN=0x2, LEFT=0x4, RIGHT=0x8, START=0x10, BACK=0x20, L3=0x40, R3=0x80, LB=0x100, RB=0x200,
          A=0x1000, B=0x2000, X=0x4000, Y=0x8000, PS=0x10000, PAD=0x20000)

# ---- DualSense / DualShock / other HID pads through the Windows joystick API (winmm), no driver or install
class _JoyInfoEx(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('dwSize', 'dwFlags', 'dwXpos', 'dwYpos', 'dwZpos', 'dwRpos', 'dwUpos',
                                              'dwVpos', 'dwButtons', 'dwButtonNumber', 'dwPOV', 'dwReserved1', 'dwReserved2')]

_JOY = {'dll': None, 'tried': False, 'id': None, 'next_scan': 0.0, 'map': None, 'name': ''}
SONY_PIDS = {0x0CE6: 'DualSense', 0x0DF2: 'DualSense Edge', 0x05C4: 'DualShock 4', 0x09CC: 'DualShock 4'}
# DirectInput button order on Sony pads -> the shared layout (Cross = A, Circle = B, Square = X, Triangle = Y)
SONY_BTN = {0: 'X', 1: 'A', 2: 'B', 3: 'Y', 4: 'LB', 5: 'RB', 8: 'BACK', 9: 'START', 10: 'L3', 11: 'R3', 12: 'PS', 13: 'PAD'}
GENERIC_BTN = {0: 'A', 1: 'B', 2: 'X', 3: 'Y', 4: 'LB', 5: 'RB', 6: 'BACK', 7: 'START', 8: 'L3', 9: 'R3'}


def _joy_name(dll, jid):
    buf = ctypes.create_string_buffer(1024)
    if dll.joyGetDevCapsW(jid, buf, 728) != 0: return 0, 0, ''
    mid, pid = int.from_bytes(buf.raw[0:2], 'little'), int.from_bytes(buf.raw[2:4], 'little')
    name = buf.raw[4:68].decode('utf-16-le', 'ignore').split('\x00')[0]
    return mid, pid, name


def read_joy():
    import time as _t
    if not _JOY['tried']:
        _JOY['tried'] = True
        if _sys.platform == 'win32':
            try: _JOY['dll'] = ctypes.windll.winmm
            except OSError: pass
    dll = _JOY['dll']
    if not dll: return None
    ji = _JoyInfoEx(); ji.dwSize = ctypes.sizeof(_JoyInfoEx); ji.dwFlags = 0xFF
    if _JOY['id'] is None:
        if _t.time() < _JOY['next_scan']: return None
        _JOY['next_scan'] = _t.time() + 2.0
        for jid in range(16):
            if dll.joyGetPosEx(jid, ctypes.byref(ji)) == 0:
                mid, pid, name = _joy_name(dll, jid)
                _JOY.update(id=jid, sony=(mid == 0x054C or pid in SONY_PIDS), name=SONY_PIDS.get(pid, name or 'Gamepad'))
                # triggers rest at the bottom of their range, sticks rest in the middle: tell them apart once
                rest = {'Z': ji.dwZpos, 'R': ji.dwRpos, 'U': ji.dwUpos, 'V': ji.dwVpos}
                trig = [k for k in 'ZRUV' if rest[k] < 6000]
                stick = [k for k in 'ZRUV' if k not in trig]
                _JOY['map'] = dict(rx=stick[0] if stick else 'Z', ry=stick[1] if len(stick) > 1 else 'R',
                                   lt=trig[0] if trig else 'U', rt=trig[1] if len(trig) > 1 else 'V')
                break
        else:
            return None
    if dll.joyGetPosEx(_JOY['id'], ctypes.byref(ji)) != 0:
        _JOY['id'] = None; return None
    ax = {'X': ji.dwXpos, 'Y': ji.dwYpos, 'Z': ji.dwZpos, 'R': ji.dwRpos, 'U': ji.dwUpos, 'V': ji.dwVpos}
    def c(v): return (v - 32767.5) / 32767.5
    def stick(a, b):
        v = Vector((a, b)); m = v.length
        if m < 0.15: return 0.0, 0.0
        v = v * (min(1.0, (m - 0.15) / 0.85) / m); return v.x, v.y
    M = _JOY['map']
    lx, ly = stick(c(ax['X']), -c(ax['Y'])); rx, ry = stick(c(ax[M['rx']]), -c(ax[M['ry']]))
    bmap = SONY_BTN if _JOY['sony'] else GENERIC_BTN
    b = 0
    for bit, name in bmap.items():
        if ji.dwButtons & (1 << bit): b |= XB[name]
    pov = ji.dwPOV
    if pov != 0xFFFF and pov <= 36000:
        d = pov / 100.0
        if d >= 315 or d <= 45: b |= XB['UP']
        if 45 <= d <= 135: b |= XB['RIGHT']
        if 135 <= d <= 225: b |= XB['DOWN']
        if 225 <= d <= 315: b |= XB['LEFT']
    return dict(lx=lx, ly=ly, rx=rx, ry=ry, lt=ax[M['lt']] / 65535, rt=ax[M['rt']] / 65535, b=b, pad=_JOY['id'],
                name=_JOY['name'], sony=_JOY['sony'])


def read_pad():
    if not _XI['tried']:
        _XI['tried'] = True
        if _sys.platform == 'win32':
            for n in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
                try: _XI['dll'] = ctypes.windll.LoadLibrary(n); break
                except OSError: pass
    x = _XI['dll']
    if not x: return read_joy()
    for i in range(4):
        st = _XState()
        if x.XInputGetState(i, ctypes.byref(st)) == 0:
            g = st.Gamepad
            def stick(a, b):
                v = Vector((a / 32767, b / 32767)); m = v.length
                if m < 0.22: return 0.0, 0.0
                v = v * (min(1.0, (m - 0.22) / 0.78) / m); return v.x, v.y
            lx, ly = stick(g.sThumbLX, g.sThumbLY); rx, ry = stick(g.sThumbRX, g.sThumbRY)
            return dict(lx=lx, ly=ly, rx=rx, ry=ry, lt=g.bLeftTrigger / 255, rt=g.bRightTrigger / 255, b=g.wButtons, pad=i,
                        name='Xbox controller', sony=False)
    return read_joy()


class DriveInput:
    """one frame of intent, merged from gamepad and keyboard"""
    def __init__(self):
        self.move = self.turn = self.look_x = self.look_y = 0.0
        self.grip_l = self.grip_r = 0.0
        self.arm_l = self.arm_r = self.crouch = self.run = False
        self.fire = set()      # one-shot buttons this frame: wave grab thumbs celebrate hatch power record follow exit


KEY_FIRE = {'SPACE': 'wave', 'G': 'grab', 'T': 'thumbs', 'V': 'celebrate', 'H': 'hatch', 'P': 'power',
            'R': 'record', 'F': 'follow', 'ESC': 'exit', 'L': 'look'}
PAD_FIRE = {'A': 'wave', 'B': 'grab', 'X': 'thumbs', 'Y': 'celebrate', 'UP': 'hatch', 'START': 'power',
            'BACK': 'record', 'R3': 'follow', 'LEFT': 'look', 'PAD': 'follow', 'PS': 'exit'}
MOVE_ACTIONS = {'wave': 'RM_wave', 'grab': 'RM_grab_lift', 'thumbs': 'RM_thumbs_up', 'celebrate': 'RM_celebrate',
                'look': 'RM_look_around'}
_PATH = re.compile(r'pose\.bones\["([^"]+)"\]\.(rotation_euler|location)')
LOCO = ('root', 'IK_foot', 'roll_', 'pole_', 'COG')


def action_fcurves(act):
    if hasattr(act, 'layers') and len(act.layers):
        for layer in act.layers:
            for st in layer.strips:
                for cb in st.channelbags:
                    yield from cb.fcurves
    elif hasattr(act, 'fcurves'):
        yield from act.fcurves


def _smooth(cur, tgt, rate, dt):
    return cur + (tgt - cur) * min(1.0, rate * dt)


class DriveCore:
    """Walks the rig from stick input: root travels, feet step and stay planted, body sways; everything is servo-eased."""
    T_WALK, T_RUN, V_WALK, V_RUN, YAW_RATE = 0.46, 0.36, 0.45, 0.8, math.radians(75)
    # gait (per droid via rig custom props drive_<name>): double support s, CoM height m, sideways ZMP target as a
    # COG offset m, heel-peel lead s, heel slap s, peel/strike degrees, toe counter-turn, body drop over the foot m
    DS, COM_H, SWAY, PEEL, SLAP, BALL, HEEL, TOE_K, DROP, ENV_T, REACH, TWIST = 0.30, 1.5, 0.38, 0.16, 0.18, 18.0, 12.0, 0.15, 0.02, 0.25, 1.0, 9.0

    def __init__(self, ob):
        self.ob = ob; pb = ob.pose.bones; B = ob.data.bones
        self.M_root = B['root'].matrix_local.copy(); self.M_cog = B['COG'].matrix_local.copy()
        self.M_foot = {S: B[f'IK_foot.{S}'].matrix_local.copy() for S in 'LR'}
        self.off = {S: self.M_foot[S].translation.copy() for S in 'LR'}          # foot home in the robot's frame
        self.cog_off = self.M_cog.translation.copy()
        # start where the root is now
        Mr = ob.matrix_world.inverted() @ (ob.matrix_world @ pb['root'].matrix)
        R0 = Mr @ self.M_root.inverted()
        self.pos = R0.translation.copy(); self.pos.z = 0.0
        self.yaw = R0.to_euler('XYZ').z
        self.speed = self.yawrate = 0.0
        self.feet = {}
        for S in 'LR':
            P = self.root_xf(self.pos, self.yaw) @ self.off[S]; P.z = 0.0
            self.feet[S] = dict(P=P, Y=self.yaw, step=None)
        self.ch = {}                      # smoothed scalar channels
        self.t = 0.0; self.powered = True; self.hatch_open = False; self.follow = True
        self.overlay = None               # (action, start time, length s, channels)
        self.last_lift = None
        self.ph = 0.75                    # gait clock, 0..1 per two steps (L lifts near 0.25 - half its swing)
        for k in ('DS', 'COM_H', 'SWAY', 'PEEL', 'SLAP', 'BALL', 'HEEL', 'TOE_K', 'DROP', 'ENV_T', 'REACH', 'TWIST'):
            v = ob.get('drive_' + k.lower())
            if v is not None: setattr(self, k, float(v))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def root_xf(pos, yaw):
        return Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, 'Z')

    def home(self, S, lookahead):
        p = self.pos + Matrix.Rotation(self.yaw, 3, 'Z') @ Vector((0, -1, 0)) * (self.speed * lookahead)
        y = self.yaw + self.yawrate * lookahead
        h = self.root_xf(p, y) @ self.off[S]; h.z = 0.0
        return h, y

    def sm(self, k, tgt, rate, dt, start=0.0):
        v = _smooth(self.ch.get(k, start), tgt, rate, dt); self.ch[k] = v; return v

    def play(self, name):
        act = bpy.data.actions.get(name)
        if not act: return
        fps = bpy.context.scene.render.fps or 24
        n = (act.frame_range[1] - act.frame_range[0]) / fps
        allow_cog = name in ('RM_crouch', 'RM_power_down', 'RM_power_up', 'RM_celebrate')
        chans = []
        for fc in action_fcurves(act):
            m = _PATH.match(fc.data_path)
            if not m: continue
            b = m.group(1)
            if b.startswith(LOCO) and not (allow_cog and b == 'COG'): continue
            if b not in self.ob.pose.bones: continue
            chans.append((b, m.group(2), fc.array_index, fc))
        self.overlay = dict(act=act, t0=self.t, n=n, chans=chans, name=name, f0=act.frame_range[0])

    # ---------------------------------------------------------------- one tick
    def tick(self, inp, dt):
        ob = self.ob; pb = ob.pose.bones; r = math.radians
        self.t += dt
        for f in inp.fire:
            if f in MOVE_ACTIONS and self.powered: self.play(MOVE_ACTIONS[f])
            elif f == 'hatch': self.hatch_open = not self.hatch_open
            elif f == 'follow': self.follow = not self.follow
            elif f == 'power':
                self.play('RM_power_down' if self.powered else 'RM_power_up'); self.powered = not self.powered
        busy = self.overlay is not None and self.overlay['name'] in ('RM_power_down', 'RM_power_up')
        can_walk = self.powered and not busy

        # body travel
        vmax = self.V_RUN if inp.run else self.V_WALK
        tgt_v = (inp.move * vmax) if can_walk else 0.0
        tgt_w = (-inp.turn * self.YAW_RATE) if can_walk else 0.0
        # the body may not outrun its planted feet
        worst = 0.0
        for S, F in self.feet.items():
            if F['step'] is None:
                h, _ = self.home(S, 0.0); worst = max(worst, (F['P'] - h).length)
        lim = max(0.0, min(1.0, (0.26 - worst) / 0.08))
        twist = max([abs((F['Y'] - self.yaw + math.pi) % (2 * math.pi) - math.pi) for F in self.feet.values() if F['step'] is None] or [0.0])
        tlim = max(0.0, min(1.0, (math.radians(self.TWIST) - twist) / math.radians(5)))   # hip yaw bearing stays clear of the pelvis
        gait = self.ch.get('env', 0.0)          # the body only travels once the weight is moving from foot to foot
        lim = self.sm('lim', lim, 3.0, dt, 1.0)      # a heavy body changes speed gradually (no surges as feet land)
        self.speed = _smooth(self.speed, tgt_v * lim * gait, 2.5, dt)
        self.yawrate = _smooth(self.yawrate, tgt_w * (0.4 + 0.6 * lim) * tlim, 5.0, dt)
        fwd = Matrix.Rotation(self.yaw, 3, 'Z') @ Vector((0, -1, 0))
        self.pos += fwd * self.speed * dt; self.yaw += self.yawrate * dt

        # feet: a gait clock. Each foot lifts at its own point in the cycle, so both feet are down between steps
        # (double support). The body sways as a linear inverted pendulum whose floor push (ZMP) sits on the stance foot
        # while the other foot is in the air: x = P (1 - cosh(t/tau) / cosh(Th/2tau)) per half cycle, which is what
        # mass and gravity allow (an eased sway that "waits" over the foot would need impossible sideways forces).
        T = self.T_RUN if inp.run else self.T_WALK
        Tc = self.sm('Tc', 2 * (T + self.DS), 3.0, dt, 2 * (T + self.DS))   # walk <-> run changes the rhythm smoothly
        moving = abs(self.speed) > 0.03 or abs(self.yawrate) > 0.05
        errs = {}
        for S, F in self.feet.items():
            h, y = self.home(S, 0.0)
            errs[S] = (F['P'] - h).length + 0.004 * abs(math.degrees(y - F['Y']))
        want = {S: moving or errs[S] > 0.025 for S in 'LR'}
        busy_step = any(F['step'] is not None for F in self.feet.values())
        env = self.ch['env'] = _smooth(self.ch.get('env', 0.0), 1.0 if (any(want.values()) or busy_step) else 0.0, 1 / self.ENV_T, dt)
        ph0 = self.ph; self.ph = (self.ph + dt / Tc) % 1.0
        half = 0.5 * T / Tc
        lift_at = {'L': (0.25 - half) % 1.0, 'R': (0.75 - half) % 1.0}
        for S, F in self.feet.items():
            other = self.feet['R' if S == 'L' else 'L']
            crossed = (ph0 <= lift_at[S] < self.ph) or (self.ph < ph0 and (lift_at[S] >= ph0 or lift_at[S] < self.ph))
            if crossed and F['step'] is None and other['step'] is None and want[S] and env >= 0.9:
                F['step'] = dict(t=0.0, P0=F['P'].copy(), Y0=F['Y'], T=T, ball=F.get('ball', 0.0)); self.last_lift = S
        swing = {'L': 0.0, 'R': 0.0}
        for S, F in self.feet.items():
            st = F['step']
            if st is None:
                ttl = ((lift_at[S] - self.ph) % 1.0) * Tc        # heel peels just before the toe pushes off
                peel = 1.0 - ttl / self.PEEL if (want[S] and env >= 0.85 and ttl < self.PEEL) else 0.0
                F['ball'] = self.BALL * peel * peel * (3 - 2 * peel)
                lt = (self.t - F.get('landed', -9)) / self.SLAP     # heel takes the impact, the forefoot rolls down gently
                F['heel'] = self.HEEL * (1 - lt) ** 2 if lt < 1 else 0.0
                continue
            st['t'] += dt; s = min(1.0, st['t'] / st['T'])
            look = max(0.0, st['T'] - st['t']) + 0.5 * st['T']
            P1, Y1 = self.home(S, look)
            e = s * s * (3 - 2 * s)
            F['P'] = st['P0'].lerp(P1, e); F['Y'] = st['Y0'] + (Y1 - st['Y0']) * e
            hz = 0.08 if not inp.run else 0.065   # lift eases off the floor (no jolt), comes down with speed onto the heel
            F['P'].z = hz * ((1 - math.cos(2 * math.pi * s)) / 2 if s < 0.5 else math.sin(math.pi * s))
            swing[S] = math.sin(math.pi * s)
            a = min(1.0, s / 0.45); F['ball'] = st['ball'] * (1 - a * a * (3 - 2 * a))         # push-off, toe leaves last
            b = max(0.0, (s - 0.5) / 0.5); F['heel'] = self.HEEL * b * b * (3 - 2 * b)        # toes up for the heel strike
            if s >= 1.0:
                F['P'].z = 0.0; F['step'] = None; F['landed'] = self.t
        # lateral pendulum: ZMP P on the stance foot, CoM follows the cosh profile, eased in and out with the gait
        tau = math.sqrt(self.COM_H / 9.81); Th = Tc / 2
        u = (self.ph % 0.5) * Tc - Th / 2                     # time from mid single support
        prof = 1 - math.cosh(u / tau) / math.cosh(Th / 2 / tau)
        side = -1 if self.ph < 0.5 else 1                     # L in the air (ph < 0.5): weight over R (-x)
        cx = side * self.SWAY * prof * env * env * (3 - 2 * env)
        self.ch['sway'] = cx

        # pose: root, COG, feet (armature-space matrices -> local)
        Rw = self.root_xf(Vector((self.pos.x, self.pos.y, 0.0)), self.yaw)
        root_pose = Rw @ self.M_root
        pb['root'].matrix_basis = self.M_root.inverted() @ root_pose
        sn = min(1.0, abs(self.speed) / self.V_WALK)
        crouch = self.sm('crouch', -0.18 if (inp.crouch and self.powered) else 0.0, 5.0, dt)
        cz = -0.035 - 0.03 * sn + crouch - 0.012 * max(swing.values()) - self.DROP * (cx / self.SWAY) ** 2 \
            - self.REACH * max(0.0, worst - 0.1) ** 2      # hip over the foot / a planted foot far behind: knees give a little
        cog_local = Matrix.Translation(self.cog_off + Vector((cx, 0.0, cz)))
        cog_pose = Rw @ cog_local @ self.M_cog.to_3x3().to_4x4()
        par = root_pose @ self.M_root.inverted() @ self.M_cog
        pb['COG'].matrix_basis = par.inverted() @ cog_pose
        for S, F in self.feet.items():
            Mf = Matrix.Translation(F['P']) @ Matrix.Rotation(F['Y'], 4, 'Z') @ self.M_foot[S].to_3x3().to_4x4()
            par = root_pose @ self.M_root.inverted() @ self.M_foot[S]
            pb[f'IK_foot.{S}'].matrix_basis = par.inverted() @ Mf
            pb[f'IK_foot.{S}']['ik_fk'] = 1.0; pb[f'IK_hand.{S}']['ik_fk'] = 0.0
            for bn, val in ((f'roll_ball.{S}', F.get('ball', 0.0)), (f'roll_heel.{S}', F.get('heel', 0.0)),
                            (f'IK-toe.{S}', F.get('ball', 0.0) * self.TOE_K)):
                if bn in pb: pb[bn].rotation_euler = (r(val), 0, 0)

        # upper body
        pan = self.sm('pan', -inp.look_x * 100 if self.powered else 0.0, 4.0, dt)
        tilt = self.sm('tilt', (-inp.look_y * 25) if self.powered else 22, 4.0, dt)
        pb['sensor'].rotation_euler = (r(tilt), r(pan), 0)
        waist = self.sm('waist', max(-40, min(40, pan * 0.3 + math.degrees(self.yawrate) * 0.15)), 3.0, dt)
        pb['waist'].rotation_euler = (0, r(waist), 0)
        lean = self.sm('lean', -5 * sn * (1 if self.speed >= 0 else -1) + (6 if crouch < -0.05 else 0), 3.0, dt)
        pb['hips'].rotation_euler = (r(lean), 0, r(3 * (swing['L'] - swing['R']) * sn))
        for S, up, g in (('L', inp.arm_l, inp.grip_l), ('R', inp.arm_r, inp.grip_r)):
            other = 'R' if S == 'L' else 'L'
            sw = 12 * sn * (swing[other] - swing[S])
            ux = self.sm(f'arm_{S}', (62 if up else 0) + (0 if up else sw), 6.0, dt)
            fx = self.sm(f'fore_{S}', 50 if up else 14, 6.0, dt)
            pb[f'FK-upper_arm.{S}'].rotation_euler = (r(ux), 0, r(10 if S == 'L' else -10) if up else 0)
            pb[f'FK-forearm.{S}'].rotation_euler = (r(fx), 0, 0)
            pb[f'FK-hand.{S}'].rotation_euler = (0, 0, 0)
            gv = self.sm(f'grip_{S}', 20 + 38 * g, 10.0, dt, 20)
            pb[f'grip.{S}'].rotation_euler = (r(gv), 0, 0)
            pb[f'f_thumb_0.{S}'].rotation_euler = (0, 0, 0)
        pb['hatch'].rotation_euler = (r(self.sm('hatch', 75 if self.hatch_open else 0, 3.0, dt)), 0, 0)

        # library move on top, eased in and out
        ov = self.overlay
        if ov:
            fps = bpy.context.scene.render.fps or 24
            lt = self.t - ov['t0']
            if lt >= ov['n'] and not (ov['name'] == 'RM_power_down'):
                self.overlay = None
            else:
                lt = min(lt, ov['n'])
                w = 1.0 if ov['name'] in ('RM_power_down', 'RM_power_up') else min(1.0, lt / 0.25, max(0.0, (ov['n'] - lt) / 0.25))
                fr = ov['f0'] + lt * fps
                for b, prop, i, fc in ov['chans']:
                    p = pb[b]; vec = list(getattr(p, prop)); vec[i] = vec[i] + (fc.evaluate(fr) - vec[i]) * w
                    setattr(p, prop, vec)
                if ov['name'] == 'RM_power_up' and lt >= ov['n']: self.overlay = None
        return dict(pos=self.pos.copy(), yaw=self.yaw, speed=self.speed)

    def keyed_bones(self):
        out = ['root', 'COG', 'hips', 'waist', 'sensor', 'hatch']
        for S in 'LR':
            out += [b for b in (f'roll_ball.{S}', f'roll_heel.{S}', f'IK-toe.{S}') if b in self.ob.pose.bones]
            out += [f'IK_foot.{S}', f'FK-upper_arm.{S}', f'FK-forearm.{S}', f'FK-hand.{S}', f'grip.{S}', f'f_thumb_0.{S}']
        return out


# ---------------------------------------------------------------- the live operator
_HUD = {'h': None, 'lines': []}

def _draw_hud():
    import blf
    y = 60
    for i, (txt, col) in enumerate(reversed(_HUD['lines'])):
        blf.size(0, 15); blf.color(0, *col); blf.position(0, 24, y + i * 22, 0); blf.draw(0, txt)


class ROBOT_OT_drive(bpy.types.Operator):
    """Drive the robot live with a gamepad or the keyboard. R records a take into the motion library, Esc stops."""
    bl_idname = 'robot.drive'; bl_label = 'Drive the robot'

    def invoke(self, ctx, event):
        ob = rig(ctx)
        if ctx.area is None or ctx.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Start it from the 3D viewport'); return {'CANCELLED'}
        if ctx.mode != 'POSE' and ctx.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ad = ob.animation_data or ob.animation_data_create()
        self.saved = dict(action=ad.action, nla=ad.use_nla, springs=ob.get('springs_on', 1), frame=ctx.scene.frame_current)
        ad.action = None; ad.use_nla = False; ob['springs_on'] = 1; _STATE.clear()
        for p in ob.pose.bones:
            if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')):
                p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
        self.core = DriveCore(ob); self.keys = set(); self.prev_b = 0; self.rec = None; self.ob = ob
        self.area = ctx.area
        wm = ctx.window_manager; self.timer = wm.event_timer_add(1 / 24, window=ctx.window)
        wm.modal_handler_add(self)
        if _HUD['h'] is None:
            _HUD['h'] = bpy.types.SpaceView3D.draw_handler_add(_draw_hud, (), 'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}

    def gather(self):
        i = DriveInput(); k = self.keys
        i.move = (1.0 if 'W' in k else 0) - (1.0 if 'S' in k else 0)
        i.turn = (1.0 if 'D' in k else 0) - (1.0 if 'A' in k else 0)
        i.look_x = (1.0 if 'RIGHT_ARROW' in k else 0) - (1.0 if 'LEFT_ARROW' in k else 0)
        i.look_y = (1.0 if 'UP_ARROW' in k else 0) - (1.0 if 'DOWN_ARROW' in k else 0)
        i.grip_l = 1.0 if 'Q' in k else 0.0; i.grip_r = 1.0 if 'E' in k else 0.0
        i.arm_l = 'ONE' in k; i.arm_r = 'TWO' in k; i.crouch = 'C' in k
        i.run = 'LEFT_SHIFT' in k or 'RIGHT_SHIFT' in k
        i.fire |= self.fired; self.fired = set()
        p = read_pad(); self.pad = p
        if p:
            if abs(p['ly']) > abs(i.move): i.move = p['ly']
            if abs(p['lx']) > abs(i.turn): i.turn = p['lx']
            if p['rx'] or p['ry']: i.look_x, i.look_y = p['rx'], p['ry']
            i.grip_l = max(i.grip_l, p['lt']); i.grip_r = max(i.grip_r, p['rt'])
            b = p['b']; i.arm_l |= bool(b & XB['LB']); i.arm_r |= bool(b & XB['RB'])
            i.crouch |= bool(b & XB['DOWN']); i.run |= bool(b & XB['L3'])
            new = b & ~self.prev_b; self.prev_b = b
            for name, act in PAD_FIRE.items():
                if new & XB[name]: i.fire.add(act)
        return i

    def modal(self, ctx, ev):
        if not hasattr(self, 'fired'): self.fired = set()
        if ev.type == 'TIMER':
            inp = self.gather()
            if 'exit' in inp.fire: return self.finish(ctx)
            if 'record' in inp.fire: self.toggle_rec(ctx)
            self.core.tick(inp, 1 / 24)
            sc = ctx.scene
            if self.rec:
                sc.frame_current = self.rec['f']
                for b in self.core.keyed_bones():
                    p = self.ob.pose.bones[b]
                    p.keyframe_insert('rotation_euler', frame=self.rec['f'], group=b)
                    p.keyframe_insert('location', frame=self.rec['f'], group=b)
                self.rec['f'] += 1
            ctx.view_layer.update()
            _STATE['frame'] = sc.frame_current - 1; spring_step(sc)
            if self.core.follow and self.area:
                rv = self.area.spaces.active.region_3d
                tgt = self.ob.matrix_world @ Vector((self.core.pos.x, self.core.pos.y, 1.2))
                rv.view_location = rv.view_location.lerp(tgt, 0.12)
            src = (self.pad.get('name', 'Gamepad') if self.pad else 'Keyboard (no gamepad found)')
            _HUD['lines'] = [
                (('● REC  take frame %d' % self.rec['f']) if self.rec else 'DRIVE MODE   ' + src, (1, .3, .25, 1) if self.rec else (0.95, 0.82, 0.55, 1)),
                *[(t, (0.9, 0.9, 0.85, 1)) for t in control_lines(self.pad)]]
            if self.area: self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if ev.type in ('LEFTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MOUSEMOVE', 'TRACKPADPAN', 'TRACKPADZOOM'):
            return {'PASS_THROUGH'}      # orbit and zoom the view while driving
        if ev.value == 'PRESS':
            if ev.type in KEY_FIRE and not ev.is_repeat: self.fired.add(KEY_FIRE[ev.type])
            self.keys.add(ev.type)
        elif ev.value == 'RELEASE':
            self.keys.discard(ev.type)
        if ev.type == 'RIGHTMOUSE' and ev.value == 'PRESS': return self.finish(ctx)
        return {'RUNNING_MODAL'}

    def toggle_rec(self, ctx):
        ad = self.ob.animation_data
        if self.rec is None:
            n = 1 + sum(1 for a in bpy.data.actions if a.name.startswith('RM_take_'))
            act = bpy.data.actions.new(f'RM_take_{n:02d}'); act.use_fake_user = True
            act['robot_motion'] = 1; act['label'] = f'Drive take {n}'; act['order'] = 200 + n; act['loop'] = 0
            ad.action = act
            if hasattr(ad, 'action_slot') and act.slots: ad.action_slot = act.slots[0]
            self.rec = dict(act=act, f=1)
            for S in 'LR':
                self.ob.pose.bones[f'IK_foot.{S}'].keyframe_insert('["ik_fk"]', frame=1)
                self.ob.pose.bones[f'IK_hand.{S}'].keyframe_insert('["ik_fk"]', frame=1)
        else:
            act = self.rec['act']; end = self.rec['f'] - 1
            act.frame_range = (1, max(2, end)); act.use_frame_range = True
            ctx.scene.frame_start, ctx.scene.frame_end = 1, max(2, end)
            self.saved['action'] = act; self.saved['frame'] = 1
            ad.action = None; self.rec = None
            self.report({'INFO'}, f'{act.get("label")} saved to the motion library ({end} frames)')

    def finish(self, ctx):
        if self.rec: self.toggle_rec(ctx)
        ctx.window_manager.event_timer_remove(self.timer)
        if _HUD['h'] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_HUD['h'], 'WINDOW'); _HUD['h'] = None
        ob = self.ob; ad = ob.animation_data
        ad.action = self.saved['action']; ad.use_nla = self.saved['nla']; ob['springs_on'] = self.saved['springs']
        if ad.action and hasattr(ad, 'action_slot') and ad.action.slots: ad.action_slot = ad.action.slots[0]
        ctx.scene.frame_set(self.saved['frame'])
        if self.area: self.area.tag_redraw()
        return {'FINISHED'}


def control_lines(pad):
    if pad and pad.get('sony'):
        return ['Left stick: walk and turn   L3: run   Right stick: look',
                'L2 / R2: grip left / right   L1 / R1: raise arm   D-pad down: crouch',
                'Cross: wave   Circle: grab   Square: thumbs up   Triangle: celebrate',
                'D-pad left: look around   D-pad up: hatch   Options: power',
                'Create: record a take   Touchpad / R3: follow camera   PS: stop']
    return ['Move W/S or left stick   Turn A/D   Run Shift or L3   Look arrows or right stick',
            'Grip Q/E or triggers   Raise arm 1/2 or LB/RB   Crouch C or D-pad down',
            'Wave Space/A   Grab G/B   Thumbs up T/X   Celebrate V/Y   Look around L/D-pad left',
            'Hatch H/D-pad up   Power P/Start   Record R/Back   Follow cam F/R3   Stop Esc']


class ROBOT_PT_drive(bpy.types.Panel):
    bl_label = 'Drive mode (gamepad / keyboard)'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Robot'

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        lay = self.layout
        lay.operator('robot.drive', icon='PLAY', text='Drive the robot')
        p = read_pad()
        lay.label(text=(f'{p.get("name", "Gamepad")} connected' if p else 'No gamepad found: keyboard works. Plug in the DualSense (USB or Bluetooth)'),
                  icon='CHECKMARK' if p else 'INFO')
        col = lay.column(align=True)
        for t in control_lines(p if p else {'sony': True}):
            col.label(text=t)
        col.separator(); col.label(text='Keyboard: W A S D, Shift, arrows, Q E, 1 2, C, Space G T V L H P R F, Esc')
        takes = [a for a in bpy.data.actions if a.name.startswith('RM_take_')]
        if takes: lay.label(text=f'{len(takes)} recorded take(s) in the Motion library', icon='REC')


CLASSES = (ROBOT_OT_hold, ROBOT_OT_palette, ROBOT_OT_snap, ROBOT_OT_reset, ROBOT_OT_check, ROBOT_OT_bake_springs, ROBOT_OT_clear_springs, ROBOT_PT_panel,
           ROBOT_OT_key_pose, ROBOT_OT_mirror, ROBOT_OT_pose_preset, ROBOT_OT_motion, ROBOT_PT_easy, ROBOT_PT_motions, ROBOT_PT_look,
           ROBOT_OT_drive, ROBOT_PT_drive)


def register():
    for c in CLASSES:
        try: bpy.utils.register_class(c)
        except ValueError: pass
    hs = bpy.app.handlers.frame_change_post
    for h in [h for h in hs if getattr(h, '__name__', '') == 'spring_step']: hs.remove(h)
    hs.append(spring_step)


register()
