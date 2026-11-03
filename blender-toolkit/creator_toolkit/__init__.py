"""Creator Toolkit: general Blender tools for design, motion and character work.

Every tool is a module in ./modules with:
    LABEL, ICON, GROUP          - names shown in the UI
    CLASSES                     - bpy classes to register
    register_extra()/unregister_extra()  (optional)
    draw(layout, context)       - the module's panel body

The Master Launcher hosts the modules through MODULES (see LAUNCHER.md).
Without the launcher, the toolkit shows its own "Toolkit" sidebar tab.
"""
import importlib
import bpy

from . import compat  # noqa: F401

_NAMES = [
    'vault', 'doodle', 'cleanimport', 'material', 'style', 'palette', 'lights',
    'rig', 'thingrig', 'springs', 'mocap', 'motion', 'tween', 'playback', 'lipsync', 'physics52', 'smear52',
    'kinetic', 'camera', 'music', 'gnkit', 'shapes52', 'gpkit', 'nodetidy',
    'deliver', 'templates', 'turntable', 'speed', 'pie', 'updates',
]

MODULES = []
for _n in _NAMES:
    MODULES.append(importlib.import_module('.modules.' + _n, __package__))

GROUP_ORDER = ['Assets', 'Look', 'Rigging', 'Animation', 'Motion design', 'Procedural & 2D', 'Output', 'Setup']


def _group_draw(group):
    def draw(layout, context):
        for m in _sorted_modules():
            if m.GROUP == group:
                box = layout.box()
                box.label(text=m.LABEL, icon=m.ICON)
                draw_module(m, box, context)
    return draw


def _section_draw(mod):
    def draw(layout, context):
        draw_module(mod, layout, context)
    return draw


_GROUP_ICONS = {'Assets': 'ASSET_MANAGER', 'Look': 'SHADING_RENDERED', 'Rigging': 'ARMATURE_DATA',
                'Animation': 'ACTION', 'Motion design': 'FONT_DATA', 'Procedural & 2D': 'GEOMETRY_NODES',
                'Output': 'RENDER_ANIMATION', 'Setup': 'PREFERENCES'}


def _doodle_master():
    tools = []
    for i, g in enumerate(GROUP_ORDER):
        mods = [m for m in _sorted_modules() if m.GROUP == g]
        tools.append({
            'id': 'tk_' + g.lower().replace(' & ', '_').replace(' ', '_'),
            'label': g, 'icon': _GROUP_ICONS[g], 'order': 61 + i,
            'sections': [{'label': m.LABEL, 'draw': _section_draw(m), 'space': 'VIEW_3D', 'closed': True}
                         for m in mods],
        })
    return {'tools': tools}


def draw_module(mod, layout, context):
    try:
        mod.draw(layout, context)
    except Exception as e:  # never let one tool break the whole sidebar
        layout.label(text=f'{mod.LABEL}: {e}', icon='ERROR')


DOODLE_MASTER = None  # filled after modules load (bottom of file)


class CTK_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__
    own_tab: bpy.props.BoolProperty(
        name='Show the Toolkit sidebar tab',
        description='Turn off when the Master Launcher shows these tools for you',
        default=True)
    vault_dir: bpy.props.StringProperty(
        name='Vault folder', subtype='DIR_PATH',
        description='Where the Asset Vault, presets and brand kits are kept',
        default='')
    deliver_root: bpy.props.StringProperty(
        name='Projects folder', subtype='DIR_PATH',
        description='Deliver panel makes <Project>\\ and <Project>\\work\\ here',
        default='')
    doodle_lib_dir: bpy.props.StringProperty(
        name='Doodle Library folder', subtype='DIR_PATH', default='',
        description='Only needed without the Doodle Library add-on. Default: Documents/Talking Character App/blender-library')
    auto_update_check: bpy.props.BoolProperty(
        name='Check for updates when Blender starts', default=True,
        description='Looks at GitHub once per start (needs Allow Online Access). Nothing installs without your click')
    rhubarb_path: bpy.props.StringProperty(
        name='Rhubarb Lip Sync (optional)', subtype='FILE_PATH',
        description='rhubarb.exe gives sharper lip sync. Without it, Lip sync reads loudness', default='')

    def draw(self, context):
        c = self.layout.column()
        c.prop(self, 'own_tab')
        c.prop(self, 'vault_dir')
        c.prop(self, 'deliver_root')
        c.prop(self, 'rhubarb_path')
        c.prop(self, 'doodle_lib_dir')
        c.prop(self, 'auto_update_check')


