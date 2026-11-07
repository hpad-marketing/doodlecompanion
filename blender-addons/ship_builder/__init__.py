"""Ship Builder: the droid sitcom's spaceship sets.

Window > Ship Studio opens the add-on's own window: a picture library of sets,
rooms, droids, motions, props, cameras, moods and hero ship presets beside one
big preview, the live scene and the timeline. Sets load as rooms docked door to
door; walk mode drives a droid through them with WASD or a DualSense.
"""
import bpy

from . import studio, walk, stations, rigui, cutaway

CLASSES = studio.CLASSES + walk.CLASSES + stations.CLASSES + rigui.CLASSES


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    studio.register()
    stations.register()
    cutaway.start()


def unregister():
    cutaway.stop()
    stations.unregister()
    studio.unregister()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
