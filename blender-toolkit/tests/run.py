"""Headless test: python -I tests/run.py  (needs pip bpy)."""
import sys, os, traceback, tempfile
import bpy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import addon_utils  # noqa
import creator_toolkit as ctk
os.environ.setdefault('CTK_TEST', '1')
a = bpy.context.preferences.addons.new(); a.module = 'creator_toolkit'
ctk.register()
tmp = tempfile.mkdtemp()
os.environ['CTK_VAULT_DIR'] = os.path.join(tmp, 'vault'); os.environ['CTK_DELIVER_ROOT'] = os.path.join(tmp, 'projects')
p = bpy.context.preferences.addons['creator_toolkit'].preferences
p.vault_dir = os.path.join(tmp, 'vault'); p.deliver_root = os.path.join(tmp, 'projects')
fails = []
def t(name, fn):
    try:
        fn(); print('PASS', name)
    except Exception:
        fails.append(name); print('FAIL', name); traceback.print_exc()
sys.path.insert(0, HERE)
import cases  # noqa
for name, fn in cases.CASES:
    t(name, fn)
ctk.unregister()
print('VERSION', bpy.app.version_string, 'FAILS', len(fails), fails)
