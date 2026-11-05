"""Doodle Library browser: Doodle Studio's sets, props, faces, motions and outfits as pictures.

Uses the Doodle Library add-on (installed with Doodle Studio 3D) when it is on, so faces, motions
and whole sets go onto Bunny exactly like in Doodle Studio 3D. Without it, props, scenery and
2D cards still append straight from the library files."""
import importlib
import json
import os
import bpy
from .. import uxfit

LABEL, ICON, GROUP = 'Doodle Library', 'OUTLINER_OB_GROUP_INSTANCE', 'Assets'

CATS = [('set', 'Sets', 'SCENE_DATA'), ('prop', 'Props', 'OBJECT_DATA'), ('expression', 'Faces', 'USER'),
        ('motion', 'Motions', 'ARMATURE_DATA'), ('mouth_set', 'Mouths', 'SPEAKER'),
        ('outfit', 'Outfits', 'MOD_CLOTH'), ('accessory', 'Accessories', 'MOD_CLOTH'),
        ('scenery', 'Scenery', 'MESH_CUBE'), ('card', '2D cards', 'IMAGE_PLANE')]
OBJECT_CATS = {'prop', 'scenery', 'card'}
_prev = {'coll': None}
_cache = {'path': None, 'mtime': None, 'items': []}


def dl_api():
    """The Doodle Library API: its own add-on when that is on, else the Toolkit's built-in copy."""
    for key in list(bpy.context.preferences.addons.keys()):
        if key == 'doodle_library' or key.endswith('.doodle_library'):
            try:
                return importlib.import_module(key + '.api')
            except Exception:
                return None
    try:
        from .. import dsl
        if dsl._active['on']:
            return importlib.import_module(dsl.__name__ + '.api')
    except Exception:
        pass
    return None


def library_root():
    api = dl_api()
    if api:
        try:
            pkg = importlib.import_module(api.__name__.rsplit('.', 1)[0] + '.paths')
            return pkg.library_root()
        except Exception:
            pass
    from . import _util
    p = _util.addon_prefs()
    d = getattr(p, 'doodle_lib_dir', '') if p else ''
    return bpy.path.abspath(d) if d else (os.environ.get('DSL_LIBRARY') or os.path.join(
        os.path.expanduser('~'), 'Documents', 'Talking Character App', 'blender-library'))


def rows():
    path = os.path.join(library_root(), 'library.json')
    if not os.path.exists(path):
        return []
    m = os.path.getmtime(path)
    if _cache['path'] != path or _cache['mtime'] != m:
        with open(path, encoding='utf-8') as f:
            _cache['items'] = json.load(f).get('items', [])
        _cache['path'], _cache['mtime'] = path, m
    return _cache['items']


def filtered(cat, text=''):
    t = text.lower().strip()
    out = [r for r in rows() if r.get('category') == cat]
    if t:
        out = [r for r in out if t in (r.get('name', '') + ' ' + r['id'] + ' ' + ' '.join(r.get('tags', []))).lower()]
    out.sort(key=lambda r: (-r.get('uses', 0), r.get('name', r['id'])))
    return out


def _previews():
    if _prev['coll'] is None:
        from bpy.utils import previews
        _prev['coll'] = previews.new()
    return _prev['coll']


_enum_keep = []


def _items(self, context):
    p = context.scene.ctk_doodle
    pc = _previews()
    root = library_root()
    out = []
    for i, r in enumerate(filtered(p.category, p.search)[:400]):
        icon = 0
        rel = r.get('preview')
        if rel:
            full = os.path.join(root, rel)
            if full not in pc and os.path.exists(full):
                pc.load(full, full, 'IMAGE')
            if full in pc:
                icon = pc[full].icon_id
        out.append((r['id'], r.get('name') or r['id'], r.get('desc', ''), icon, i))
    if not out:
        out = [('', 'Nothing here', '', 0, 0)]
    _enum_keep[:] = out  # Blender needs the strings kept alive
    return out


