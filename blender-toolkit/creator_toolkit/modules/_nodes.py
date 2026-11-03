"""Tiny node-tree builder that works on Blender 4.2 - 5.x.

Socket lookups skip hidden/unavailable sockets, and enum settings fall back to
menu sockets (5.x turned several node enums into 'Mode'-style inputs)."""
import bpy


def _avail(s):
    if hasattr(s, 'is_inactive') and s.is_inactive:
        return False
    return getattr(s, 'enabled', True) and not getattr(s, 'is_unavailable', False)


def sock(coll, key, kind=None):
    if isinstance(key, int):
        return coll[key]
    hits = [s for s in coll if (s.name == key or s.identifier == key)]
    live = [s for s in hits if _avail(s)] or hits
    if kind:
        typed = [s for s in live if s.type == kind]
        live = typed or live
    if not live:
        raise KeyError('%s not in %s' % (key, [s.name for s in coll]))
    return live[0]


def setting(node, prop, value, menu=None):
    """Set an enum on the node, or on its menu socket when the enum became a socket."""
    if hasattr(node, prop):
        try:
            setattr(node, prop, value)
            return
        except (TypeError, ValueError):
            pass
    names = [menu] if menu else []
    names += [prop.replace('_', ' ').title(), 'Mode', 'Method', 'Type']
    for n in names:
        s = next((s for s in node.inputs if s.name == n and s.type == 'MENU'), None)
        if s is None:
            continue
        for cand in (value, value.replace('_', ' ').title(), value.title(), value.capitalize(),
                     value.split('_')[-1].title(), value.split('_')[0].title()):
            try:
                s.default_value = cand
                return
            except (TypeError, ValueError):
                continue
    raise AttributeError('cannot set %s=%s on %s' % (prop, value, node.bl_idname))


class Tree:
    def __init__(self, name, kind='GeometryNodeTree', reuse=True):
        old = bpy.data.node_groups.get(name)
        if old and reuse and old.get('ctk_built'):
            self.tree, self.fresh = old, False
            return
        self.tree = bpy.data.node_groups.new(name, kind)
        self.tree['ctk_built'] = 1
        self.fresh = True
        self.nodes, self.links = self.tree.nodes, self.tree.links
        self.gin = self.nodes.new('NodeGroupInput')
        self.gout = self.nodes.new('NodeGroupOutput')
        self.x = 0

    def socket(self, name, in_out, stype, default=None, lo=None, hi=None):
        s = self.tree.interface.new_socket(name=name, in_out=in_out, socket_type=stype)
        if default is not None and hasattr(s, 'default_value'):
            s.default_value = default
        if lo is not None and hasattr(s, 'min_value'):
            s.min_value = lo
        if hi is not None and hasattr(s, 'max_value'):
            s.max_value = hi
        return s

    def geo_io(self):
        self.socket('Geometry', 'INPUT', 'NodeSocketGeometry')
        self.socket('Geometry', 'OUTPUT', 'NodeSocketGeometry')

    def n(self, idname, **kw):
        node = self.nodes.new(idname)
        self.x += 200
        node.location = (self.x, 0)
        for k, v in kw.items():
            if k.startswith('i_'):
                sock(node.inputs, k[2:].replace('__', ' ')).default_value = v
            else:
                setting(node, k, v)
        return node

    def i(self, name):
        return sock(self.gin.outputs, name)

    def link(self, a, b):
        self.links.new(a, b)

    def out(self, sock_):
        self.links.new(sock_, sock(self.gout.inputs, 'Geometry'))
        self.gout.location = (self.x + 250, 0)
        self.gin.location = (-250, 0)


def O(node, key, kind=None):
    return sock(node.outputs, key, kind)


def I(node, key, kind=None):
    return sock(node.inputs, key, kind)


def group_inputs(group):
    return [it for it in group.interface.items_tree
            if getattr(it, 'item_type', 'SOCKET') == 'SOCKET' and it.in_out == 'INPUT'
            and it.socket_type != 'NodeSocketGeometry']


def input_slot(mod, identifier):
    """(owner, property path) for one modifier input: 5.2 keeps them in mod.properties.inputs,
    earlier versions in ID properties on the modifier."""
    props = getattr(mod, 'properties', None)
    ins = getattr(props, 'inputs', None) if props is not None else None
    if ins is not None and hasattr(ins, identifier):
        return getattr(ins, identifier), 'value'
    return mod, '["%s"]' % identifier


def get_input(mod, name):
    for it in group_inputs(mod.node_group):
        if it.name == name:
            owner, path = input_slot(mod, it.identifier)
            return owner.value if path == 'value' else mod[it.identifier]
    raise KeyError(name)


def draw_modifier_inputs(layout, mod):
    if not mod or not mod.node_group:
        return
    col = layout.column(align=True)
    coll = {'NodeSocketObject': 'objects', 'NodeSocketCollection': 'collections',
            'NodeSocketMaterial': 'materials', 'NodeSocketImage': 'images'}
    for it in group_inputs(mod.node_group):
        try:
            owner, path = input_slot(mod, it.identifier)
            if path != 'value' and it.socket_type in coll:
                col.prop_search(owner, path, bpy.data, coll[it.socket_type], text=it.name)
            else:
                col.prop(owner, path, text=it.name)
        except Exception:
            pass


def set_input(mod, name, value):
    for it in group_inputs(mod.node_group):
        if it.name == name:
            owner, path = input_slot(mod, it.identifier)
            if path == 'value':
                owner.value = value
            else:
                mod[it.identifier] = value
            return True
    return False
