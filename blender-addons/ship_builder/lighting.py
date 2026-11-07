"""Ship-wide lighting: render settings, space world, haze, cameras and moods.

Every practical light and glowing material is tagged with sb_light = role and
remembers its base energy/colour, so a mood can be switched and switched back.
"""
import math
import bpy
from mathutils import Vector

from . import mats as M

# role multipliers per mood: (energy multiplier, colour override or None)
MOODS = {
    "NORMAL": {"ceiling": (1.0, None), "practical": (1.0, None), "screen": (1.0, None), "alert": (0.0, None), "emergency": (0.0, None)},
    "NIGHT": {"ceiling": (0.12, (0.45, 0.55, 1.0)), "practical": (0.7, None), "screen": (1.0, None), "alert": (0.0, None), "emergency": (0.0, None)},
    "RED_ALERT": {"ceiling": (0.25, (1.0, 0.12, 0.08)), "practical": (0.5, None), "screen": (1.0, (1.0, 0.2, 0.15)), "alert": (1.0, None), "emergency": (0.0, None)},
    "POWER_CUT": {"ceiling": (0.0, None), "practical": (0.0, None), "screen": (0.05, None), "alert": (0.0, None), "emergency": (1.0, None)},
    "DOCKING": {"ceiling": (0.6, (1.0, 0.75, 0.45)), "practical": (1.0, None), "screen": (1.2, (1.0, 0.7, 0.3)), "alert": (0.35, (1.0, 0.6, 0.1)), "emergency": (0.0, None)},
}


def render_setup(scene=None, preview=False):
    sc = scene or bpy.context.scene
    sc.render.engine = "CYCLES"
    c = sc.cycles
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    c.device = "GPU"
                    break
            except TypeError:
                continue
    except Exception:
        pass
    c.samples = 64 if preview else 256
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.max_bounces = 10
    c.glossy_bounces = 6
    c.transmission_bounces = 8
    c.volume_bounces = 1
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.6
    c.volume_step_rate = 4.0 if preview else 1.5
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.render.film_transparent = False


def space_world(strength=0.03):
    """The outside: switchable views (views.py) seen through every window, a faint ambient on walls."""
    from . import views
    return views.build(bpy.context.scene, ambient=strength)


def haze(room, density=0.01):
    """A room-sized volume of faint dust so light strips and screens bloom."""
    import bmesh
    me = bpy.data.meshes.new("SB Haze")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"{room.name} Haze", me)
    room.root.objects.link(ob)
    ob.location = (0, room.D / 2, room.H / 2)
    ob.scale = (room.W - 0.1, room.D - 0.05, room.H - 0.1)
    me.materials.append(M.haze(f"SB Haze {room.name}", density))
    ob.visible_shadow = False
    ob["sb_haze"] = 1
    return ob


def camera(room, name="Wide master", lens=24, loc=None, target=None, fstop=4.0, portrait=True):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.display_size = 0.25            # small in the view, so walking past it never blacks out the set
    cam.sensor_fit = "AUTO"
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    ob = bpy.data.objects.new(f"{room.name} {name}", cam)
    room.root.objects.link(ob)
    ob.location = loc or (0, -2.2, 1.45)
    t = Vector(target or (0, room.D * 0.6, 1.0))
    d = t - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.dof.focus_distance = d.length
    ob["sb_cam"] = name
    sc = bpy.context.scene
    if sc.camera is None or not sc.camera.get("sb_cam"):
        sc.camera = ob
    return ob


def set_mood(mood, scene=None):
    sc = scene or bpy.context.scene
    table = MOODS[mood]
    for ob in sc.objects:
        role = ob.get("sb_light")
        if role is None or ob.type != "LIGHT":
            continue
        mul, col = table.get(role, (1.0, None))
        ob.data.energy = ob.get("sb_energy", ob.data.energy) * mul
        ob.data.color = col or tuple(ob.get("sb_color", ob.data.color))
        ob.hide_render = mul == 0
        if ob.get("sb_flicker"):
            from . import wear as Wr
            Wr.write_flicker(ob.data, "energy", ob.data.energy, Wr.flicker_keys(ob["sb_flicker"]))
    for m in bpy.data.materials:
        if not m.get("sb_emit"):
            continue
        role = m.get("sb_role", "practical")
        nd = m.node_tree.nodes.get("SB_Emit")
        if nd is None:
            continue
        mul, col = table.get(role, (1.0, None))
        base = m.get("sb_strength", 8.0)
        sock = nd.inputs["Emission Strength"]
        if not sock.is_linked:
            sock.default_value = base * mul
            if m.get("sb_flicker"):
                from . import wear as Wr
                Wr.write_flicker(sock, "default_value", base * mul, Wr.flicker_keys(m["sb_flicker"]))
        nd.inputs["Emission Color"].default_value = tuple(col or tuple(m.get("sb_color"))[:3]) + (1,)
    sc["sb_mood"] = mood


def camera_finish(scene=None, bloom=0.35, vignette=0.25, aberration=0.004):
    """Photographic finish in the compositor: soft bloom on bright fixtures,
    a touch of lens dispersion and a gentle vignette. Safe to call twice."""
    sc = scene or bpy.context.scene
    ng = bpy.data.node_groups.get("SB Camera Finish")
    if ng is None:
        ng = bpy.data.node_groups.new("SB Camera Finish", "CompositorNodeTree")
    ng.nodes.clear()
    if not any(s.name == "Image" and s.in_out == "OUTPUT" for s in ng.interface.items_tree):
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers")
    gl = N.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Threshold"].default_value = 1.0
    gl.inputs["Strength"].default_value = bloom
    gl.inputs["Size"].default_value = 0.6
    L.new(rl.outputs["Image"], gl.inputs["Image"])
    ld = N.new("CompositorNodeLensdist")
    try:
        ld.inputs["Dispersion"].default_value = aberration
        ld.inputs["Distortion"].default_value = -0.008
    except KeyError:
        pass
    L.new(gl.outputs["Image"], ld.inputs["Image"])
    el = N.new("CompositorNodeEllipseMask")
    el.inputs["Size"].default_value = (0.95, 1.1)
    bl = N.new("CompositorNodeBlur")
    try:
        bl.inputs["Size"].default_value = (300, 300)
    except (KeyError, TypeError):
        pass
    L.new(el.outputs["Mask"], bl.inputs["Image"])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs[3].default_value = 1.0 - vignette
    mr.inputs[4].default_value = 1.0
    L.new(bl.outputs["Image"], mr.inputs[0])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs[0].default_value = 1.0
    L.new(ld.outputs["Image"], mx.inputs[6])
    L.new(mr.outputs[0], mx.inputs[7])
    out = N.new("NodeGroupOutput")
    L.new(mx.outputs[2], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return ng
