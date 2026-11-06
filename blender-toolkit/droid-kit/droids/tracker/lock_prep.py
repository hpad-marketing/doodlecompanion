"""copy of the droid file with the look-dev studio (lights, floor, camera) for the lock sheet"""
import bpy, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2])
import stage
stage.setup_studio(engine_gpu=False)
sc = bpy.context.scene; sc.view_settings.view_transform = 'Khronos PBR Neutral'; sc.cycles.device = 'CPU'
bpy.data.objects['TrackerRig'].hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