def prefs():
    a = bpy.context.preferences.addons.get(__package__)
    return a.preferences if a else None


class CTK_PT_root(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_label = 'Creator Toolkit'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        p = prefs()
        return p is None or p.own_tab

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator('wm.call_menu_pie', text='Pie', icon='PROPERTIES').name = 'CTK_MT_pie'
        row.operator('ctk.search', text='Find a tool', icon='VIEWZOOM')


def _make_panel(mod, idx):
    def draw(self, context):
        draw_module(mod, self.layout, context)

    def draw_header(self, context):
        self.layout.label(text='', icon=mod.ICON)

    return type(f'CTK_PT_{mod.__name__.rsplit(".", 1)[-1]}', (bpy.types.Panel,), dict(
        bl_space_type='VIEW_3D', bl_region_type='UI', bl_category='Toolkit',
        bl_label=f'{mod.GROUP} · {mod.LABEL}', bl_options={'DEFAULT_CLOSED'},
        bl_order=idx + 1, poll=CTK_PT_root.poll, draw=draw, draw_header=draw_header))


def _sorted_modules():
    return sorted(MODULES, key=lambda m: (GROUP_ORDER.index(m.GROUP), MODULES.index(m)))


def _search_items(self, context):
    return [(m.__name__, f'{m.GROUP}: {m.LABEL}', '') for m in _sorted_modules()]


class CTK_OT_search(bpy.types.Operator):
    """Type a tool's name and open it"""
    bl_idname = 'ctk.search'
    bl_label = 'Find a tool'
    bl_property = 'tool'
    tool: bpy.props.EnumProperty(items=_search_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        mod = next(m for m in MODULES if m.__name__ == self.tool)
        bpy.ops.ctk.tool_popup('INVOKE_DEFAULT', tool=self.tool)
        self.report({'INFO'}, f'Opened {mod.LABEL}')
        return {'FINISHED'}


class CTK_OT_tool_popup(bpy.types.Operator):
    """Show one tool in a popup"""
    bl_idname = 'ctk.tool_popup'
    bl_label = 'Tool'
    tool: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        mod = next((m for m in MODULES if m.__name__ == self.tool), None)
        if mod:
            self.layout.label(text=mod.LABEL, icon=mod.ICON)
            draw_module(mod, self.layout, context)

    def execute(self, context):
        return {'FINISHED'}


_panels = []
_core = (CTK_Prefs, CTK_PT_root, CTK_OT_search, CTK_OT_tool_popup)


def register():
    for c in _core:
        bpy.utils.register_class(c)
    for m in MODULES:
        for c in m.CLASSES:
            bpy.utils.register_class(c)
        if hasattr(m, 'register_extra'):
            m.register_extra()
    for i, m in enumerate(_sorted_modules()):
        p = _make_panel(m, i)
        bpy.utils.register_class(p)
        _panels.append(p)


def unregister():
    for p in reversed(_panels):
        bpy.utils.unregister_class(p)
    _panels.clear()
    for m in reversed(MODULES):
        if hasattr(m, 'unregister_extra'):
            m.unregister_extra()
        for c in reversed(m.CLASSES):
            bpy.utils.unregister_class(c)
    for c in reversed(_core):
        bpy.utils.unregister_class(c)


DOODLE_MASTER = _doodle_master()
