"""One-click Asset Vault: save anything to one library every project can use."""
import os
import uuid
import bpy
from . import _util

LABEL, ICON, GROUP = 'Asset Vault', 'ASSET_MANAGER', 'Assets'
LIB_NAME = 'Creator Vault'
KINDS = [('OBJECTS', 'Selected objects', ''), ('MATERIAL', 'Active material', ''),
         ('NODEGROUP', 'Active node group (modifier)', ''), ('POSE', 'Current action / pose', ''),
         ('LIGHTS', 'Selected lights as a rig', ''), ('SCENE', 'Whole scene', '')]
CATS = {'OBJECTS': 'Props', 'MATERIAL': 'Materials', 'NODEGROUP': 'Node groups', 'POSE': 'Poses',
        'LIGHTS': 'Light rigs', 'SCENE': 'Scenes'}


def _cats_file():
    return os.path.join(_util.vault_dir(), 'blender_assets.cats.txt')


def catalog_id(path):
    """Return the UUID for a catalog path like 'Props/Furniture', creating it if needed."""
    f = _cats_file()
    rows = {}
    if os.path.exists(f):
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('VERSION'):
                u, p, *_ = line.split(':')
                rows[p] = u
    parts = path.strip('/').split('/')
    for i in range(1, len(parts) + 1):
        p = '/'.join(parts[:i])
        rows.setdefault(p, str(uuid.uuid4()))
    with open(f, 'w', encoding='utf-8') as out:
        out.write('# Creator Vault catalogs\nVERSION 1\n\n')
        for p, u in sorted(rows.items()):
            out.write(f'{u}:{p}:{p.replace("/", "-")}\n')
    return rows['/'.join(parts)]


def ensure_library(context=None):
    libs = bpy.context.preferences.filepaths.asset_libraries
    d = _util.vault_dir()
    for lib in libs:
        if bpy.path.abspath(lib.path).rstrip('\\/') == d.rstrip('\\/'):
            return lib
    try:
        lib = libs.new(name=LIB_NAME, directory=d)
    except TypeError:
        lib = libs.new()
    try:
        lib.name = LIB_NAME
        lib.path = d
    except Exception:
        pass
    return lib


def online_supported():
    try:
        import _bpy_internal.assets.remote_library.cli  # noqa: F401  (Blender 5.2+)
        return hasattr(bpy.types.UserAssetLibrary, 'bl_rna') and \
            'remote_url' in bpy.types.UserAssetLibrary.bl_rna.properties
    except Exception:
        return False


def publish_listing(folder=None):
    """Write Blender's online-library index next to the Vault files (5.2). Upload the whole
    folder to any static web host (GitHub Pages, your site, a CDN) and every PC can browse it."""
    from _bpy_internal.assets.remote_library import cli
    folder = folder or _util.vault_dir()
    try:
        cli.main(['-q', 'generate', folder])
    except SystemExit as e:
        if e.code:
            raise RuntimeError('Listing failed (%s)' % e.code)
    return folder


def add_online(url, name='Creator Vault (online)'):
    libs = bpy.context.preferences.filepaths.asset_libraries
    for lib in libs:
        if getattr(lib, 'remote_url', '') == url:
            return lib
    bpy.ops.preferences.asset_library_add(name=name, remote_url=url, type='REMOTE')
    return next(lib for lib in libs if getattr(lib, 'remote_url', '') == url)


def _clean(name):
    return ''.join(c if c.isalnum() or c in ' -_' else '_' for c in name).strip() or 'asset'


class CTK_OT_vault_save(bpy.types.Operator):
    """Save to your Vault with a thumbnail, category and tags. Every project sees it in the Asset Browser"""
    bl_idname = 'ctk.vault_save'
    bl_label = 'Save to Vault'
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(name='What', items=KINDS)
    name: bpy.props.StringProperty(name='Name')
    category: bpy.props.StringProperty(name='Category', description='Use / for sub-folders, e.g. Props/Kitchen')
    tags: bpy.props.StringProperty(name='Tags', description='Comma separated')

    def invoke(self, context, event):
        if not self.name:
            ob = context.active_object
            self.name = ob.name if ob else context.scene.name
        if not self.category:
            self.category = CATS[self.kind]
        return context.window_manager.invoke_props_dialog(self)

    def _gather(self, context):
        k = self.kind
        if k == 'OBJECTS':
            obs = [o for o in context.selected_objects]
            if not obs:
                return None, 'Select objects first'
            if len(obs) == 1:
                return [obs[0]], None
            coll = bpy.data.collections.new(self.name)
            for o in obs:
                coll.objects.link(o)
            return [coll], None
        if k == 'LIGHTS':
            obs = [o for o in context.selected_objects if o.type == 'LIGHT' or o.type == 'EMPTY']
            if not obs:
                return None, 'Select lights first'
            coll = bpy.data.collections.new(self.name)
            for o in obs:
                coll.objects.link(o)
            return [coll], None
        if k == 'MATERIAL':
            ob = context.active_object
            m = ob.active_material if ob else None
            return ([m], None) if m else (None, 'Active object has no material')
        if k == 'NODEGROUP':
            ob = context.active_object
            mod = ob.modifiers.active if ob and ob.modifiers else None
            ng = getattr(mod, 'node_group', None)
            return ([ng], None) if ng else (None, 'Active modifier has no node group')
        if k == 'POSE':
            ob = context.active_object
            act = ob.animation_data.action if ob and ob.animation_data else None
            return ([act], None) if act else (None, 'Active object has no action')
        if k == 'SCENE':
            return [context.scene], None
        return None, 'Nothing to save'

    def execute(self, context):
        ids, err = self._gather(context)
        if err:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}
        cid = catalog_id(self.category or CATS[self.kind])
        for idb in ids:
            idb.asset_mark()
            ad = idb.asset_data
            ad.catalog_id = cid
            for t in [t.strip() for t in self.tags.split(',') if t.strip()]:
                if t not in ad.tags:
                    ad.tags.new(t)
            try:
                idb.asset_generate_preview()
            except Exception:
                pass
        sub = os.path.join(_util.vault_dir(), *[_clean(x) for x in (self.category or CATS[self.kind]).split('/') if x.strip()])
        os.makedirs(sub, exist_ok=True)
        path = os.path.join(sub, _clean(self.name) + '.blend')
        n = 2
        while os.path.exists(path):
            path = os.path.join(sub, f'{_clean(self.name)}_{n:02d}.blend')
            n += 1
        bpy.data.libraries.write(path, set(ids), fake_user=True, compress=True)
        for idb in ids:
            try:
                idb.asset_clear()
            except Exception:
                pass
            if isinstance(idb, bpy.types.Collection) and idb.users <= 1 and self.kind in ('OBJECTS', 'LIGHTS'):
                bpy.data.collections.remove(idb)
        ensure_library()
        self.report({'INFO'}, f'Saved to Vault: {path}')
        return {'FINISHED'}


