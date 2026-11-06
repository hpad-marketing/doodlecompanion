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
    """Near-black space with faint stars, so windows show stars and walls get no fake fill."""
    w = bpy.data.worlds.get("SB Space") or bpy.data.worlds.new("SB Space")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 420
    nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs[1].default_value = 0.035
    mr.inputs[2].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], mr.inputs[0])
    neb = nt.nodes.new("ShaderNodeTexNoise")
    neb.inputs["Scale"].default_value = 1.4
    neb.inputs["Detail"].default_value = 8
    nt.links.new(tc.outputs["Generated"], neb.inputs["Vector"])
    nmr = nt.nodes.new("ShaderNodeMapRange")
    nmr.inputs[1].default_value = 0.55
    nmr.inputs[2].default_value = 0.8
    nmr.inputs[4].default_value = 0.02
    nt.links.new(neb.outputs[0], nmr.inputs[0])
    nebc = nt.nodes.new("ShaderNodeMix")
    nebc.data_type = "RGBA"
    nebc.inputs[6].default_value = (0.0, 0.0, 0.0, 1)
    nebc.inputs[7].default_value = (0.25, 0.1, 0.45, 1)
    nt.links.new(nmr.outputs[0], nebc.inputs[0])
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.inputs[0].default_value = 1.0
    nt.links.new(nebc.outputs[2], add.inputs[6])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = 4.0
    nt.links.new(mr.outputs[0], st.inputs[0])
    nt.links.new(st.outputs[0], add.inputs[7])
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(add.outputs[2], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    # camera sees space, everything else gets only a faint ambient
    lp = nt.nodes.new("ShaderNodeLightPath")
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = (0.5, 0.55, 0.65, 1)
    amb.inputs["Strength"].default_value = strength
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(bg.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = w
    return w


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
