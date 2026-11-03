import os
import json
import bpy


def addon_prefs():
    pkg = __package__.rsplit('.', 1)[0]
    a = bpy.context.preferences.addons.get(pkg)
    return a.preferences if a else None


def vault_dir():
    p = addon_prefs()
    d = (p.vault_dir if p and p.vault_dir else '') or os.environ.get('CTK_VAULT_DIR') or os.path.join(os.path.expanduser('~'), 'Documents', 'Creator Vault')
    d = bpy.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d


def load_json(name, default):
    path = os.path.join(vault_dir(), name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(name, data):
    path = os.path.join(vault_dir(), name)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)
    return path


def hex_to_linear(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def linear_to_hex(rgb):
    out = []
    for x in rgb[:3]:
        x = max(0.0, min(1.0, x))
        s = x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        out.append(int(round(s * 255)))
    return '#%02X%02X%02X' % tuple(out)


def selected_meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


def key_value(obj, path, frame, value, index=-1):
    if index >= 0:
        getattr(obj, path)[index] = value
        obj.keyframe_insert(path, index=index, frame=frame)
    else:
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=frame)
