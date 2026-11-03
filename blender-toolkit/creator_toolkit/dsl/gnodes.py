"""Blender version shims for the add-on (the same as blender-bunny lib/compat.py gn_* helpers)."""


# Geometry Nodes modifier inputs. Up to 5.1 they are ID properties on the modifier
# (mod["Socket_2"] = 1.0, driver path '["Socket_2"]'). 5.2 drops ID properties there:
# the values live at mod.properties.inputs.Socket_2.value.
def gn_inputs(mod):
    p = getattr(mod, 'properties', None)
    return getattr(p, 'inputs', None) if p is not None else None


def gn_has(mod, ident):
    if ident is None:
        return False
    ins = gn_inputs(mod)
    return hasattr(ins, ident) if ins is not None else ident in mod.keys()


def gn_get(mod, ident, default=None):
    ins = gn_inputs(mod)
    if ins is None:
        return mod.get(ident, default)
    s = getattr(ins, ident, None)
    return default if s is None else s.value


def gn_set(mod, ident, value):
    ins = gn_inputs(mod)
    if ins is None:
        mod[ident] = value
    else:
        getattr(ins, ident).value = value


def gn_socket(mod, ident):
    """(struct, data path) to key, drive or un-drive one modifier input: (mod, '["Socket_2"]')
    up to 5.1, (mod.properties.inputs.Socket_2, 'value') on 5.2."""
    ins = gn_inputs(mod)
    return (mod, f'["{ident}"]') if ins is None else (getattr(ins, ident), 'value')


def gn_driver_add(mod, ident):
    owner, path = gn_socket(mod, ident)
    return owner.driver_add(path)


# Node options. 5.0 and 5.1 turned some node enums into menu input sockets (Fill Curve Mode,
# String to Curves Align X/Y and Font, Resample Mode, Transform Mode), and 5.2 shows only the
# sockets of the chosen data type (Random Value, Compare), so inputs[2] is no longer "Min".
def _norm(x):
    import re
    return re.sub(r'[^a-z0-9]', '', str(x).lower())


def set_option(node, key, value):
    """node.key = value, or the menu socket that replaced it ('NGONS' finds 'N-gons')."""
    if hasattr(node, key):
        setattr(node, key, value)
        return
    sock = node.inputs.get(key.replace('_', ' ').title())
    if sock is None:
        raise AttributeError(f'{node.bl_idname} has no {key}')
    try:
        sock.default_value = value
        return
    except (TypeError, ValueError) as e:
        import re
        if not isinstance(value, str):
            raise
        items = re.findall(r"'([^']*)'", str(e).split('not found in', 1)[-1])
    hit = next((i for i in items if _norm(i) == _norm(value)), None)
    if hit is None:
        raise AttributeError(f'{node.bl_idname} {key}: no option {value!r} in {items}')
    sock.default_value = hit


def sock(sockets, name):
    """The live socket called `name` (4.x keeps one hidden socket per data type)."""
    hit = [s for s in sockets if s.name == name]
    return next((s for s in hit if s.enabled), hit[0] if hit else None)
