"""Droid Kit shared helpers: where the kit lives, the droid's settings file and its output folder.
Every kit script runs headless: python3 <script>.py [args] in.blend out.blend   (bpy 5.2 wheel or blender -b --python)
Pick the droid with the env var DROID=<id> (reads droids/<id>.json) or DROID_SETTINGS=<path>."""
import json, os
KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(KIT)
VERSION = open(os.path.join(ROOT, 'VERSION')).read().strip() if os.path.exists(os.path.join(ROOT, 'VERSION')) else 'dev'
_S = None
def settings():
    global _S
    if _S is None:
        p = os.environ.get('DROID_SETTINGS') or (os.path.join(ROOT, 'droids', os.environ['DROID'] + '.json') if os.environ.get('DROID') else '')
        _S = json.load(open(p)) if p and os.path.exists(p) else {}
        if not _S:   # no DROID given (e.g. nightly run inside Blender): find the droid whose current_file is the open .blend
            try:
                import bpy; open_name = os.path.basename(bpy.data.filepath)
            except Exception: open_name = ''
            for f in sorted(os.listdir(os.path.join(ROOT, 'droids'))) if open_name else []:
                if f.endswith('.json') and not f.startswith('_'):
                    d = json.load(open(os.path.join(ROOT, 'droids', f)))
                    if d.get('current_file') == open_name: _S = d; break
    return _S
def get(key, default=None): return settings().get(key, default)
def path(name): return os.path.join(KIT, name)
def out_dir(*sub):
    d = os.path.join(os.environ.get('DROID_OUT', 'out'), *sub); os.makedirs(d, exist_ok=True); return d
def rig_name(): return get('rig', 'RobotRig')
