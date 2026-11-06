"""Command centre: the wide front viewport, a console arc under it, side stations,
a hologram star-map table in the middle and two chairs nobody needs."""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

from .. import kit as K
from .. import mats as M
from .. import lighting as Li
from . import common as C
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Command centre", "size": (9.0, 7.0, 3.6), "doors": {"left": 1.5, "right": 4.0}}


def keypad(room, loc, rot, cols=10, rows=3, key=0.022, gap=0.006, mat=None):
    """One keyboard object: a key repeated with array modifiers (cheap, detailed)."""
    k = K.box("Keys", (key, key, 0.008), loc, mat or room.pal["plastic_grey"], room.dress, bevel=0.002, segs=2)
    k.rotation_euler = rot
    for axis, n in ((0, cols), (1, rows)):
        a = k.modifiers.new(f"Array{axis}", "ARRAY")
        a.count = n
        a.use_relative_offset = False
        a.use_constant_offset = True
        off = [0, 0, 0]
        off[axis] = key + gap
        a.constant_offset_displace = off
    # move array modifiers before the bevel so every key is bevelled
    for m in [m for m in k.modifiers if m.type == "ARRAY"]:
        with bpy.context.temp_override(object=k):
            bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)
    return k


def lever(room, loc, angle=20):
    base = K.box("Lever Base", (0.06, 0.12, 0.03), loc, room.pal["dark_steel"], room.dress, bevel=0.005)
    rod = K.cyl("Lever", 0.006, 0.12, (loc[0], loc[1] + 0.02 * math.sin(math.radians(angle)), loc[2] + 0.07), room.pal["steel"], room.dress, verts=12, rot=(math.radians(angle), 0, 0))
    K.cyl("Lever Knob", 0.016, 0.03, (loc[0], loc[1] + 0.06 * math.sin(math.radians(angle)), loc[2] + 0.13), M.plastic("SB Knob Red", (0.45, 0.05, 0.03, 1), 0.3), room.dress, verts=20, rot=(math.radians(angle), 0, 0))
    return base


