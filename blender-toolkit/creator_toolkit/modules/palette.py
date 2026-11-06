"""Palette Painter + brand kits: recolour a scene by role, pull palettes from images."""
import bpy
from . import _util

LABEL, ICON, GROUP = 'Palette Painter', 'COLOR', 'Look'
ROLES = ['main', 'accent', 'background', 'floor', 'extra']
BUILTIN = {
    'Doodle ink + mustard': ['#E0A64B', '#1F1F1D', '#F2E6CF', '#C9B48F', '#7A6A4F'],
    'Sunbaked': ['#E07A3F', '#2E4057', '#F6E7CB', '#D9A066', '#8C4A2F'],
    'Teal + coral': ['#FF7F6B', '#16697A', '#E8F1F2', '#82C0CC', '#FFA62B'],
    'Playroom': ['#FF5E5B', '#00A6A6', '#FFF1D0', '#F4D35E', '#5C80BC'],
    'Dusk': ['#F28F3B', '#2D3047', '#E8D7F1', '#93B7BE', '#C8553D'],
    'Sage': ['#8FA67A', '#3E4A3D', '#F1EFE3', '#C9C3A3', '#B5651D'],
    'Midnight': ['#F2C14E', '#0B132B', '#1C2541', '#3A506B', '#5BC0BE'],
    'Mono': ['#222222', '#E04F4F', '#F5F5F0', '#BBBBBB', '#777777'],
}


def kits():
    k = dict(BUILTIN)
    k.update(_util.load_json('brand_kits.json', {}))
    return k


def _kit_items(self, context):
    return [(k, k, '') for k in sorted(kits())]


def auto_roles(context, objs):
    """Guess a role per material: floor-like, background (biggest), main, accent, extra."""
    sized = []
    for o in objs:
        if o.type != 'MESH' or o.get('dm_lock'):
            continue
        d = o.dimensions
        sized.append((d.x * d.y + d.y * d.z + d.x * d.z, o))
    sized.sort(key=lambda t: -t[0])
    seen = {}
    order = ['main', 'accent', 'extra']
    i = 0
    for area, o in sized:
        flat = o.dimensions.z < 0.05 * max(o.dimensions.x, o.dimensions.y, 1e-6)
        for s in o.material_slots:
            m = s.material
            if not m or m.name in seen or m.get('ctk_role'):
                seen.setdefault(m.name if m else '', 1)
                continue
            name = (o.name + m.name).lower()
            if flat or 'floor' in name or 'ground' in name:
                role = 'floor'
            elif any(w in name for w in ('wall', 'backdrop', 'sky', 'bg', 'background')) or (sized and o is sized[0][1] and len(sized) > 2):
                role = 'background'
            else:
                role = order[i % 3]
                i += 1
            m['ctk_role'] = role
            seen[m.name] = 1


def set_material_color(m, rgb):
    m.diffuse_color = (*rgb, 1)
    if not m.use_nodes:
        return
    for n in m.node_tree.nodes:
        if n.type == 'GROUP' and 'Color' in n.inputs:
            n.inputs['Color'].default_value = (*rgb, 1)
        elif n.type == 'BSDF_PRINCIPLED':
            n.inputs['Base Color'].default_value = (*rgb, 1)
        elif n.type in ('EMISSION', 'BSDF_DIFFUSE') and n.inputs['Color'].default_value[:3] != (0.0, 0.0, 0.0):
            if not m.name.startswith('CTK Ink'):
                n.inputs['Color'].default_value = (*rgb, 1)
        elif n.type == 'MIX_RGB' and n.blend_type == 'MULTIPLY' and not n.inputs[2].is_linked:
            n.inputs[2].default_value = (*rgb, 1)


class CTK_OT_palette_apply(bpy.types.Operator):
    """Recolour every material by its role (main, accent, background, floor). Objects marked 'keep colours' are skipped"""
    bl_idname = 'ctk.palette_apply'
    bl_label = 'Apply palette'
    bl_options = {'REGISTER', 'UNDO'}
    kit: bpy.props.EnumProperty(name='Palette', items=_kit_items)
    reguess: bpy.props.BoolProperty(name='Guess roles again', default=False)

    def execute(self, context):
        objs = [o for o in context.scene.objects if not o.get('dm_lock')]
        if self.reguess:
            for o in objs:
                for s in o.material_slots:
                    if s.material and 'ctk_role' in s.material:
                        del s.material['ctk_role']
        auto_roles(context, objs)
        cols = [_util.hex_to_linear(h) for h in kits()[self.kit]]
        n = 0
        done = set()
        for o in objs:
            for s in o.material_slots:
                m = s.material
                if not m or m.name in done or m.name.startswith('CTK Ink') or m.get('dm_lock'):
                    continue
                role = m.get('ctk_role', 'extra')
                set_material_color(m, cols[ROLES.index(role) % len(cols)])
                done.add(m.name)
                n += 1
        context.scene['ctk_palette'] = self.kit
        self.report({'INFO'}, f'{n} materials recoloured')
        return {'FINISHED'}


class CTK_OT_palette_set_role(bpy.types.Operator):
    """Set the role of the active material"""
    bl_idname = 'ctk.palette_set_role'
    bl_label = 'Set role'
    bl_options = {'REGISTER', 'UNDO'}
    role: bpy.props.EnumProperty(items=[(r, r.title(), '') for r in ROLES])

    def execute(self, context):
        for o in context.selected_objects:
            for s in o.material_slots:
                if s.material:
                    s.material['ctk_role'] = self.role
        return {'FINISHED'}


