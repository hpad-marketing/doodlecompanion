"""Render-queue wrapper: lock sheet for the tracked porter on the GPU.
args after --: <droid blend> <outdir> [samples]"""
import os, sys, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, '..', '..', '_shared', 'droid-kit')
os.environ['DROID_SETTINGS'] = os.path.join(HERE, 'tracker.json')
os.environ['DROID'] = 'tracker'
a = sys.argv[sys.argv.index('--') + 1:]
sys.argv = ['lock_sheet.py', '--'] + a
runpy.run_path(os.path.join(KIT, 'tools', 'lock_sheet.py'), run_name='__main__')
