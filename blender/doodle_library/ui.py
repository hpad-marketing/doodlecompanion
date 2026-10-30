"""Panels in the 3D View sidebar (tab "Doodle"): Library, Background, Look."""
import os

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from . import index, paths, sets, style

_previews = None
_enum_cache = {}
LIB_CATS = [c for c in index.CATEGORIES if c[0] != 'set']


# ------------------------------------------------------------------ previews
def icon_for(item):
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
    rel = item.get('preview')
    if not rel:
        return 0
    if item['id'] not in _previews:
        p = paths.lib_path(rel)
        if not os.path.exists(p):
            return 0
        _previews.load(item['id'], p, 'IMAGE')
    return _previews[item['id']].icon_id


# ------------------------------------------------------------------ list state
class DSLItem(bpy.types.PropertyGroup):
    item_id: StringProperty()
    sub: StringProperty()
    icon: IntProperty()


def _sub_items(self, context):
    cat = context.window_manager.dsl_category
    subs = sorted({i.get('sub') or 'Other' for i in index.items(cat)})
    _enum_cache['subs'] = [('ALL', 'All', 'Everything in this section')] + [(s, s, '') for s in subs]
    return _enum_cache['subs']


def refresh(self=None, context=None):
    context = context or bpy.context
    wm = context.window_manager
    cat = wm.dsl_category
    q = wm.dsl_search.lower().strip()
    try:
        sub = wm.dsl_sub
    except Exception:
        sub = 'ALL'
    rows = index.items(cat)
    if sub and sub != 'ALL':
        rows = [r for r in rows if (r.get('sub') or 'Other') == sub]
    if q:
        rows = [r for r in rows if q in r['name'].lower() or q in ' '.join(r.get('tags', [])).lower()
                or q in (r.get('description') or '').lower()]
    if wm.dsl_sort == 'USED':
        rows = sorted(rows, key=lambda r: (-(r.get('uses') or 0), r['name']))
    elif wm.dsl_sort == 'RECENT':
        rows = sorted(rows, key=lambda r: r.get('last_used') or r.get('added') or '', reverse=True)
    wm.dsl_items.clear()
    for r in rows:
        it = wm.dsl_items.add()
        it.name = r['name']
        it.item_id = r['id']
        it.sub = r.get('sub') or ''
    wm.dsl_index = min(wm.dsl_index, max(0, len(rows) - 1))


def _on_category(self, context):
    context.window_manager.dsl_index = 0
    try:
        context.window_manager.dsl_sub = 'ALL'
    except Exception:
        pass
    refresh(self, context)


def selected_item(context):
    wm = context.window_manager
    if 0 <= wm.dsl_index < len(wm.dsl_items):
        return index.get(wm.dsl_items[wm.dsl_index].item_id)
    return None


class DSL_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index_=0):
        row = layout.row(align=True)
        it = index.get(item.item_id)
        ic = icon_for(it) if it else 0
        if ic:
            row.label(text=item.name, icon_value=ic)
        else:
            row.label(text=item.name, icon='DOT')
        sub = row.row()
        sub.alignment = 'RIGHT'
        sub.enabled = False
        sub.label(text=item.sub)

    def filter_items(self, context, data, propname):
        return [], []


# ------------------------------------------------------------------ background state
class DSLSetProp(bpy.types.PropertyGroup):
    prop_id: StringProperty()

    def _toggle(self, context):
        if _enum_cache.get('syncing'):
            return
        try:
            sets.set_prop(self.prop_id, self.on)
        except Exception as e:
            print('Doodle Library:', e)

    on: BoolProperty(update=_toggle)


def _set_items(self, context):
    rows = [('NONE', 'No set', 'Empty: no room around Bunny', 'BLANK1', 0)]
    for i, s in enumerate(sorted(sets.sets(), key=lambda s: (s.get('sub') != 'Indoor', s['name'])), start=1):
        rows.append((s['id'], s['name'], '%s set' % (s.get('sub') or ''), 'HOME' if s.get('sub') == 'Indoor' else 'WORLD', i))
    _enum_cache['sets'] = rows
    return rows