class CTK_OT_vault_add_library(bpy.types.Operator):
    """Add your Vault folder to the Asset Browser so every project can see it"""
    bl_idname = 'ctk.vault_add_library'
    bl_label = 'Show Vault in Asset Browser'

    def execute(self, context):
        lib = ensure_library()
        self.report({'INFO'}, f'Vault library: {lib.path if lib else "?"}')
        return {'FINISHED'}


class CTK_OT_vault_open(bpy.types.Operator):
    """Open the Vault folder"""
    bl_idname = 'ctk.vault_open'
    bl_label = 'Open Vault folder'

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=_util.vault_dir())
        return {'FINISHED'}


class CTK_OT_vault_publish(bpy.types.Operator):
    """Make your Vault ready to put online: writes Blender's online library index into the Vault folder"""
    bl_idname = 'ctk.vault_publish'
    bl_label = 'Prepare online Vault'

    @classmethod
    def poll(cls, context):
        return online_supported()

    def execute(self, context):
        try:
            d = publish_listing()
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Ready. Upload this folder to your web host: ' + d)
        return {'FINISHED'}


class CTK_OT_vault_online(bpy.types.Operator):
    """Browse your online Vault on this PC (downloads assets only when you use them)"""
    bl_idname = 'ctk.vault_online'
    bl_label = 'Connect online Vault'
    url: bpy.props.StringProperty(name='Vault web address', default='https://')

    @classmethod
    def poll(cls, context):
        return online_supported()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def execute(self, context):
        if not self.url.startswith('https://') or len(self.url) < 12:
            self.report({'ERROR'}, 'Paste the https:// address where the Vault folder is hosted')
            return {'CANCELLED'}
        add_online(self.url.rstrip('/') + '/')
        self.report({'INFO'}, 'Online Vault added to the Asset Browser')
        return {'FINISHED'}


class CTK_MT_vault_context(bpy.types.Menu):
    bl_label = 'Save to Vault'
    bl_idname = 'CTK_MT_vault_context'

    def draw(self, context):
        for k, label, _ in KINDS:
            self.layout.operator(CTK_OT_vault_save.bl_idname, text=label).kind = k


def _object_menu(self, context):
    self.layout.separator()
    self.layout.menu(CTK_MT_vault_context.bl_idname, icon=ICON)


CLASSES = (CTK_OT_vault_save, CTK_OT_vault_add_library, CTK_OT_vault_open, CTK_OT_vault_publish, CTK_OT_vault_online,
           CTK_MT_vault_context)


def register_extra():
    bpy.types.VIEW3D_MT_object_context_menu.append(_object_menu)


def unregister_extra():
    bpy.types.VIEW3D_MT_object_context_menu.remove(_object_menu)


def draw(layout, context):
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator('ctk.vault_save', text='Objects', icon='OBJECT_DATA').kind = 'OBJECTS'
    row.operator('ctk.vault_save', text='Material', icon='MATERIAL').kind = 'MATERIAL'
    row.operator('ctk.vault_save', text='Pose', icon='ARMATURE_DATA').kind = 'POSE'
    row = col.row(align=True)
    row.operator('ctk.vault_save', text='Nodes', icon='GEOMETRY_NODES').kind = 'NODEGROUP'
    row.operator('ctk.vault_save', text='Lights', icon='LIGHT').kind = 'LIGHTS'
    row.operator('ctk.vault_save', text='Scene', icon='SCENE_DATA').kind = 'SCENE'
    row = layout.row(align=True)
    row.operator('ctk.vault_add_library', icon='ASSET_MANAGER')
    row.operator('ctk.vault_open', text='', icon='FILE_FOLDER')
    if online_supported():
        row = layout.row(align=True)
        row.operator('ctk.vault_publish', icon='WORLD')
        row.operator('ctk.vault_online', icon='URL')
    layout.label(text='Tip: right-click an object › Save to Vault', icon='INFO')
