"""Node tidying: lay out messy node trees in clean columns, frame and clear unused nodes.
Also switches on Blender's bundled Node Wrangler."""
import bpy

LABEL, ICON, GROUP = 'Node tidy', 'NODETREE', 'Procedural & 2D'


def _height(n):
    if n.dimensions.y > 1:
        return n.dimensions.y
    if n.type == 'REROUTE':
        return 20
    if n.type == 'FRAME':
        return 0
    socks = [s for s in list(n.inputs) + list(n.outputs) if getattr(s, 'enabled', True) and not s.hide]
    return 60 + 22 * len(socks)


def _width(n):
    return n.dimensions.x if n.dimensions.x > 1 else n.width


def _outputs(tree):
    outs = [n for n in tree.nodes if n.type in ('OUTPUT_MATERIAL', 'OUTPUT_WORLD', 'GROUP_OUTPUT', 'COMPOSITE',
                                                 'OUTPUT_LIGHT', 'VIEWER', 'OUTPUT_FILE')]
    if not outs:
        has_out = {l.from_node for l in tree.links}
        outs = [n for n in tree.nodes if n not in has_out and n.type != 'FRAME']
    return outs


def tidy(tree, only=None, gap_x=60, gap_y=30):
    nodes = [n for n in tree.nodes if n.type != 'FRAME' and (only is None or n in only)]
    if not nodes:
        return 0
    down = {n: [] for n in nodes}
    for l in tree.links:
        if l.from_node in down and l.to_node in down and not l.is_muted:
            down[l.from_node].append(l.to_node)
    depth = {}

    def d(n, seen=()):
        if n in depth:
            return depth[n]
        if n in seen:
            return 0
        kids = down[n]
        v = 0 if not kids else 1 + max(d(k, seen + (n,)) for k in kids)
        depth[n] = v
        return v
    for n in nodes:
        d(n)
    cols = {}
    for n, v in depth.items():
        cols.setdefault(v, []).append(n)
    right = max((n.location.x + _width(n) for n in nodes if depth[n] == 0), default=0)
    top = max(n.location.y for n in nodes)
    x = right
    for v in sorted(cols):
        col = sorted(cols[v], key=lambda n: -n.location.y)
        w = max(_width(n) for n in col)
        x -= w
        cy = top
        for n in col:
            n.location = (x + (w - _width(n)) / 2 if n.type == 'REROUTE' else x, cy)
            cy -= _height(n) + gap_y
        x -= gap_x
    return len(nodes)


def unused(tree):
    keep = set()
    stack = list(_outputs(tree))
    ups = {}
    for l in tree.links:
        ups.setdefault(l.to_node, []).append(l.from_node)
    while stack:
        n = stack.pop()
        if n in keep:
            continue
        keep.add(n)
        stack.extend(ups.get(n, []))
    return [n for n in tree.nodes if n not in keep and n.type not in ('FRAME', 'GROUP_INPUT', 'GROUP_OUTPUT')]


def trees_for(context):
    sp = context.space_data
    if sp and sp.type == 'NODE_EDITOR' and sp.edit_tree:
        return [sp.edit_tree]
    out = []
    o = context.active_object
    if o:
        for s in o.material_slots:
            if s.material and s.material.node_tree:
                out.append(s.material.node_tree)
        for m in o.modifiers:
            if m.type == 'NODES' and m.node_group:
                out.append(m.node_group)
    return out


class CTK_OT_node_tidy(bpy.types.Operator):
    """Arrange nodes in clean left-to-right columns (whole tree, or only the selected nodes)"""
    bl_idname = 'ctk.node_tidy'
    bl_label = 'Tidy nodes'
    bl_options = {'REGISTER', 'UNDO'}
    selected_only: bpy.props.BoolProperty(name='Selected only', default=False)
    spacing: bpy.props.IntProperty(name='Spacing', default=60, min=10, max=400)

    def execute(self, context):
        n = 0
        for t in trees_for(context):
            only = [x for x in t.nodes if x.select] if self.selected_only else None
            n += tidy(t, only, self.spacing, self.spacing // 2)
        self.report({'INFO'}, f'Tidied {n} nodes')
        return {'FINISHED'}


class CTK_OT_node_clean(bpy.types.Operator):
    """Delete nodes that feed nothing into the output"""
    bl_idname = 'ctk.node_clean'
    bl_label = 'Remove unused nodes'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for t in trees_for(context):
            for x in unused(t):
                t.nodes.remove(x)
                n += 1
        self.report({'INFO'}, f'Removed {n} unused nodes')
        return {'FINISHED'}


class CTK_OT_node_frame(bpy.types.Operator):
    """Put the selected nodes in a labelled, coloured frame"""
    bl_idname = 'ctk.node_frame'
    bl_label = 'Frame selected'
    bl_options = {'REGISTER', 'UNDO'}
    label: bpy.props.StringProperty(name='Label', default='Group')
    color: bpy.props.FloatVectorProperty(name='Colour', subtype='COLOR', size=3, min=0, max=1,
                                         default=(0.55, 0.42, 0.2))

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        for t in trees_for(context):
            sel = [n for n in t.nodes if n.select and n.type != 'FRAME']
            if not sel:
                continue
            f = t.nodes.new('NodeFrame')
            f.label = self.label
            f.use_custom_color = True
            f.color = self.color
            for n in sel:
                loc = n.location.copy()
                n.parent = f
                n.location = loc
        return {'FINISHED'}


class CTK_OT_node_wrangler(bpy.types.Operator):
    """Switch on Blender's bundled Node Wrangler add-on"""
    bl_idname = 'ctk.node_wrangler'
    bl_label = 'Turn on Node Wrangler'

    def execute(self, context):
        import addon_utils
        for name in ('node_wrangler', 'bl_ext.blender_org.node_wrangler'):
            try:
                addon_utils.enable(name, default_set=True, persistent=True)
                if name in context.preferences.addons:
                    self.report({'INFO'}, 'Node Wrangler is on (Ctrl+Shift+click previews a node)')
                    return {'FINISHED'}
            except Exception:
                pass
        self.report({'WARNING'}, 'Node Wrangler not found. Get it from Edit > Preferences > Get Extensions')
        return {'CANCELLED'}


class CTK_PT_nodetidy_editor(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_label = 'Node tidy'

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (CTK_OT_node_tidy, CTK_OT_node_clean, CTK_OT_node_frame, CTK_OT_node_wrangler, CTK_PT_nodetidy_editor)


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('ctk.node_tidy', icon='ALIGN_JUSTIFY')
    row.operator('ctk.node_tidy', text='Selected').selected_only = True
    row = layout.row(align=True)
    row.operator('ctk.node_frame', icon='OBJECT_HIDDEN')
    row.operator('ctk.node_clean', icon='TRASH')
    layout.operator('ctk.node_wrangler', icon='NODETREE')
    if not (context.space_data and context.space_data.type == 'NODE_EDITOR'):
        layout.label(text='Here it tidies the active object\'s materials and node setups', icon='INFO')
