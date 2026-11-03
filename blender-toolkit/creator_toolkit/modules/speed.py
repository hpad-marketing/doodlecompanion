"""Heavy scene / Final switch: one click makes a big scene light to work in, one click puts
every setting back for the final render."""
import bpy

LABEL, ICON, GROUP = 'Heavy scene switch', 'MEMORY', 'Setup'

# (owner getter, property, heavy-scene value)
SETTINGS = [
    (lambda s: s.render, 'use_simplify', True),
    (lambda s: s.render, 'simplify_subdivision', 1),
    (lambda s: s.render, 'simplify_child_particles', 0.2),
    (lambda s: s.render, 'simplify_volumes', 0.3),
    (lambda s: s.render, 'use_texture_cache', True),                 # 5.2: mip-mapped texture cache
    (lambda s: s.render, 'use_auto_generate_texture_cache', True),   # 5.2
    (lambda s: s.eevee, 'shadow_resolution_scale', 0.5),
    (lambda s: s.eevee, 'use_shadow_jitter_viewport', False),
    (lambda s: s.eevee, 'use_raytracing', False),
    (lambda s: s.eevee, 'fast_gi_resolution', '4'),
    (lambda s: s.eevee, 'volumetric_tile_size', '16'),
    (lambda s: s.eevee, 'volumetric_samples', 32),
    (lambda s: s.eevee, 'taa_samples', 8),
]
PREFS = [('gl_texture_limit', 'CLAMP_1024')]


def is_heavy(scene):
    return bool(scene.get('ctk_heavy'))


def set_heavy(scene, on):
    if on == is_heavy(scene):
        return 0
    n = 0
    if on:
        keep = {}
        for get, prop, val in SETTINGS:
            owner = get(scene)
            if not hasattr(owner, prop):
                continue  # older Blender: skip 5.2-only settings
            keep[prop] = getattr(owner, prop)
            try:
                setattr(owner, prop, val)
                n += 1
            except (TypeError, ValueError):
                pass
        sysp = bpy.context.preferences.system
        for prop, val in PREFS:
            if hasattr(sysp, prop):
                keep['pref:' + prop] = getattr(sysp, prop)
                try:
                    setattr(sysp, prop, val)
                except (TypeError, ValueError):
                    pass
        scene['ctk_heavy'] = keep
    else:
        keep = dict(scene['ctk_heavy'])
        for get, prop, _ in SETTINGS:
            owner = get(scene)
            if prop in keep and hasattr(owner, prop):
                setattr(owner, prop, keep[prop])
                n += 1
        sysp = bpy.context.preferences.system
        for prop, _ in PREFS:
            if 'pref:' + prop in keep:
                setattr(sysp, prop, keep['pref:' + prop])
        del scene['ctk_heavy']
    return n


class CTK_OT_heavy(bpy.types.Operator):
    """Switch between a light working scene and full final quality"""
    bl_idname = 'ctk.heavy_scene'
    bl_label = 'Heavy scene'
    on: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        n = set_heavy(context.scene, self.on)
        self.report({'INFO'}, ('Light mode: %d settings lowered' if self.on else 'Final quality: %d settings restored') % n)
        return {'FINISHED'}


CLASSES = (CTK_OT_heavy,)


def draw(layout, context):
    on = is_heavy(context.scene)
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator('ctk.heavy_scene', text='Light working mode', icon='MEMORY', depress=on).on = True
    row.operator('ctk.heavy_scene', text='Final quality', icon='RENDER_STILL', depress=not on).on = False
    if on:
        layout.label(text='Remember: switch to Final before rendering', icon='ERROR')
