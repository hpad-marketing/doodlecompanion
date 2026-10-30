"""Small shims so the same scripts run on Blender 4.4/4.5 and 5.x.
5.0 removed Action.fcurves (layered actions) and SequenceEditor.sequences."""


def fcurves(idb):
    """The F-curve collection animating this ID (supports iteration and .remove)."""
    ad = getattr(idb, 'animation_data', None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, 'fcurves'):
        return act.fcurves
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
    return cb.fcurves if cb else []


def strips(sequence_editor):
    se = sequence_editor
    return se.strips if hasattr(se, 'strips') else se.sequences


def video_output(render):
    """Switch the render output to FFmpeg video (5.0 first asks for the media type)."""
    if hasattr(render.image_settings, 'media_type'):
        render.image_settings.media_type = 'VIDEO'
    render.image_settings.file_format = 'FFMPEG'
