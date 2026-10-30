"""Use the graphics card for everything Blender can run on it.

EEVEE (the library's look) always draws on the GPU. Cycles picks its device from
the preferences, so this switches Cycles to the best backend the card supports
(OptiX, then CUDA, HIP, oneAPI, Metal), ticks every GPU, and sets every scene to
render on it. Viewport, previews, thumbnails, bakes and final renders all follow.
Cloth, rigid body and hoodie physics have no GPU path in Blender, so they stay on
the CPU (they are cached, so they only cost time once).
"""
import bpy
from bpy.app.handlers import persistent

ORDER = ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL')


def enable():
    """Turn on GPU compute in the preferences. Returns the backend used, or None."""
    addon = bpy.context.preferences.addons.get('cycles')
    if addon is None:
        return None
    cp = addon.preferences
    for kind in ORDER:
        try:
            cp.compute_device_type = kind
        except TypeError:
            continue  # this build has no such backend
        cp.refresh_devices()
        gpus = [d for d in cp.devices if d.type == kind]
        if not gpus:
            continue
        for d in cp.devices:
            d.use = d.type == kind
        return kind
    cp.compute_device_type = 'NONE'
    return None


def apply_to_scenes():
    for sc in bpy.data.scenes:
        cy = getattr(sc, 'cycles', None)
        if cy is None:
            continue
        cy.device = 'GPU'
        if hasattr(cy, 'denoising_use_gpu'):
            cy.denoising_use_gpu = True


@persistent
def on_load(_dummy=None):
    if enable():
        apply_to_scenes()


def register():
    try:
        kind = enable()
        print('Doodle Library: GPU compute', kind or 'not available (CPU)')
    except Exception as e:
        print('Doodle Library: could not switch on the GPU:', e)
    bpy.app.handlers.load_post.append(on_load)


def unregister():
    if on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load)
