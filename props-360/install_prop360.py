# Adds the 360° prop library module to the Doodle Studio source on the PC (run from the Talking Character App folder).
# Backs up what it changes, copies src/prop-library-360.js and puts it in the build list just before 'ux-overhaul'.
# It never touches the install folder or Doodle Studio Exports\Backup; build with tools/build_candidate.py afterwards.
import pathlib, shutil, sys, time
ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
HERE = pathlib.Path(__file__).resolve().parent
build = ROOT / 'tools' / 'build_complete.py'
if not build.exists(): sys.exit('Run this from the Talking Character App folder (tools/build_complete.py not found)')
backup = ROOT / 'backups' / ('prop360-' + time.strftime('%Y%m%d-%H%M%S')); backup.mkdir(parents=True)
shutil.copy2(build, backup / 'build_complete.py')
if (ROOT / 'src' / 'prop-library-360.js').exists(): shutil.copy2(ROOT / 'src' / 'prop-library-360.js', backup / 'prop-library-360.js')
shutil.copy2(HERE / 'prop-library-360.js', ROOT / 'src' / 'prop-library-360.js')
s = build.read_text(encoding='utf-8')
if "'prop-library-360'" not in s:
    if s.count(",'ux-overhaul']") != 1: sys.exit("Build list not found: expected exactly one ,'ux-overhaul'] in tools/build_complete.py")
    build.write_text(s.replace(",'ux-overhaul']", ",'prop-library-360','ux-overhaul']"), encoding='utf-8')
print('backup:', backup); print('module installed in src; build list:', "'prop-library-360'" in build.read_text(encoding='utf-8'))
