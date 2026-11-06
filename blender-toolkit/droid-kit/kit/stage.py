"""Studio + render helpers, importable after opening robot.blend."""
import bpy, math
from mathutils import Vector

def setup_studio(engine_gpu=True):
    sc = bpy.context.scene
    if 'Studio' in bpy.data.collections:
        return
    c = bpy.data.collections.new('Studio'); sc.collection.children.link(c)
    # cyc backdrop: floor + curved wall
    import bmesh
    bm = bmesh.new()
    prof = []
    for i in range(0, 13):
        a = math.radians(90 * i / 12)
        prof.append((0, 3.0 - 1.2 * math.sin(a) * 0 + (1.2 * (1 - math.cos(a))) * 0 + 0, 0))
    # simple: floor plane + vertical wall with bevelled corner
    pts = [(-8, y, 0) for y in (-8,)]
    me = bpy.data.meshes.new('cyc')
    verts, faces = [], []
    ys = [-8 + i * 0.5 for i in range(0, 27)]  # floor to y=2
    R = 1.5; y0 = 5.0
    line = [(y, 0.0) for y in ys]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        line.append((y0 + R * math.sin(a), R * (1 - math.cos(a))))
    line += [(y0 + R, R + 1.0 * k) for k in range(1, 7)]
    for x in (-10, 10):
        for (y, z) in line:
            verts.append((x, y, z))
    n = len(line)
    for i in range(n - 1):
        faces.append((i, n + i, n + i + 1, i + 1))   # wound so the floor normal points UP (collision_check reads inside/outside from it)
    me.from_pydata(verts, [], faces); me.update()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new('Studio_Cyc', me); c.objects.link(ob)
    m = bpy.data.materials.new('Studio_Floor')
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (0.62, 0.60, 0.57, 1); b.inputs['Roughness'].default_value = 0.8
    me.materials.append(m)
    # lights
    def area(name, loc, rot, energy, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size
        o = bpy.data.objects.new(name, L); c.objects.link(o); o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        return o
    area('Key', (3.5, -3.0, 4.0), (45, 0, 50), 900, 3.0)
    area('Fill', (-4.0, -2.5, 2.5), (65, 0, -60), 300, 4.0)
    area('Rim', (0.5, 4.0, 3.5), (-50, 0, 180), 500, 2.5)
    w = bpy.data.worlds.new('Studio_World'); sc.world = w
    bg = w.node_tree.nodes.get('Background')
    if bg: bg.inputs[0].default_value = (0.35, 0.36, 0.38, 1); bg.inputs[1].default_value = 0.6
    cam = bpy.data.cameras.new('Cam'); cam.lens = 50
    co = bpy.data.objects.new('Camera', cam); c.objects.link(co); sc.camera = co
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 1080
    sc.view_settings.view_transform = 'AgX'
    sc.cycles.device = 'GPU' if engine_gpu else 'CPU'

def aim(cam, loc, target, lens=50):
    cam.location = Vector(loc); cam.data.lens = lens
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def render(path, res=900, samples=48):
    sc = bpy.context.scene
    if res: sc.render.resolution_x = sc.render.resolution_y = res
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
