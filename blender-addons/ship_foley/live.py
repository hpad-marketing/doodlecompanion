"""Live contact sounds while a droid is driven in walk mode.

    from ship_foley import live
    live.contact(armature, "foot.L", speed=0.5, surface=floor_object)

Plays at once through Blender's audio device. Same physics as the bake, so
what you hear while driving is what the baked shot will sound like.
"""
import numpy as np

from . import synth as S
from . import profiles as P
from . import detect as D

_dev = None
_cache = {}


def _device():
    global _dev
    if _dev is None:
        import aud
        _dev = aud.Device()
    return _dev


def play_hit(hit, volume=1.0, pan=0.0):
    import aud
    key = hit.key()
    snd = _cache.get(key)
    if snd is None:
        data = S.render(hit, room_wet=0.1)
        snd = aud.Sound.buffer(np.ascontiguousarray(data.reshape(-1, 1)), S.RATE)
        if len(_cache) > 256:
            _cache.clear()
        _cache[key] = snd
    return _device().play(snd.volume(float(volume)))


def contact(arm, limb, speed, surface=None, material=None, seed=0):
    """One touch by a droid. limb: 'foot.L', 'foot.R', 'hand.L', 'hand.R', 'body'."""
    prof = D.profile_for(arm)
    foot = limb.startswith("foot") or limb == "body"
    mass = prof["mass_kg"] * (prof["leg"] if foot else prof["arm"])
    b_mat = material or (P.classify(D._mat_name(surface)) if surface is not None else "deck")
    size = max(min(max(surface.dimensions), 1.2), 0.03) if surface is not None else 1.0
    hit = S.Hit("step" if foot else "grab", mass, speed,
                prof["foot"] if foot else prof["hand"], prof["foot_size"] if foot else prof["hand_size"],
                b_mat, size, seed=seed % 8)
    return play_hit(hit)


# --- walk mode: Ship Builder calls feet.ON_PLANT on every landing ------------

def on_plant(rig, side, point, normal, speed, surface):
    """Ship Builder foot-plant callback: (rig, "L"/"R", point, normal, speed, surface)."""
    import bpy
    from . import place
    cam = bpy.context.scene.camera
    vol = place.distance_gain((cam.matrix_world.translation - point).length) if cam else 1.0
    prof = D.profile_for(rig)
    b_mat = "deck"
    if surface is not None:
        b_mat = surface.get("sb_surface") if surface.get("sb_surface") in P.MATERIALS else P.classify(D._mat_name(surface))
    size = max(min(max(surface.dimensions), 1.2), 0.03) if surface is not None else 1.0
    hit = S.Hit("step", prof["mass_kg"] * prof["leg"], max(float(speed), 0.05), prof["foot"],
                prof["foot_size"], b_mat, size, seed=(ord(side[0]) + int(abs(point.x) * 100)) % 8)
    play_hit(hit, volume=vol)


def attach_walk():
    """Hook into any loaded Ship Builder; safe to call again."""
    import sys
    hooked = 0
    for name, mod in list(sys.modules.items()):
        if name.endswith("ship_builder.feet") and hasattr(mod, "ON_PLANT"):
            if on_plant not in mod.ON_PLANT:
                mod.ON_PLANT.append(on_plant)
            hooked += 1
    return hooked


def detach_walk():
    import sys
    for name, mod in list(sys.modules.items()):
        if name.endswith("ship_builder.feet") and hasattr(mod, "ON_PLANT"):
            while on_plant in mod.ON_PLANT:
                mod.ON_PLANT.remove(on_plant)
