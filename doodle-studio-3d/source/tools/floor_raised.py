"""A set floor that sits above the rig's ground (a raised stage, a thick backdrop sweep):
floor collision must stand Bunny on it, and never move him when he already clears it.
Run: $DS3D_BPY tools/floor_raised.py   (prints ok/FAIL lines)"""
import math
import os
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'host', 'blender')
sys.path[:0] = [os.path.join(HERE, 'lib')]
import bpy  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'Bunny3D_v2.blend'))
import collision  # noqa: E402
import ds_map  # noqa: E402
import json  # noqa: E402

fails = 0


def ok(c, m):
    global fails
    print(('ok   ' if c else 'FAIL ') + m, flush=True)
    fails += 0 if c else 1


arm = bpy.data.objects['BUNNY_rig']
meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
settings = bpy.data.objects['BUNNY_settings']
objs = collision.objects()
obs = [objs[k] for k in collision.FLOOR_PARTS if k in objs]


def pose(v):
    ds_map.apply_pose(arm, meta['controls'], v, meta['S'], settings)
    bpy.context.view_layer.update()


def stroke():
    return collision.drawn_zmin(obs)


# no set: standing is untouched, a sunk pose comes up to z = 0
pose({})
z0 = stroke()
ok(collision.floor_lift(arm, objs) == 0.0, f'standing on the bare ground is never moved (stroke {z0:.4f})')
pose({'bodyY': 40})
collision.floor_lift(arm, objs)
ok(0 <= stroke() < 0.003, f'a sunk pose comes up onto the ground ({stroke():.4f})')

# a floor 4 cm up (thick sweep): he stands on it, ink included
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0.04))
floor = bpy.context.active_object
floor.name = 'SET_test:floor'
pose({})
collision.floor_lift(arm, objs)
ok(0.04 <= stroke() < 0.043, f'standing on a floor 4 cm up: the stroke rests on it ({stroke():.4f})')
pose({'bodyY': 25, 'legL': 70, 'kneeL': 120, 'kneeR': 90})
collision.floor_lift(arm, objs)
ok(0.04 <= stroke() < 0.043, f'a kneel on the raised floor stays on top of it ({stroke():.4f})')
ok(abs(collision.ground_z(arm, obs) - 0.04) < 1e-4, 'the floor is found under the feet')

# a table top 70 cm up nearby is not a floor
floor.location.z = 0.7
pose({})
bpy.context.view_layer.update()
ok(abs(collision.ground_z(arm, obs)) < 1e-4, 'a surface far above the ground (a table) is not taken for the floor')
ok(collision.floor_lift(arm, objs) == 0.0, 'and he is not lifted onto it')

# a small prop under the feet (a bench foot, a kerb stone) is scenery, not the floor
floor.location.z = 0.0
bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0, 0, -0.27))   # top 3 cm up, under both feet
stone = bpy.context.active_object
stone.name = 'SET_test:stone'
pose({})
bpy.context.view_layer.update()
ok(abs(collision.ground_z(arm, obs)) < 1e-4, 'a small prop under the feet is not taken for the floor')
bpy.data.objects.remove(stone)

# the set's ink outline floating over the floor (an outline hull) is never the floor
ink = bpy.data.materials.get('DS_ink_outline') or bpy.data.materials.new('DS_ink_outline')
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0.05))
hull = bpy.context.active_object
hull.name = 'SET_test:hull'
hull.data.materials.append(ink)
bpy.context.view_layer.update()
ok(abs(collision.ground_z(arm, obs)) < 1e-4, "a set's outline hull above the floor is not taken for the floor")
bpy.data.objects.remove(hull)

# a stage 15 cm up is the floor you see: he stands on it
floor.location.z = 0.15
pose({})
collision.floor_lift(arm, objs)
ok(0.15 <= stroke() < 0.153, f'a stage 15 cm up is the floor: the stroke rests on it ({stroke():.4f})')

sys.exit(1 if fails else 0)
