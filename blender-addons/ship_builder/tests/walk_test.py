"""python walk_test.py -- <ship.blend>: drive a stand-in from the lounge to the bridge headless.
Checks: it arrives, every door on the way opens and closes behind it, and the droid never intersects anything."""
import sys, os, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a[0]))
from ship_builder import walk as Wk, ship as S, collide
sc = bpy.context.scene

class Ctx:  # pick_pawn only needs these
    active_object = None
    scene = sc
pawn = Wk.pick_pawn(Ctx)
info = S.info(sc)
lounge, corr, bridge = info['rooms']
pawn.location = (lounge['x'] + 1.5, 1.5, 0.0)
for c in S.door_controls().values():
    c['open'] = 0.0
bpy.context.view_layer.update()
w = Wk.Walker(sc, pawn)
print('PAWN r', round(w.radius, 2), 'h', round(w.height, 2))
doors = {d['id']: d for d in w.world.doors}
route = [Vector((lounge['x'] + lounge['W'] / 2 - 1.2, 1.5, 0)), Vector((bridge['x'] - bridge['W'] / 2 + 1.5, 1.5, 0)),
         Vector((bridge['x'] - 1.0, 2.0, 0))]
w.record(True)
dt, t, wp = 1 / 30, 0.0, 0
hits_all, opened, rooms_seen, cams_seen = [], {}, [], []
while wp < len(route) and t < 40:
    d = route[wp] - w.pos
    if d.length < 0.25:
        wp += 1
        continue
    right, fwd = w._view_axes()
    dn = d.normalized()
    w.tick(dt, Wk.Input(dn.dot(right), dn.dot(fwd)))
    t += dt
    if int(t / dt) % 60 == 0:
        print('  t', round(t, 1), 'pos', tuple(round(v, 2) for v in w.pos), 'z', round(w.z, 3), 'wp', wp)
    for k, dd in doors.items():
        opened[k] = max(opened.get(k, 0), dd['ctl']['open'])
    r = w._room_at(w.pos)
    if r and (not rooms_seen or rooms_seen[-1] != r):
        rooms_seen.append(r)
    if not cams_seen or cams_seen[-1] != sc.camera.name:
        cams_seen.append(sc.camera.name)
    if int(t / dt) % 6 == 0:
        bpy.context.view_layer.update()
        h = collide.audit_objects(list(sc.objects), only=[pawn])
        if h:
            hits_all.append((round(t, 2), h))
# keep ticking still so doors behind close
for _ in range(60):
    w.tick(dt, Wk.Input())
w.record(False)
print('ARRIVED', wp >= len(route), 'in', round(t, 1), 's at', tuple(round(v, 2) for v in w.pos))
print('ROOMS', rooms_seen)
print('CAMS', cams_seen)
print('DOORS max open', {k: round(v, 2) for k, v in opened.items()})
print('DOORS now', {k: round(d['ctl']['open'], 2) for k, d in doors.items()})
print('HITS', len(hits_all), hits_all[:5])
print('ACTION', pawn.animation_data.action.name if pawn.animation_data and pawn.animation_data.action else None, 'frame_end', sc.frame_end, 'markers', [(m.name, m.frame) for m in sc.timeline_markers])
if len(a) > 1:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a[1]))
