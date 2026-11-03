"""Doodle Studio 3D powers, in any scene: auto-ink, jelly bounce, cheering crowd, scatter,
toon liquids, fisheye lens and 360 video.

They run the same code as Doodle Studio 3D (the 3D Bunny's lib/powers.py). When the 3D Bunny
folder is on this PC its own copy is used; otherwise the copy that ships inside the Toolkit."""
import bpy

LABEL, ICON, GROUP = 'Doodle powers', 'OUTLINER_OB_FORCE_FIELD', 'Procedural & 2D'

SCATTER = [('grass', 'Grass', ''), ('flowers', 'Flowers', ''), ('pebbles', 'Pebbles', ''), ('leaves', 'Leaves', '')]
LIQUID = [('splash', 'Splash', ''), ('pour', 'Pour', ''), ('puddle', 'Puddle', '')]


def _powers():
    from ..dsl import paths
    return paths.bunny_module('powers')


def _log(op):
    return lambda msg: op.report({'INFO'}, msg) if op else print(msg)


def _cam(context):
    cam = context.scene.camera
    if cam is None:
        raise RuntimeError('Add a camera first: ink weight is measured from the camera')
    return cam


class CTK_PowersProps(bpy.types.PropertyGroup):
    scatter_kind: bpy.props.EnumProperty(name='Scatter', items=SCATTER, default='flowers')
    scatter_count: bpy.props.IntProperty(name='Count', default=30, min=1, max=400)
    scatter_radius: bpy.props.FloatProperty(name='Radius', default=1.2, min=0.1, max=20, unit='LENGTH')
    scatter_seed: bpy.props.IntProperty(name='Seed', default=1)
    crowd_count: bpy.props.IntProperty(name='People', default=18, min=1, max=80)
    crowd_rows: bpy.props.IntProperty(name='Rows', default=2, min=1, max=6)
    crowd_distance: bpy.props.FloatProperty(name='Distance', default=2.2, min=0.5, max=20, unit='LENGTH')
    crowd_cheer: bpy.props.BoolProperty(name='Cheer', default=True)
    liquid: bpy.props.EnumProperty(name='Liquid', items=LIQUID, default='splash')
    jelly: bpy.props.FloatProperty(name='Wobble', default=0.22, min=0.02, max=0.6)
    fisheye: bpy.props.FloatProperty(name='Fisheye', default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class CTK_OT_power(bpy.types.Operator):
    """Run one Doodle Studio 3D power on this scene"""
    bl_idname = 'ctk.power'
    bl_label = 'Doodle power'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[
        ('AUTOINK', 'Auto-ink', 'Every model without an outline gets the brand ink line'),
        ('JELLY', 'Jelly bounce', 'Selected objects wobble like jelly from this frame'),
        ('CROWD', 'Crowd', 'Ink silhouettes that bob and cheer behind the action'),
        ('SCATTER', 'Scatter', 'Grass, flowers, pebbles or leaves around the 3D cursor'),
        ('LIQUID', 'Toon liquid', 'Droplets on arcs and a puddle that spreads, at the 3D cursor'),
        ('FISHEYE', 'Fisheye', 'Barrel lens in the compositor'),
        ('PANO360', '360 video', 'Equirectangular camera for a 360 render'),
    ])

    def execute(self, context):
        sc, p, log = context.scene, context.scene.ctk_powers, _log(self)
        try:
            pw = _powers()
            f0 = sc.frame_current - 1  # Doodle Studio counts shot frames from 0
            cur = tuple(sc.cursor.location)
            if self.kind == 'AUTOINK':
                pw.autoink(_cam(context), log)
            elif self.kind == 'JELLY':
                obs = [o for o in context.selected_objects if o.type != 'CAMERA']
                if not obs:
                    raise RuntimeError('Select what should wobble')
                for o in obs:
                    pw.jelly(o, sc.frame_current, p.jelly)
                log(f'Jelly on {len(obs)} objects')
            elif self.kind == 'CROWD':
                pw.crowd({'count': p.crowd_count, 'rows': p.crowd_rows, 'distance': p.crowd_distance,
                          'cheer': p.crowd_cheer}, _cam(context), log)
            elif self.kind == 'SCATTER':
                pw.scatter([{'kind': p.scatter_kind, 'count': p.scatter_count, 'radius': p.scatter_radius,
                             'seed': p.scatter_seed, 'center': cur[:2]}], _cam(context), log)
            elif self.kind == 'LIQUID':
                pw.liquids([{'kind': p.liquid, 'frame': f0, 'at': cur}], _cam(context), log)
            elif self.kind == 'FISHEYE':
                pw.fisheye(p.fisheye, log)
            elif self.kind == 'PANO360':
                pw.pano360(_cam(context), log)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (CTK_PowersProps, CTK_OT_power)


def register_extra():
    bpy.types.Scene.ctk_powers = bpy.props.PointerProperty(type=CTK_PowersProps)


def unregister_extra():
    del bpy.types.Scene.ctk_powers


def draw(layout, context):
    p = context.scene.ctk_powers
    row = layout.row(align=True)
    row.operator('ctk.power', text='Auto-ink', icon='MOD_LINEART').kind = 'AUTOINK'
    row.operator('ctk.power', text='Jelly', icon='MOD_SOFT').kind = 'JELLY'
    row.prop(p, 'jelly', text='Wobble')
    box = layout.box()
    row = box.row(align=True)
    row.prop(p, 'scatter_kind', text='')
    row.operator('ctk.power', text='Scatter at cursor', icon='PARTICLES').kind = 'SCATTER'
    row = box.row(align=True)
    row.prop(p, 'scatter_count')
    row.prop(p, 'scatter_radius')
    row.prop(p, 'scatter_seed')
    box = layout.box()
    row = box.row(align=True)
    row.prop(p, 'crowd_count')
    row.prop(p, 'crowd_rows')
    row = box.row(align=True)
    row.prop(p, 'crowd_distance')
    row.prop(p, 'crowd_cheer')
    row.operator('ctk.power', text='Add crowd', icon='COMMUNITY').kind = 'CROWD'
    row = layout.row(align=True)
    row.prop(p, 'liquid', text='')
    row.operator('ctk.power', text='Liquid at cursor', icon='MOD_FLUIDSIM').kind = 'LIQUID'
    row = layout.row(align=True)
    row.prop(p, 'fisheye', text='Fisheye')
    row.operator('ctk.power', text='Apply', icon='CAMERA_DATA').kind = 'FISHEYE'
    row.operator('ctk.power', text='360 video', icon='WORLD').kind = 'PANO360'