def sync_set_props(context=None):
    context = context or bpy.context
    wm = context.window_manager
    st = sets.set_state()
    _enum_cache['syncing'] = True
    try:
        wm.dsl_set_props.clear()
        labels = {o['dsl_prop']: o.get('dsl_label', o['dsl_prop']) for o in sets.set_objects() if not o.get('dsl_shell')}
        for pid, on in st['props'].items():
            it = wm.dsl_set_props.add()
            it.prop_id = pid
            it.name = labels.get(pid, pid)
            it.on = on
    finally:
        _enum_cache['syncing'] = False


def _on_set(self, context):
    wm = context.window_manager
    if _enum_cache.get('syncing'):
        return
    try:
        if wm.dsl_set == 'NONE':
            sets.clear_set()
            st = dict(context.scene.get('dsl_set_state', {}) or {})
            st['set'] = None
            context.scene['dsl_set_state'] = st
        else:
            sets.switch_set(wm.dsl_set)
    except Exception as e:
        print('Doodle Library:', e)
    sync_set_props(context)


def _on_shadows(self, context):
    style.set_shadows(context.window_manager.dsl_shadows, bunny_too=context.window_manager.dsl_shadow_bunny)


# ------------------------------------------------------------------ panels
class DSLPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Doodle'


class DSL_PT_library(DSLPanel, bpy.types.Panel):
    bl_label = 'Doodle Library'

    def draw(self, context):
        wm = context.window_manager
        L = self.layout
        if not os.path.exists(index.path()):
            L.label(text='Library not found:', icon='ERROR')
            L.label(text=paths.library_root())
            L.operator('dsl.prefs', text='Set the library folder', icon='PREFERENCES')
            return
        L.row().prop(wm, 'dsl_category', expand=True)
        row = L.row(align=True)
        row.prop(wm, 'dsl_search', text='', icon='VIEWZOOM')
        row.prop(wm, 'dsl_sub', text='')
        row.prop(wm, 'dsl_sort', text='', icon_only=True)
        row.operator('dsl.refresh', text='', icon='FILE_REFRESH')
        L.template_list('DSL_UL_items', '', wm, 'dsl_items', wm, 'dsl_index', rows=7)
        it = selected_item(context)
        if not it:
            L.label(text='%d items' % len(wm.dsl_items))
            return
        row = L.row()
        ic = icon_for(it)
        if ic:
            row.template_icon(icon_value=ic, scale=5.0)
        col = row.column()
        col.label(text=it['name'])
        extra = []
        if it.get('frames'):
            extra.append('%d frames%s' % (it['frames'], ', loops' if it.get('loop') else ''))
        if it.get('uses'):
            extra.append('used %d×' % it['uses'])
        if extra:
            col.label(text=' · '.join(extra))
        desc = it.get('description') or ''
        for line in _wrap(desc, 46)[:4]:
            col.label(text=line)
        cat = it['category']
        opts = L.row(align=True)
        if cat == 'motion' and it['kind'] == 'ds':
            opts.prop(wm, 'dsl_opt_fix', toggle=True)
            opts.prop(wm, 'dsl_opt_mirror', toggle=True)
            opts.prop(wm, 'dsl_opt_camera', toggle=True)
        elif cat == 'prop':
            opts.prop(wm, 'dsl_opt_hold', toggle=True)
        label = {'motion': 'Insert at playhead', 'expression': 'Key face at playhead', 'mouth_set': 'Use these mouths',
                 'prop': 'Add prop', 'scenery': 'Add to scene', 'card': 'Add card'}.get(cat, 'Insert')
        L.operator('dsl.insert', text=label, icon='ADD').item_id = it['id']
        row = L.row(align=True)
        row.operator('dsl.save_motion', text='Save motion', icon='ACTION')
        row.operator('dsl.save_face', text='Save face', icon='USER')
        row.operator('dsl.save_selection', text='Save selection', icon='OBJECT_DATA')