class CTK_DoodleProps(bpy.types.PropertyGroup):
    category: bpy.props.EnumProperty(name='Show', items=[(k, l, '', ic, i) for i, (k, l, ic) in enumerate(CATS)])
    search: bpy.props.StringProperty(name='Search', options={'TEXTEDIT_UPDATE'})
    pick: bpy.props.EnumProperty(name='Item', items=_items)
    hold: bpy.props.BoolProperty(name="Put props in Bunny's hand", default=False)


def append_object(row):
    path = os.path.join(library_root(), row['file'])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if row['datablock'] not in src.objects:
            raise RuntimeError('%s is missing from %s' % (row['datablock'], row['file']))
        dst.objects = [row['datablock']]
    ob = dst.objects[0]
    coll = bpy.data.collections.get('Doodle Library') or bpy.data.collections.new('Doodle Library')
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    coll.objects.link(ob)
    ob.location = bpy.context.scene.cursor.location
    ob['dsl_id'] = row['id']
    return ob


def insert(item_id, hold=False):
    row = next((r for r in rows() if r['id'] == item_id), None)
    if not row:
        raise KeyError(item_id)
    api = dl_api()
    if api:
        try:
            return api.insert(item_id, hold=hold) if row['category'] == 'prop' else api.insert(item_id)
        except Exception:
            # props and scenery still come in plain when the 3D Bunny files aren't on this PC
            if row['category'] not in OBJECT_CATS:
                raise
    if row['category'] in OBJECT_CATS and row.get('file') and row.get('datablock'):
        return append_object(row)
    raise RuntimeError('Sets, faces and motions need the Doodle Library add-on (it comes with Doodle Studio 3D)')


class CTK_OT_doodle_insert(bpy.types.Operator):
    """Add the picked library item (faces and motions go on at the playhead)"""
    bl_idname = 'ctk.doodle_insert'
    bl_label = 'Add to scene'
    bl_options = {'REGISTER', 'UNDO'}
    item: bpy.props.StringProperty()

    def execute(self, context):
        p = context.scene.ctk_doodle
        item = self.item or p.pick
        if not item:
            self.report({'WARNING'}, 'Pick something first')
            return {'CANCELLED'}
        try:
            insert(item, p.hold)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class CTK_OT_doodle_refresh(bpy.types.Operator):
    """Reload library.json and the pictures"""
    bl_idname = 'ctk.doodle_refresh'
    bl_label = 'Refresh library'

    def execute(self, context):
        _cache['mtime'] = None
        if _prev['coll'] is not None:
            _prev['coll'].clear()
        return {'FINISHED'}


CLASSES = (CTK_DoodleProps, CTK_OT_doodle_insert, CTK_OT_doodle_refresh)


def register_extra():
    bpy.types.Scene.ctk_doodle = bpy.props.PointerProperty(type=CTK_DoodleProps)


def unregister_extra():
    del bpy.types.Scene.ctk_doodle
    if _prev['coll'] is not None:
        from bpy.utils import previews
        previews.remove(_prev['coll'])
        _prev['coll'] = None


def draw(layout, context):
    p = context.scene.ctk_doodle
    if not rows():
        layout.label(text='Doodle Library not found', icon='ERROR')
        uxfit.wrap(layout, context, 'Set its folder in the add-on preferences')
        return
    row = layout.row(align=True)
    row.prop(p, 'category', text='')
    row.prop(p, 'search', text='', icon='VIEWZOOM')
    row.operator('ctk.doodle_refresh', text='', icon='FILE_REFRESH')
    layout.template_icon_view(p, 'pick', show_labels=True, scale=7.0, scale_popup=5.0)
    row = layout.row(align=True)
    if p.category == 'prop':
        row.prop(p, 'hold')
    row.operator('ctk.doodle_insert', icon='ADD')
    uxfit.wrap(layout, context, 'Effects, lighting, storytime and more: Doodle tab', icon='INFO')