class CTK_OT_palette_lock(bpy.types.Operator):
    """Keep the selected objects' colours when a palette is applied"""
    bl_idname = 'ctk.palette_lock'
    bl_label = 'Keep colours'
    bl_options = {'REGISTER', 'UNDO'}
    lock: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        for o in context.selected_objects:
            o['dm_lock'] = self.lock
        return {'FINISHED'}


class CTK_OT_palette_from_image(bpy.types.Operator):
    """Pull a 5-colour palette from an image and save it as a brand kit"""
    bl_idname = 'ctk.palette_from_image'
    bl_label = 'Palette from image'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.png;*.jpg;*.jpeg;*.webp;*.tif;*.bmp', options={'HIDDEN'})
    name: bpy.props.StringProperty(name='Kit name', default='')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        img = bpy.data.images.load(self.filepath, check_existing=False)
        try:
            hexes = extract_palette(img, 5)
        finally:
            bpy.data.images.remove(img)
        import os
        name = self.name or os.path.splitext(os.path.basename(self.filepath))[0]
        mine = _util.load_json('brand_kits.json', {})
        mine[name] = hexes
        _util.save_json('brand_kits.json', mine)
        self.report({'INFO'}, f'Brand kit "{name}": ' + ' '.join(hexes))
        return {'FINISHED'}


def extract_palette(img, k=5):
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    px = px[px[:, 3] > 0.5][:, :3]
    if len(px) > 20000:
        px = px[np.random.default_rng(1).choice(len(px), 20000, replace=False)]
    if len(px) == 0:
        return BUILTIN['Mono']
    # k-means++ seeding, 12 iterations
    rng = np.random.default_rng(2)
    cents = [px[rng.integers(len(px))]]
    for _ in range(k - 1):
        d = np.min([((px - c) ** 2).sum(1) for c in cents], axis=0)
        cents.append(px[rng.choice(len(px), p=d / d.sum())] if d.sum() > 0 else px[rng.integers(len(px))])
    cents = np.array(cents)
    for _ in range(12):
        lab = np.argmin(((px[:, None, :] - cents[None]) ** 2).sum(2), axis=1)
        for i in range(k):
            if (lab == i).any():
                cents[i] = px[lab == i].mean(0)
    counts = np.bincount(lab, minlength=k)
    order = np.argsort(-counts)
    # roles: most vivid -> main, next vivid -> accent, lightest -> background, mid -> floor
    cs = [cents[i] for i in order]
    sat = [max(c) - min(c) for c in cs]
    lum = [0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in cs]
    idx = list(range(len(cs)))
    main = max(idx, key=lambda i: sat[i] * (counts[order[i]] ** 0.3)); idx.remove(main)
    accent = max(idx, key=lambda i: sat[i] + abs(lum[i] - lum[main])); idx.remove(accent)
    bg = max(idx, key=lambda i: lum[i]); idx.remove(bg)
    rest = sorted(idx, key=lambda i: -counts[order[i]])
    final = [cs[main], cs[accent], cs[bg]] + [cs[i] for i in rest]
    return [_util.linear_to_hex(c) for c in final][:k]


class CTK_OT_palette_save_scene(bpy.types.Operator):
    """Save the scene's current role colours as a brand kit"""
    bl_idname = 'ctk.palette_save_scene'
    bl_label = 'Save scene colours as kit'
    name: bpy.props.StringProperty(name='Kit name', default='Client kit')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .style import base_color
        found = {}
        for o in context.scene.objects:
            for s in o.material_slots:
                m = s.material
                if m and m.get('ctk_role') and m['ctk_role'] not in found:
                    found[m['ctk_role']] = _util.linear_to_hex(base_color(m))
        if not found:
            self.report({'WARNING'}, 'Apply a palette or set roles first')
            return {'CANCELLED'}
        hexes = [found.get(r, '#808080') for r in ROLES]
        mine = _util.load_json('brand_kits.json', {})
        mine[self.name] = hexes
        _util.save_json('brand_kits.json', mine)
        return {'FINISHED'}


CLASSES = (CTK_OT_palette_apply, CTK_OT_palette_set_role, CTK_OT_palette_lock,
           CTK_OT_palette_from_image, CTK_OT_palette_save_scene)


def draw(layout, context):
    layout.operator_menu_enum('ctk.palette_apply', 'kit', text='Apply palette / brand kit', icon='COLOR')
    cur = context.scene.get('ctk_palette')
    if cur and cur in kits():
        row = layout.row(align=True)
        for h in kits()[cur]:
            row.label(text=h)
    row = layout.row(align=True)
    row.label(text='Role of selected:')
    row.operator_menu_enum('ctk.palette_set_role', 'role', text='Set')
    row = layout.row(align=True)
    row.operator('ctk.palette_lock', text='Keep colours', icon='LOCKED').lock = True
    row.operator('ctk.palette_lock', text='Unlock', icon='UNLOCKED').lock = False
    row = layout.row(align=True)
    row.operator('ctk.palette_from_image', icon='IMAGE_DATA')
    row.operator('ctk.palette_save_scene', icon='ADD', text='Save kit')
