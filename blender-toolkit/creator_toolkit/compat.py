"""Small helpers that hide differences between Blender 4.2 - 5.x."""
import bpy

V = bpy.app.version


def eevee_id():
    ids = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    return 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'


def strips(scene):
    se = scene.sequence_editor or scene.sequence_editor_create()
    return se.strips if hasattr(se, 'strips') else se.sequences


def strips_all(scene):
    se = scene.sequence_editor
    if not se:
        return []
    return list(se.strips_all if hasattr(se, 'strips_all') else se.sequences_all)


def action_fcurves(action, id_data=None):
    """Return the F-Curves of an action (layered actions in 4.4+, legacy before)."""
    if action is None:
        return []
    if hasattr(action, 'layers') and len(getattr(action, 'layers', [])):
        out = []
        slot = None
        if id_data is not None and id_data.animation_data:
            slot = getattr(id_data.animation_data, 'action_slot', None)
        for layer in action.layers:
            for strip in layer.strips:
                bags = strip.channelbags if hasattr(strip, 'channelbags') else []
                for bag in bags:
                    if slot is None or bag.slot == slot:
                        out.extend(bag.fcurves)
        if out:
            return out
    return list(getattr(action, 'fcurves', []))


def fcurves_of(obj):
    ad = getattr(obj, 'animation_data', None)
    return action_fcurves(ad.action, obj) if ad and ad.action else []


def link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def node_group_new(name, kind='GeometryNodeTree'):
    return bpy.data.node_groups.new(name, kind)


def group_socket(tree, name, in_out, socket_type, default=None, min_value=None, max_value=None):
    s = tree.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    if default is not None and hasattr(s, 'default_value'):
        s.default_value = default
    if min_value is not None and hasattr(s, 'min_value'):
        s.min_value = min_value
    if max_value is not None and hasattr(s, 'max_value'):
        s.max_value = max_value
    return s


def gp_data_new(name):
    """Grease Pencil data block (v3 on 4.3+)."""
    coll = bpy.data.grease_pencils_v3 if hasattr(bpy.data, 'grease_pencils_v3') else bpy.data.grease_pencils
    return coll.new(name)


def gp_object_type():
    return 'GREASEPENCIL' if V >= (4, 3, 0) else 'GPENCIL'
