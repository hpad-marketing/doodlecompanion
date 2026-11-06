"""Put side-cast accessories on Bunny, Koala or Frog (what the library panel runs).

  import apply_accessory
  apply_accessory.wear('glasses_square')   # any id in ACCESSORIES; several can be worn at once
  apply_accessory.remove('glasses_square')
  apply_accessory.remove_all()

Accessories are built on the character in the open file, measured off its own face and head,
so one accessory fits every cast member. Building happens in the rig's rest pose; the rig file
itself is never changed. Each accessory lives in its own ACC_<id> collection.
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accessories as AC

INK_SRC = 'BUNNY_hand.L'


def _top_tree():
    """The top the character wears right now (an outfit body, else the hoodie), as a BVH."""
    tops = [o for c in bpy.data.collections if c.name.startswith('OUTFIT_') and c.name != 'OUTFIT_colliders'
            for o in c.objects if (o.get('ds_top') or o.name.endswith('_body'))]
    top = tops[0] if tops else bpy.data.objects.get('BUNNY_shirt')
    if top is None:
        return None
    _, tree = AC._eval_world(top)
    return tree


def worn():
    return [c.name[4:] for c in bpy.data.collections if c.name.startswith('ACC_')]


def refit():
    """Re-seat every worn accessory (run after changing outfits: ties sit on the new top)."""
    for aid in worn():
        wear(aid)


def remove(aid):
    c = bpy.data.collections.get('ACC_' + aid)
    if not c:
        return
    for ob in list(c.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(c)


def remove_all():
    for c in [c for c in bpy.data.collections if c.name.startswith('ACC_')]:
        remove(c.name[4:])


def wear(aid):
    if aid not in AC.ACCESSORIES:
        raise KeyError(f'unknown accessory {aid!r}; have {sorted(AC.ACCESSORIES)}')
    remove(aid)
    rig = bpy.data.objects['BUNNY_rig']
    src = bpy.data.objects[INK_SRC]
    sc = bpy.context.scene
    keep_pos, keep_frame = rig.data.pose_position, sc.frame_current
    rig.data.pose_position = 'REST'
    sc.frame_set(sc.frame_start)
    try:
        coll = bpy.data.collections.new('ACC_' + aid)
        (bpy.data.collections.get('Bunny') or sc.collection).children.link(coll)
        A = AC.anchors()
        AC.TOP = _top_tree()
        obs = AC.ACCESSORIES[aid][1](A, rig, src, coll)
        cam = sc.camera
        settings = bpy.data.objects['BUNNY_settings']
        from apply_outfit import _stroke_drivers
        for ob in coll.objects:
            for ms in ob.material_slots:
                _stroke_drivers(ms.material, cam, settings)
            AC.drive_strokes(ob, cam, settings)
            ob['ds_accessory'] = aid
    finally:
        rig.data.pose_position = keep_pos
        sc.frame_set(keep_frame)
    return coll
