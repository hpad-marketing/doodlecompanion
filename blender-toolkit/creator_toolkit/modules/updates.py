"""Update channel: checks GitHub for a newer Creator Toolkit and installs it in place."""
import json
import os
import tempfile
import threading
import urllib.request
import bpy

LABEL, ICON, GROUP = 'Updates', 'URL', 'Setup'
FEED = 'https://raw.githubusercontent.com/hpad-marketing/doodlecompanion/main/blender-toolkit/release/latest.json'
STATE = {'status': '', 'latest': None, 'busy': False}


def installed_version():
    try:
        import tomllib
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'blender_manifest.toml'), 'rb') as f:
            return tomllib.load(f)['version']
    except Exception:
        return '0.0.0'


def _v(s):
    return tuple(int(x) for x in str(s).split('.')[:3] if x.isdigit())


def online_ok():
    return getattr(bpy.app, 'online_access', True)


def fetch(url=FEED, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': 'CreatorToolkit'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(blocking=False):
    def work():
        STATE['busy'] = True
        try:
            info = json.loads(fetch().decode('utf-8'))
            STATE['latest'] = info
            if _v(info['version']) > _v(installed_version()):
                STATE['status'] = 'Version %s is ready: %s' % (info['version'], info.get('notes', ''))
            else:
                STATE['status'] = 'You have the latest version (%s)' % installed_version()
        except Exception as e:
            STATE['status'] = 'Could not check: %s' % e
        STATE['busy'] = False
    if blocking:
        work()
    else:
        threading.Thread(target=work, daemon=True).start()


def install_zip(path):
    """Install over the current copy (same repository, same id)."""
    repo = 'user_default'
    pkg = __package__.rsplit('.', 2)[0]
    if pkg.startswith('bl_ext.'):
        repo = pkg.split('.')[1]
    return bpy.ops.extensions.package_install_files(repo=repo, filepath=path, overwrite=True, enable_on_install=True)


class CTK_OT_update_check(bpy.types.Operator):
    """Look for a newer Creator Toolkit on GitHub"""
    bl_idname = 'ctk.update_check'
    bl_label = 'Check for updates'

    def execute(self, context):
        if not online_ok():
            self.report({'WARNING'}, 'Turn on Edit > Preferences > System > Allow Online Access first')
            return {'CANCELLED'}
        check()
        self.report({'INFO'}, 'Checking...')
        return {'FINISHED'}


class CTK_OT_update_install(bpy.types.Operator):
    """Download the newer version and install it over this one"""
    bl_idname = 'ctk.update_install'
    bl_label = 'Install update'

    def execute(self, context):
        info = STATE.get('latest')
        if not info or _v(info['version']) <= _v(installed_version()):
            self.report({'INFO'}, 'Nothing newer to install')
            return {'CANCELLED'}
        try:
            data = fetch(info['zip_url'], 60)
            path = os.path.join(tempfile.mkdtemp(), 'creator_toolkit-%s.zip' % info['version'])
            with open(path, 'wb') as f:
                f.write(data)
            install_zip(path)
        except Exception as e:
            self.report({'ERROR'}, 'Update failed: %s' % e)
            return {'CANCELLED'}
        self.report({'INFO'}, 'Updated to %s. Restart Blender to finish' % info['version'])
        return {'FINISHED'}


class CTK_OT_update_from_file(bpy.types.Operator):
    """Install a Creator Toolkit zip you downloaded"""
    bl_idname = 'ctk.update_from_file'
    bl_label = 'Install from a zip'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.zip', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        install_zip(self.filepath)
        return {'FINISHED'}


CLASSES = (CTK_OT_update_check, CTK_OT_update_install, CTK_OT_update_from_file)


def _startup_check():
    from . import _util
    p = _util.addon_prefs()
    if p and getattr(p, 'auto_update_check', False) and online_ok():
        check()
    return None


def register_extra():
    if not os.environ.get('CTK_TEST'):
        bpy.app.timers.register(_startup_check, first_interval=8.0)


def draw(layout, context):
    row = layout.row(align=True)
    row.label(text='Installed: ' + installed_version())
    row.operator('ctk.update_check', icon='FILE_REFRESH')
    info = STATE.get('latest')
    if info and _v(info['version']) > _v(installed_version()):
        row.operator('ctk.update_install', icon='IMPORT')
    if STATE['status']:
        layout.label(text=STATE['status'][:80])
    row.operator('ctk.update_from_file', text='', icon='FILE_ARCHIVE')
