"""Clean Import: make any downloaded model usable in one click."""
import os
import bpy
import bmesh
from mathutils import Vector

LABEL, ICON, GROUP = 'Clean Import', 'IMPORT', 'Assets'

IMPORTERS = {
    '.fbx': lambda p: bpy.ops.import_scene.fbx(filepath=p),
    '.obj': lambda p: bpy.ops.wm.obj_import(filepath=p),
    '.glb': lambda p: bpy.ops.import_scene.gltf(filepath=p),
    '.gltf': lambda p: bpy.ops.import_scene.gltf(filepath=p),
    '.stl': lambda p: bpy.ops.wm.stl_import(filepath=p),
    '.ply': lambda p: bpy.ops.wm.ply_import(filepath=p),
    '.usd': lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.usdz': lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.usdc': lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.dae': lambda p: bpy.ops.wm.collada_import(filepath=p),
}


def clean_objects(context, objs, target_height=0.0, max_faces=0, merge=True, name=''):
    meshes = [o for o in objs if o.type == 'MESH']
    report = []
    # make single-user so cleanup never touches other files' data
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()
    # 1. apply transforms (fix 100x FBX scale and odd rotations)
    for o in meshes:
        mw = o.matrix_world.copy()
        if o.parent:
            o.parent = None
            o.matrix_world = mw
        o.data.transform(mw)
        o.matrix_world.identity()
    # 2. per-mesh fixes
    for o in meshes:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        before = len(bm.verts)
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context='VERTS')
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
        if before - len(o.data.vertices):
            report.append(f'{o.name}: merged {before - len(o.data.vertices)} verts')
        if max_faces and len(o.data.polygons) > max_faces:
            m = o.modifiers.new('CTK Simplify', 'DECIMATE')
            m.ratio = max(0.02, max_faces / len(o.data.polygons))
            report.append(f'{o.name}: simplified to ~{max_faces} faces')
        try:
            o.data.shade_smooth_by_angle() if hasattr(o.data, 'shade_smooth_by_angle') else None
        except Exception:
            pass
    # remove empties left over from importers
    for o in list(objs):
        if o.type == 'EMPTY' and not o.children:
            bpy.data.objects.remove(o)
    if not meshes:
        return report
    # 3. scale to a target height and sit on the floor, origin at the bottom centre
    lo = Vector((min(v.co.x for o in meshes for v in o.data.vertices), min(v.co.y for o in meshes for v in o.data.vertices), min(v.co.z for o in meshes for v in o.data.vertices)))
    hi = Vector((max(v.co.x for o in meshes for v in o.data.vertices), max(v.co.y for o in meshes for v in o.data.vertices), max(v.co.z for o in meshes for v in o.data.vertices)))
    size = hi - lo
    s = (target_height / size.z) if target_height and size.z > 1e-6 else 1.0
    base = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    from mathutils import Matrix
    T = Matrix.Scale(s, 4) @ Matrix.Translation(-base)
    for o in meshes:
        o.data.transform(T)
        o.location = context.scene.cursor.location.copy()
    # 4. names and textures
    if name:
        for i, o in enumerate(meshes):
            o.name = name if len(meshes) == 1 else f'{name}_{i + 1:02d}'
            o.data.name = o.name
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    report.append(f'{len(meshes)} meshes cleaned, height {size.z * s:.2f} m')
    return report


class CTK_OT_clean_selected(bpy.types.Operator):
    """Fix scale, normals, origins, duplicates and heavy meshes on the selected objects"""
    bl_idname = 'ctk.clean_selected'
    bl_label = 'Clean selected'
    bl_options = {'REGISTER', 'UNDO'}
    target_height: bpy.props.FloatProperty(name='Height (m, 0 = keep)', default=0.0, min=0.0, unit='LENGTH')
    max_faces: bpy.props.IntProperty(name='Max faces (0 = keep)', default=0, min=0)
    merge: bpy.props.BoolProperty(name='Merge duplicate points', default=True)
    name: bpy.props.StringProperty(name='Rename to')

    def execute(self, context):
        objs = list(context.selected_objects)
        if not objs:
            self.report({'WARNING'}, 'Select something first')
            return {'CANCELLED'}
        rep = clean_objects(context, objs, self.target_height, self.max_faces, self.merge, self.name)
        self.report({'INFO'}, '; '.join(rep[-3:]))
        return {'FINISHED'}


class CTK_OT_import_clean(bpy.types.Operator):
    """Import a model (FBX, OBJ, glTF, STL, PLY, USD) and clean it"""
    bl_idname = 'ctk.import_clean'
    bl_label = 'Import and clean'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.fbx;*.obj;*.glb;*.gltf;*.stl;*.ply;*.usd;*.usdz;*.usdc;*.dae', options={'HIDDEN'})
    target_height: bpy.props.FloatProperty(name='Height (m, 0 = keep)', default=0.0, min=0.0, unit='LENGTH')
    max_faces: bpy.props.IntProperty(name='Max faces (0 = keep)', default=50000, min=0)
    save_to_vault: bpy.props.BoolProperty(name='Then save to Vault', default=False)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        ext = os.path.splitext(self.filepath)[1].lower()
        imp = IMPORTERS.get(ext)
        if not imp:
            self.report({'WARNING'}, f'Unsupported file type {ext}')
            return {'CANCELLED'}
        before = set(bpy.data.objects)
        imp(self.filepath)
        new = [o for o in bpy.data.objects if o not in before]
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        rep = clean_objects(context, new, self.target_height, self.max_faces, True, name)
        for o in context.selected_objects:
            o.select_set(False)
        for o in new:
            if o.name in bpy.data.objects:
                o.select_set(True)
                context.view_layer.objects.active = o
        if self.save_to_vault:
            bpy.ops.ctk.vault_save('INVOKE_DEFAULT', kind='OBJECTS', name=name)
        self.report({'INFO'}, '; '.join(rep[-2:]))
        return {'FINISHED'}


CLASSES = (CTK_OT_clean_selected, CTK_OT_import_clean)


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('ctk.import_clean', icon='IMPORT')
    row.operator('ctk.clean_selected', icon='BRUSH_DATA')