def console(room, x, y, width, yaw=0.0, screens=2, color=(0.3, 0.85, 1.0, 1)):
    """A pilot console: body, angled desk with keyboards and levers, two raised screens."""
    pal = room.pal
    R = Matrix.Rotation(yaw, 4, "Z")
    o = Vector((x, y, 0))

    def P(dx, dy, dz):
        return o + (R @ Vector((dx, dy, dz)))

    rz = (0, 0, yaw)
    body = K.box("Console Body", (width, 0.7, 0.75), P(0, 0, 0.375), pal["hull"], room.dress, bevel=0.02, rot=rz)
    K.rigid(body, passive=True, shape="BOX")
    K.box("Console Kick", (width - 0.1, 0.6, 0.08), P(0, -0.04, 0.04), pal["dark_steel"], room.dress, bevel=0.006, rot=rz)
    desk = K.box("Console Desk", (width + 0.06, 0.55, 0.05), P(0, -0.12, 0.8), pal["panel"], room.dress, bevel=0.012, rot=(math.radians(-12), 0, yaw))
    K.rigid(desk, passive=True, shape="BOX")
    tilt = (math.radians(-12), 0, yaw)
    n_kb = max(1, int(width // 0.9))
    for i in range(n_kb):
        dx = -width / 2 + width * (i + 0.5) / n_kb
        keypad(room, P(dx - 0.13, -0.25, 0.83), tilt, 10, 3)
        lever(room, P(dx + 0.22, -0.2, 0.83), 25 + 15 * i)
        lever(room, P(dx + 0.3, -0.2, 0.83), 10)
        # status lights
        for k in range(6):
            mat = M.emissive(f"SB Status {k % 3}", [(0.3, 1.0, 0.4, 1), (1.0, 0.6, 0.1, 1), (0.3, 0.8, 1.0, 1)][k % 3], 6)
            K.cyl("Status LED", 0.007, 0.006, P(dx - 0.3 + k * 0.035, -0.02, 0.86), mat, room.dress, verts=12, rot=tilt, bevel=0)
    # raised screen stand
    for i in range(screens):
        dx = -width / 2 + width * (i + 0.5) / screens
        K.box("Screen Arm", (0.06, 0.06, 0.4), P(dx, 0.22, 1.0), pal["dark_steel"], room.dress, bevel=0.006, rot=rz)
        sw = min(0.8, width / screens - 0.1)
        c = P(dx, 0.2, 1.4)
        u = R @ Vector((1, 0, 0))
        n = R @ Vector((0, -math.cos(math.radians(15)), math.sin(math.radians(15))))
        v = n.cross(u).normalized()
        K.screen(room, c, u, v, n, sw, sw * 0.56, color if i % 2 == 0 else (1.0, 0.65, 0.2, 1), "ui", light=True, name="Console Screen", strength=1.6)
    # cable loom underneath
    K.cable(room, P(-width / 2 + 0.2, 0.3, 0.1), P(width / 2 - 0.2, 0.3, 0.1), 0.0, 0.02)
    return body


def chair(room, x, y, yaw=0.0):
    pal = room.pal
    K.cyl("Chair Base", 0.28, 0.04, (x, y, 0.02), pal["dark_steel"], room.dress, verts=40, bevel=0.01)
    K.cyl("Chair Post", 0.045, 0.42, (x, y, 0.25), pal["steel"], room.dress, verts=24)
    seat = K.rounded("Chair Seat", (0.5, 0.48, 0.1), (x, y, 0.5), M.fabric("SB Chair Vinyl", (0.04, 0.04, 0.045, 1), 0.15), room.dress, wrinkle=0.006)
    seat.rotation_euler = (0, 0, yaw)
    bx, by = x - 0.22 * math.sin(yaw), y + 0.22 * math.cos(yaw)
    back = K.rounded("Chair Back", (0.46, 0.09, 0.55), (bx, by, 0.85), M.fabric("SB Chair Vinyl", (0.04, 0.04, 0.045, 1), 0.15), room.dress, wrinkle=0.006)
    back.rotation_euler = (math.radians(-8), 0, yaw)
    for sx in (-1, 1):
        ax, ay = x + sx * 0.27 * math.cos(yaw), y + sx * 0.27 * math.sin(yaw)
        K.box("Chair Arm", (0.05, 0.38, 0.04), (ax, ay, 0.68), pal["hull"], room.dress, bevel=0.01, rot=(0, 0, yaw))
    for o in (seat, back):
        K.rigid(o, passive=True, shape="CONVEX_HULL")


def hologram(room, x, y, z, r=0.42):
    pal = room.pal
    K.cyl("Holo Base", 0.75, 0.82, (x, y, 0.41), pal["hull"], room.dress, verts=64, bevel=0.02)
    K.cyl("Holo Rim", 0.8, 0.05, (x, y, 0.845), pal["steel"], room.dress, verts=64, bevel=0.01)
    ring = K.cyl("Holo Emitter", 0.6, 0.02, (x, y, 0.88), M.emissive("SB Holo Emitter", (0.3, 0.85, 1.0, 1), 1.2), room.dress, verts=64, bevel=0.004)
    ring["sb_light"] = "screen"
    # wireframe planet with a ring of orbit marks
    me = bpy.data.meshes.new("Holo Planet")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    bm.to_mesh(me)
    bm.free()
    hm, new = M._get("SB Hologram")
    if new:
        g = M.G(hm)
        em = g.node("ShaderNodeEmission")
        em.inputs["Color"].default_value = (0.3, 0.85, 1.0, 1)
        em.inputs["Strength"].default_value = 1.6
        tr = g.node("ShaderNodeBsdfTransparent")
        mix = g.node("ShaderNodeMixShader")
        mix.inputs[0].default_value = 0.45
        g.link(tr.outputs[0], mix.inputs[1])
        g.link(em.outputs[0], mix.inputs[2])
        g.out(mix)
        hm["sb_emit"] = 1
        hm["sb_role"] = "screen"
        hm["sb_color"] = [0.3, 0.85, 1.0, 1]
        hm["sb_strength"] = 1.6
    me.materials.append(hm)
    ob = bpy.data.objects.new("Holo Planet", me)
    room.dress.objects.link(ob)
    ob.location = (x, y, z)
    w = ob.modifiers.new("Wire", "WIREFRAME")
    w.thickness = 0.004
    ob.visible_shadow = False
    for k in range(3):
        o = K.cyl("Holo Orbit", r * (1.4 + 0.25 * k), 0.003, (x, y, z), hm, room.dress, verts=96, rot=(math.radians(70 + 8 * k), math.radians(10 * k), 0), bevel=0)
        o.modifiers.new("Wire", "WIREFRAME").thickness = 0.003
        o.visible_shadow = False
    # beam cone of light from emitter
    K.point_glow(room, (x, y, 1.0), (0.3, 0.85, 1.0), 25, 0.3, role="screen")
    return ob


def build(room_name="Command centre", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    pal = room.pal
    # wide viewport: three panes across the back wall
    dr = INFO["doors"]
    C.shell(room, back_holes=[(1.0, 8.0, 0.9, 3.15)], left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(1.0, 0.75), chamfer=0.6)
    for i, cx in enumerate((-7 / 3, 0.0, 7 / 3)):  # three panes exactly filling the 7 m x 2.25 m opening
        C.window(room, (cx, D, 0.9 + 1.125), 7 / 3 - 0.244, 2.25 - 0.244, (0, -1, 0), frame=0.12, name=f"Viewport {i}", tilt=-6)
    K.ceiling(room, light_rows=2, color=(0.75, 0.85, 1.0, 1), power=18, cols=3, cove=0.5, cove_back=False, cove_color=(0.35, 0.8, 1.0, 1), cove_power=4)
    for sx in (-1, 1):
        K.light_strip(room, (sx * 1.25, D / 2 - 0.3, 0.045), D - 1.4, "Y", (0, 0, 1), (0.3, 0.8, 1.0, 1), 4, role="practical", width=0.02)
    # console arc under the viewport
    for cx, cy, cw, yaw in ((-2.6, D - 1.0, 2.0, 12), (0.0, D - 0.85, 2.4, 0), (2.6, D - 1.0, 2.0, -12)):
        with K.piece(room, "Console", 0.03, 2):
            console(room, cx, cy, cw, math.radians(yaw), 2)
    with K.piece(room, "Chair", 0.15, 25):
        chair(room, -0.6, D - 2.0, math.radians(8))
    with K.piece(room, "Chair", 0.15, 25):
        chair(room, 0.8, D - 2.1, math.radians(-14))
    with K.piece(room, "Holo table", 0.03, 4):
        hologram(room, 0.0, 2.6, 1.55)
    # side stations: star map on the left, system wall on the right
    K.screen(room, (-W / 2 + 0.04, 4.35, 1.75), (0, 1, 0), (0, 0, 1), (1, 0, 0), 2.0, 1.1, (0.35, 0.8, 1.0, 1), "map", name="Star Map", strength=1.4)
    with K.piece(room, "Map console", 0.03, 2):
        console(room, -W / 2 + 0.45, 4.35, 1.9, math.radians(-90), 0, (0.35, 0.8, 1.0, 1))
    for k, (yy, zz) in enumerate(((1.2, 1.7), (1.83, 1.7), (1.515, 2.2))):
        K.screen(room, (W / 2 - 0.04, yy, zz), (0, -1, 0), (0, 0, 1), (-1, 0, 0), 0.55, 0.4, [(1.0, 0.65, 0.2, 1), (0.4, 1.0, 0.5, 1), (1.0, 0.3, 0.2, 1)][k], "ui", name="System Screen", strength=1.4)
    # doors: left to the corridor, right onward (blank until a room docks there)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    # overhead conduits
    K.pipe(room, [(-W / 2 + 0.9, D - 0.075, H - 0.25), (-W / 2 + 1.0, D - 0.3, H - 0.25), (W / 2 - 1.0, D - 0.3, H - 0.25), (W / 2 - 0.9, D - 0.075, H - 0.25)], 0.04)
    for k in range(6):
        K.cable(room, (-3.5 + k * 1.3, D - 0.35, H - 0.3), (-2.8 + k * 1.3, D - 0.35, H - 0.3), 0.22, 0.012)
    K.stencil(room, "BRIDGE - DECK 1", (-2.3, D - 0.035, 3.33), (math.radians(90), 0, 0), 0.11)
    K.stencil(room, "MISSION: NONE", (2.6, D - 1.36, 0.55), (math.radians(90), 0, math.radians(-12)), 0.05)
    # loose props on the consoles
    from .lounge import mug, datapad
    mug(room, (0.75, D - 1.05, 0.86), M.plastic("SB Mug Cream", (0.62, 0.58, 0.48, 1), 0.3), "Bridge Mug")
    datapad(room, (-2.4, D - 1.25, 0.88), 0.4)
    # alert beacons
    for x0 in (-W / 2 + 0.6, W / 2 - 0.6):
        K.cyl("Alert Beacon", 0.06, 0.1, (x0 * 0.72, D - 0.12, H - 0.25), M.emissive("SB Alert Lens", (1.0, 0.08, 0.05, 1), 0.0), room.dress, verts=24, rot=(math.radians(90), 0, 0))
        K.point_glow(room, (x0 * 0.72, D - 0.25, H - 0.25), (1.0, 0.1, 0.05), 60, 0.05, role="alert")
        K.point_glow(room, (x0, 0.6, 0.25), (1.0, 0.35, 0.1), 12, 0.03, role="emergency")
    C.planet(room, loc=(-30, 140, 4), radius=26, color=(0.22, 0.35, 0.55, 1), ring=False)
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 24, (0.6, -1.2, 1.5), (0.0, D * 0.7, 1.3), 5.6)
    Li.camera(room, "Console shoulder", 35, (1.6, D - 2.6, 1.45), (0.0, D - 0.6, 1.3), 2.8)
    Li.camera(room, "Holo table", 40, (1.8, 1.0, 1.3), (0.0, 2.6, 1.3), 2.0)
    room.arch = A.detail(room, seed=wear_seed, accent=(0.35, 0.8, 1.0, 1), frame_step=2.3, frame_avoid=[(-3.6, 3.6)],
                         walkway=(-1.2, 1.2, 0.3, D - 1.5))
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    return room