class DSL_PT_background(DSLPanel, bpy.types.Panel):
    bl_label = 'Background'

    def draw(self, context):
        wm = context.window_manager
        L = self.layout
        L.prop(wm, 'dsl_set', text='')
        if wm.dsl_set_props:
            box = L.box()
            grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
            for it in wm.dsl_set_props:
                grid.prop(it, 'on', text=it.name, toggle=False)
            row = box.row(align=True)
            row.operator('dsl.set_all', text='All on').on = True
            row.operator('dsl.set_all', text='All off').on = False
            row.operator('dsl.declutter', text='Declutter')
        row = L.row(align=True)
        row.prop(wm, 'dsl_shadows', text='Shadows', toggle=True, icon='LIGHT_SUN')
        row.prop(wm, 'dsl_shadow_bunny', text='On Bunny too', toggle=True)
        st = bpy.data.objects.get('DSL_settings')
        if st and wm.dsl_shadows:
            row = L.row(align=True)
            row.prop(st, '["shade_mix"]', text='Shade', slider=True)
            row.prop(st, '["form"]', text='Form', slider=True)
            sun = bpy.data.objects.get('DSL_Sun')
            if sun:
                L.prop(sun, 'rotation_euler', text='Sun')
        L.separator()
        row = L.row(align=True)
        row.operator('dsl.camera', text='Eye-level camera', icon='CAMERA_DATA')
        row = L.row(align=True)
        row.prop(wm, 'dsl_parallax_mode', text='')
        row.prop(wm, 'dsl_parallax_frames', text='Frames')
        row.prop(wm, 'dsl_parallax_amount', text='Amount')
        row.operator('dsl.parallax', text='Add move', icon='CON_CAMERASOLVER')


class DSL_PT_object(DSLPanel, bpy.types.Panel):
    bl_label = 'Selected object'

    def draw(self, context):
        from . import grips, placement, text3d
        L = self.layout
        ob = context.active_object
        row = L.row(align=True)
        row.operator('dsl.lock_bunny', text='Bunny locked' if placement.is_locked() else 'Lock Bunny',
                     icon='LOCKED' if placement.is_locked() else 'UNLOCKED', depress=placement.is_locked())
        row.operator('dsl.add_text', text='Add 3D text', icon='FONT_DATA')
        row = L.row(align=True)
        row.operator('dsl.bake_collision', text='Bake collisions', icon='PHYSICS')
        g = bool(context.scene.get('dsl_collision_guard', False))
        row.operator('dsl.collision_guard', text='Live guard', icon='CHECKBOX_HLT' if g else 'CHECKBOX_DEHLT', depress=g)
        if not ob or ob.name.startswith('BUNNY_'):
            L.label(text='Select a prop, text or scenery piece')
            return
        mod = text3d.text_modifier(ob)
        if mod:
            ids = text3d._ids(mod)
            box = L.box()
            box.label(text='Text (| = new line)', icon='FONT_DATA')
            box.prop(mod, '["%s"]' % ids['Text'], text='')
            r = box.row(align=True)
            r.prop(mod, '["%s"]' % ids['Size'], text='Size')
            r.prop(mod, '["%s"]' % ids['Depth'], text='Depth')
            r.prop(mod, '["%s"]' % ids['Wobble'], text='Wobble')
            for n in mod.node_group.nodes:
                if n.bl_idname == 'GeometryNodeStringToCurves':
                    box.template_ID(n, 'font', open='font.open')
        kind = ob.get('dsl_grip_kind')
        if kind:
            box = L.box()
            box.label(text='In hand: %s grip (%s)' % (kind, ob.get('dsl_held_side', '')), icon='VIEW_PAN')
            box.label(text='G and R stay inside what the real grip allows')
            r = box.row(align=True)
            r.operator('dsl.check_grip', text='Check grip', icon='CHECKMARK')
            r.operator('dsl.release', text='Let go', icon='UNLINKED')
        else:
            box = L.box()
            box.label(text='Goes on: %s' % placement.place_mode(ob))
            r = box.row(align=True)
            r.operator('dsl.place', text='Place (click in view)', icon='RESTRICT_SELECT_OFF')
            r.operator('dsl.drop', text='Drop', icon='TRIA_DOWN_BAR')
            if ob.get('dsl_id', '').startswith('prop-') or ob.type == 'MESH' and ob.get('dsl_id'):
                box.operator('dsl.hold', text='Put in hand', icon='VIEW_PAN')


