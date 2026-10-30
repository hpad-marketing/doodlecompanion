"""Merge index_parts/*.json into library.json, keeping anything the user saved, rows from other
tools (mocap, performance motions) and usage counts.   python3 merge_index.py LIBRARY_DIR

The add-on does the same by itself whenever a library update brings newer index parts."""
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, '..', 'doodle_library', 'index.py'), encoding='utf-8').read()
ns = {'__name__': 'dsl_index_merge'}
# only the merge needs to run here (no bpy): pull out merge_parts and its constants
start = src.index('KEEP = ')
end = src.index('def _parts_newer')
exec('import json, os\n' + src[start:end], ns)
ns['merge_parts'](sys.argv[1], quiet=False)
