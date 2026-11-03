"""Pie menu (Shift+Q in the 3D view) + a Keydial cheat sheet."""
import bpy

LABEL, ICON, GROUP = 'Pie menu + Keydial', 'PROPERTIES', 'Setup'

SHORTCUTS = [
    ('Shift+Q', 'Creator Toolkit pie', '3D View'),
    ('Shift+Alt+E', 'Breakdown (tween) between keys', '3D View, pose or object'),
    ('Ctrl+Shift+F', 'Find a tool', '3D View'),
    ('Alt+Shift+M', 'Motion preset on selection', '3D View'),
    ('Ctrl+Shift+V', 'Save selection to the Vault', '3D View'),
]


class CTK_MT_pie(bpy.types.Menu):
    bl_idname = 'CTK_MT_pie'
    bl_label = 'Creator Toolkit'

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator('ctk.vault_save', text='Save to Vault', icon='ASSET_MANAGER')       # left
        pie.operator('ctk.search', text='Find a tool', icon='VIEWZOOM')                   # right
        pie.operator('ctk.motion_preset', text='Motion preset', icon='ACTION')            # bottom
        pie.operator('ctk.tool_popup', text='Look', icon='SHADING_RENDERED').tool = __package__ + '.style'  # top
        pie.operator('ctk.tool_popup', text='Lights', icon='LIGHT').tool = __package__ + '.lights'
        pie.operator('ctk.tool_popup', text='Camera', icon='VIEW_CAMERA').tool = __package__ + '.camera'
        pie.operator('ctk.tool_popup', text='Rig', icon='ARMATURE_DATA').tool = __package__ + '.rig'
        pie.operator('ctk.tool_popup', text='Deliver', icon='RENDER_ANIMATION').tool = __package__ + '.deliver'


class CTK_OT_keydial(bpy.types.Operator):
    """Shortcuts to put on your Huion Keydial (or any macro pad)"""
    bl_idname = 'ctk.keydial_sheet'
    bl_label = 'Keydial cheat sheet'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.label(text='Map these keys on your Keydial:', icon='EVENT_K')
        for k, what, where in SHORTCUTS:
            r = col.row()
            r.label(text=k)
            r.label(text=what)
            r.label(text=where)
        col.operator('ctk.keydial_text', icon='TEXT')

    def execute(self, context):
        return {'FINISHED'}


class CTK_OT_keydial_text(bpy.types.Operator):
    """Write the cheat sheet into a Text block you can print or save"""
    bl_idname = 'ctk.keydial_text'
    bl_label = 'Copy to a text block'

    def execute(self, context):
        t = bpy.data.texts.get('Keydial shortcuts') or bpy.data.texts.new('Keydial shortcuts')
        t.clear()
        t.write('Creator Toolkit shortcuts\n\n' + '\n'.join(f'{k:14} {w}  ({p})' for k, w, p in SHORTCUTS) + '\n')
        context.window_manager.clipboard = t.as_string()
        self.report({'INFO'}, 'Cheat sheet copied and saved as the "Keydial shortcuts" text')
        return {'FINISHED'}


CLASSES = (CTK_MT_pie, CTK_OT_keydial, CTK_OT_keydial_text)
_keymaps = []


def register_extra():
    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    for idname, key, mods, props in (
            ('wm.call_menu_pie', 'Q', dict(shift=True), dict(name='CTK_MT_pie')),
            ('ctk.search', 'F', dict(ctrl=True, shift=True), {}),
            ('ctk.motion_preset', 'M', dict(alt=True, shift=True), {}),
            ('ctk.vault_save', 'V', dict(ctrl=True, shift=True), {})):
        kmi = km.keymap_items.new(idname, key, 'PRESS', **mods)
        for k, v in props.items():
            setattr(kmi.properties, k, v)
        _keymaps.append((km, kmi))


def unregister_extra():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('wm.call_menu_pie', text='Open pie (Shift+Q)', icon='PROPERTIES').name = 'CTK_MT_pie'
    row.operator('ctk.keydial_sheet', icon='EVENT_K')