class DSL_PT_look(DSLPanel, bpy.types.Panel):
    bl_label = 'Look'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        L = self.layout
        bs = bpy.data.objects.get('BUNNY_settings')
        if not bs:
            L.label(text='Open or link Bunny3D.blend first')
            return
        row = L.row(align=True)
        for k, t in (('ink_px', 'Ink px'), ('boil', 'Boil'), ('boil_step', 'Step')):
            if k in bs.keys():
                row.prop(bs, '["%s"]' % k, text=t)
        L.operator('dsl.retarget', text='Re-aim ink at active camera', icon='CAMERA_DATA')
        row = L.row(align=True)
        row.operator('dsl.inbox', text='Add to library collection', icon='COLLECTION_NEW')
        row.operator('dsl.open_folder', text='Open folder', icon='FILE_FOLDER')


def _wrap(text, n):
    out, line = [], ''
    for w in text.split():
        if len(line) + len(w) + 1 > n:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(line)
    return out


WM_PROPS = dict(
    dsl_category=EnumProperty(name='Section', items=[(c[0], c[1], c[2], c[3], i) for i, c in enumerate(LIB_CATS)],
                              update=_on_category),
    dsl_search=StringProperty(name='Search', update=refresh, options={'TEXTEDIT_UPDATE'}),
    dsl_sub=EnumProperty(name='Group', items=_sub_items, update=refresh),
    dsl_sort=EnumProperty(name='Sort', items=[('NAME', 'A–Z', 'Alphabetical', 'SORTALPHA', 0),
                                              ('USED', 'Most used', 'Most used first', 'SORTSIZE', 1),
                                              ('RECENT', 'Recent', 'Recently used or added first', 'SORTTIME', 2)],
                          update=refresh),
    dsl_items=CollectionProperty(type=DSLItem),
    dsl_index=IntProperty(),
    dsl_opt_fix=BoolProperty(name='Fix clipping', default=True, description='Run the rig solver so hands never cut into the head'),
    dsl_opt_mirror=BoolProperty(name='Mirror', description='Play the motion left-right mirrored'),
    dsl_opt_camera=BoolProperty(name='Camera moves', description="Also key the motion's camera view changes"),
    dsl_opt_hold=BoolProperty(name='Put in hand', default=True, description='Attach to Bunny with the researched grip and arm pose'),
    dsl_set=EnumProperty(name='Set', items=_set_items, update=_on_set),
    dsl_set_props=CollectionProperty(type=DSLSetProp),
    dsl_shadows=BoolProperty(name='Shadows', update=_on_shadows, description='Cast shadows on the set (off = flat Doodle Studio look)'),
    dsl_shadow_bunny=BoolProperty(name='On Bunny too', update=_on_shadows, description="Let Bunny's own mustard take shadows too"),
    dsl_parallax_mode=EnumProperty(name='Move', items=[('orbit', 'Orbit', 'Arc around Bunny: he stays centred, the room turns'),
                                                       ('truck', 'Slide', 'Slide sideways at eye level'),
                                                       ('push', 'Push in', 'Dolly toward Bunny')]),
    dsl_parallax_frames=IntProperty(name='Frames', default=72, min=6, max=1200),
    dsl_parallax_amount=FloatProperty(name='Amount', default=1.0, min=0.1, max=3.0),
)

CLASSES = (DSLItem, DSLSetProp, DSL_UL_items, DSL_PT_library, DSL_PT_background, DSL_PT_object, DSL_PT_look)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    for k, v in WM_PROPS.items():
        setattr(bpy.types.WindowManager, k, v)


def unregister():
    global _previews
    for k in WM_PROPS:
        if hasattr(bpy.types.WindowManager, k):
            delattr(bpy.types.WindowManager, k)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
