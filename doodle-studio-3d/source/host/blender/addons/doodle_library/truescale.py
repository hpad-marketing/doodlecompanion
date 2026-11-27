"""Prop sizes by use (user decision, 2026-11-03: "Mix by use").

Held props keep the cartoon size, so they read in Bunny's mitten. Props placed in the room
use true scale (0.9 x real size beside a 1.02 m Bunny), like the sets, so a room layout looks
real.

The 90 hand props from the 360 prop library are modelled at the cartoon size (squeezed toward
20-40 cm: a mug is 17 cm, a guitar 47 cm). Placed in the room they grow or shrink to the real
size in REAL_CM (the object's longest side). Asset-pack props are modelled at true scale; held,
they take the same cartoon curve the hand props were drawn with (HELD_CM). Scaling is about the
origin, which is the researched grip point, so a grip stays in the hand. The scale lives on the
object (never baked into the mesh), so holding and letting go switch it back and forth.
The helpers above apply() are pure Python: preview_export.py loads this file directly.
"""
WORLD = 0.9          # library scale: 0.9 x real size (doodle-library-blender rule)

REAL_CM = {
    'apple': 8, 'banana': 20, 'basketball': 24, 'bat': 84, 'book': 23, 'bowl': 16, 'broom': 130,
    'brush': 20, 'bulb': 11, 'burger': 11, 'cake': 22, 'calculator': 15, 'camera': 13, 'candle': 15,
    'card': 9, 'carrot': 18, 'chest': 50, 'clipboard': 32, 'controller': 15, 'cookie': 8, 'crown': 18,
    'cupcake': 7, 'donut': 9, 'drumsticks': 41, 'duck': 10, 'dumbbell': 30, 'envelope': 22,
    'flashlight': 20, 'flask': 20, 'flower': 40, 'fork': 19, 'frisbee': 27, 'gift': 25, 'glass': 14,
    'globe': 40, 'guitar': 100, 'hammer': 30, 'headphones': 20, 'hourglass': 15, 'icecream': 18,
    'lantern': 30, 'laptop': 33, 'letter': 28, 'lollipop': 25, 'magnifier': 22, 'maracas': 24,
    'medal': 35, 'mic': 18, 'money': 16, 'mug': 10, 'newspaper': 40, 'paddle': 26, 'palette': 30,
    'pan': 45, 'partyhat': 18, 'pencil': 19, 'pizza': 18, 'plant': 25, 'popcorn': 20, 'popper': 15,
    'potion': 15, 'quill': 30, 'racket': 68, 'remote': 18, 'ruler': 30, 'scissors': 20,
    'screwdriver': 22, 'scroll': 35, 'selfie': 70, 'shield': 60, 'shoppingbag': 40, 'shovel': 110,
    'sign': 90, 'skateboard': 80, 'spatula': 32, 'suitcase': 55, 'sword': 90, 'tablet': 25,
    'tambourine': 25, 'teacup': 11, 'teddy': 30, 'telescope': 40, 'testtube': 15, 'toothbrush': 19,
    'torch': 40, 'trumpet': 50, 'wallet': 11, 'wand': 35, 'watch': 12, 'wrench': 25,
}


def key(item_id):
    return item_id[5:] if str(item_id).startswith('prop-') else str(item_id)


def factor(item_id, longest_m):
    """Scale that brings a prop whose longest side is longest_m to true scale (1.0 = leave it)."""
    real = REAL_CM.get(key(item_id))
    if not real or not longest_m or longest_m <= 0:
        return 1.0
    k = real / 100.0 * WORLD / longest_m
    return 1.0 if abs(k - 1.0) < 0.02 else k


def held_cm(true_cm):
    """Cartoon size for a held prop, fitted to the 90 hand props (mug 9 -> 17 cm, guitar 90 -> 47)."""
    return 26.0 * (max(true_cm, 0.1) / 26.0) ** 0.4


def _longest(ob):
    """Longest side of the mesh as modelled: its own vertices, so the ink hull and crease tubes
    the style modifiers add (and the object scale) are left out."""
    vs = getattr(getattr(ob, 'data', None), 'vertices', None)
    if vs is not None and len(vs):
        return max(max(v.co[i] for v in vs) - min(v.co[i] for v in vs) for i in range(3))
    bb = ob.bound_box
    return max(max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3))


def use_factor(ob, held, pack=False):
    """Object scale for this prop when held (True) or placed in the room (False)."""
    pid = str(ob.get('dsl_id', ''))
    L = _longest(ob)
    if pid.startswith('prop-') and key(pid) in REAL_CM:
        return 1.0 if held else factor(pid, L)
    if pack and held and L > 0:   # pack props are true scale as modelled
        k = held_cm(L * 100) / (L * 100)
        return 1.0 if abs(k - 1.0) < 0.02 else k
    return 1.0


def set_use(ob, held, pack=False):
    """Size a prop for how it is used. pack: an asset-pack hand prop (it has a grip in its
    library row). Returns the object scale it now has."""
    pid = str(ob.get('dsl_id', ''))
    if ob.type != 'MESH' or not (pack or (pid.startswith('prop-') and key(pid) in REAL_CM)):
        return 1.0
    k = use_factor(ob, held, pack)
    ob.scale = (k, k, k)
    ob['dsl_use'] = 'held' if held else 'room'
    ob['dsl_prop_scale'] = k   # saves and the render bridge see the size choice
    import bpy
    bpy.context.view_layer.update()   # grips read matrix_world straight after
    return k
