"""Build the droid sitcom suite as one folder + zip for Sushi.

    python3 blender-addons/package_sitcom.py <out dir>

Needs a tree with every part merged in: ship_builder, ship_foley, droid_voice
and blender-toolkit/droid-kit. Writes:

    Sitcom_Suite-<date>/
        ship_builder-<v>.zip, ship_foley-<v>.zip   Blender extensions
        droid_voice/                                 plain package -> Blender's scripts/modules
        _droid_kit/                                  -> Documents/DeepInDoodles/_shared/droid-kit (adds missing files only)
        install_suite.py, INSTALL.cmd                one double-click install into every Blender 4.2+
    Sitcom_Suite-<date>.zip
"""
import datetime
import fnmatch
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EXTS = ("ship_builder", "ship_foley")
SKIP = ("__pycache__", ".git", "tests", "out", "*.zip", "*.pyc", "*.blend1")

INSTALL_PY = r'''"""Run by INSTALL.cmd inside each Blender: extensions, droid_voice, prefs."""
import bpy, glob, os, shutil, sys
here = os.path.dirname(os.path.abspath(__file__))
docs = os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles")
mods = bpy.utils.user_resource("SCRIPTS", path="modules", create=True)
shutil.copytree(os.path.join(here, "droid_voice"), os.path.join(mods, "droid_voice"), dirs_exist_ok=True)
kit = os.path.join(docs, "_shared", "droid-kit")
src = os.path.join(here, "_droid_kit")
for base, _dirs, files in os.walk(src):   # add what is missing; never overwrite the droid threads' own copy
    for fn in files:
        d = os.path.join(kit, os.path.relpath(os.path.join(base, fn), src))
        if not os.path.exists(d):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(os.path.join(base, fn), d)
ok = []
for z in sorted(glob.glob(os.path.join(here, "*.zip"))):
    try:
        bpy.ops.extensions.package_install_files(filepath=z, repo="user_default", enable_on_install=True)
        ok.append(os.path.basename(z))
    except Exception as e:
        print("INSTALL FAILED", z, e)
for m in ("ship_builder", "ship_foley"):
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default." + m)
    except Exception as e:
        print("enable", m, e)
prefs = bpy.context.preferences.addons.get("bl_ext.user_default.ship_builder")
if prefs and prefs.preferences:
    p = prefs.preferences
    p.deep_root = docs
    p.kit_dir = kit
cy = bpy.context.preferences.addons.get("cycles")
if cy:
    try:
        cy.preferences.compute_device_type = "OPTIX"
        cy.preferences.get_devices()
        for d in cy.preferences.devices:
            d.use = True
    except Exception as e:
        print("optix", e)
bpy.ops.wm.save_userpref()
import addon_utils
print("SUITE INSTALLED", bpy.app.version_string, ok,
      [m for m in ("bl_ext.user_default.ship_builder", "bl_ext.user_default.ship_foley") if addon_utils.check(m)[1]])
'''

INSTALL_CMD = r'''@echo off
rem Droid sitcom suite: installs into every Blender 4.2+ in Program Files. Close Blender first.
setlocal enabledelayedexpansion
set HERE=%~dp0
set FOUND=0
for /d %%B in ("C:\Program Files\Blender Foundation\Blender *") do (
  if exist "%%B\blender.exe" (
    echo === %%~nxB
    "%%B\blender.exe" -b --python-exit-code 1 --python "%HERE%install_suite.py" 2>&1 | findstr /b /c:"SUITE" /c:"INSTALL FAILED" /c:"Error"
    set FOUND=1
  )
)
if "%FOUND%"=="0" echo No Blender found in C:\Program Files\Blender Foundation
echo.
echo Done. Open Blender: Window ^> Ship Studio.
pause
'''


def manifest_version(d):
    with open(os.path.join(d, "blender_manifest.toml"), encoding="utf-8") as f:
        return re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M).group(1)


def skipped(name):
    return any(fnmatch.fnmatch(name, p) for p in SKIP)


def zip_ext(src, dst):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if not skipped(d)]
            for fn in files:
                if not skipped(fn):
                    p = os.path.join(base, fn)
                    z.write(p, os.path.relpath(p, src))


def copy_tree(src, dst):
    shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if skipped(n)], dirs_exist_ok=True)


def build(out):
    stamp = datetime.date.today().isoformat()
    name = f"Sitcom_Suite-{stamp}"
    dst = os.path.join(out, name)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    parts = {}
    for ext in EXTS:
        src = os.path.join(HERE, ext)
        if not os.path.isdir(src):
            sys.exit(f"missing {ext}: merge its branch first")
        v = manifest_version(src)
        zip_ext(src, os.path.join(dst, f"{ext}-{v}.zip"))
        parts[ext] = v
    dv = os.path.join(HERE, "droid_voice")
    kit = os.path.join(REPO, "blender-toolkit", "droid-kit")
    for need in (dv, kit):
        if not os.path.isdir(need):
            sys.exit(f"missing {need}: merge its branch first")
    copy_tree(dv, os.path.join(dst, "droid_voice"))
    copy_tree(kit, os.path.join(dst, "_droid_kit"))
    with open(os.path.join(dv, "__init__.py"), encoding="utf-8") as f:
        parts["droid_voice"] = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    with open(os.path.join(kit, "VERSION"), encoding="utf-8") as f:
        parts["droid_kit"] = f.read().strip()
    with open(os.path.join(dst, "install_suite.py"), "w", encoding="utf-8") as f:
        f.write(INSTALL_PY)
    with open(os.path.join(dst, "INSTALL.cmd"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(INSTALL_CMD)
    with open(os.path.join(dst, "VERSIONS.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"{k} {v}" for k, v in parts.items()) + "\n")
    zp = shutil.make_archive(dst, "zip", out, name)
    return dst, zp, parts


if __name__ == "__main__":
    d, z, parts = build(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "dist"))
    print("SUITE", z, os.path.getsize(z) // 1024, "KB", parts)
