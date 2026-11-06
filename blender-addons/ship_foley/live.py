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

def _step(rig, side, point, speed, surface, part="flat"):
    import bpy
    from . import place
    cam = bpy.context.scene.camera
    vol = place.distance_gain((cam.matrix_world.translation - point).length) if cam else 1.0
    prof = D.profile_for(rig)
    b_mat, size, hollow = "deck", 1.0, 0.0
    if surface is not None:
        tag = surface.get("sb_surface")
        b_mat = tag if tag in P.MATERIALS else P.classify(D._mat_name(surface))
        size = max(min(max(surface.dimensions), 1.2), 0.03)
        hollow = float(surface.get("foley_hollow", 0.0))
    mass = prof["mass_kg"] * prof["leg"]
    if part == "toe":            # the front of the sole rolling down: lighter, after the heel
        mass, speed = mass * 0.35, speed * 0.6
    hit = S.Hit("step", mass, max(float(speed), 0.05), prof["foot"], prof["foot_size"], b_mat, size, hollow,
                seed=(ord(side[0]) + int(abs(point.x) * 100) + len(part)) % 8)
    play_hit(hit, volume=vol)


def on_contact(rig, side, part, point, normal, speed, surface):
    """Ship Builder feet.ON_CONTACT: heel (or flat) at strike, then toe."""
    _step(rig, side, point, speed, surface, part)


def on_plant(rig, side, point, normal, speed, surface):
    """Older Ship Builder without ON_CONTACT: one sound per landing."""
    _step(rig, side, point, speed, surface)


def _feet_modules():
    import sys
    return [m for n, m in list(sys.modules.items()) if n.endswith("ship_builder.feet")]


def attach_walk():
    """Hook into any loaded Ship Builder; safe to call again. Uses heel/toe
    contacts when available, else one sound per plant (never both)."""
    hooked = 0
    for mod in _feet_modules():
        if hasattr(mod, "ON_CONTACT"):
            if on_contact not in mod.ON_CONTACT:
                mod.ON_CONTACT.append(on_contact)
            if hasattr(mod, "ON_PLANT"):
                while on_plant in mod.ON_PLANT:
                    mod.ON_PLANT.remove(on_plant)
            hooked += 1
        elif hasattr(mod, "ON_PLANT"):
            if on_plant not in mod.ON_PLANT:
                mod.ON_PLANT.append(on_plant)
            hooked += 1
    return hooked


def detach_walk():
    for mod in _feet_modules():
        for name, cb in (("ON_CONTACT", on_contact), ("ON_PLANT", on_plant)):
            lst = getattr(mod, name, None)
            while lst is not None and cb in lst:
                lst.remove(cb)
