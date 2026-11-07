"""Give a sidebar a working width.

Blender has no Python setting for a sidebar's width, and its default is too
narrow for the station screens. The region's stored width (ARegion.sizex) is
written directly, but only after the struct is matched field by field against
what the API reports (window rectangle, size, region type), so a Blender whose
layout differs is left alone instead of written to. The layout is the same in
4.5, 5.0 and 5.2: winrct, winx, winy, category_scroll, regiontype, alignment,
flag, sizex.
"""
import ctypes
import struct

import bpy

RGN_TYPE = {"UI": 4, "TOOLS": 5}


def _find(reg, kind):
    raw = bytes((ctypes.c_char * 640).from_address(reg.as_pointer()))
    for w in range(16, 600, 2):
        winx, winy = struct.unpack_from("hh", raw, w)
        if winx != reg.width or winy != reg.height:
            continue
        xmin, xmax, ymin, ymax = struct.unpack_from("iiii", raw, w - 16)
        if xmin != reg.x or ymin != reg.y or xmax - xmin + 1 != reg.width:
            continue
        if struct.unpack_from("h", raw, w + 8)[0] != RGN_TYPE[kind]:
            continue
        return w
    return None


def set_width(area, px, kind="UI"):
    """Sidebar width in unscaled pixels. Returns True when it was set."""
    try:
        reg = next((r for r in area.regions if r.type == kind), None)
        if reg is None or reg.width <= 1:
            return False
        w = _find(reg, kind)
        if w is None:
            return False
        px = int(min(px, max(120, area.width / max(bpy.context.preferences.system.ui_scale, 0.5) - 160)))
        ctypes.c_short.from_address(reg.as_pointer() + w + 14).value = px
        # hide and show once so the area lays out again with the new width
        win = next(wi for wi in bpy.context.window_manager.windows for a in wi.screen.areas if a == area)
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=reg):
            bpy.ops.screen.region_toggle(region_type=kind)
            bpy.ops.screen.region_toggle(region_type=kind)
        area.tag_redraw()
        return True
    except Exception as e:   # never break the studio over a width
        print("Ship Studio: sidebar width not set:", e)
        return False


def later(area, px, kind="UI", tries=10):
    """Set the width once the area has been drawn (regions have no size before that)."""
    ptr = area.as_pointer()

    def go(n=[tries]):
        for win in bpy.context.window_manager.windows:
            for a in win.screen.areas:
                if a.as_pointer() == ptr:
                    reg = next((r for r in a.regions if r.type == kind), None)
                    if reg is not None and reg.width > 1:
                        if reg.width >= px * bpy.context.preferences.system.ui_scale * 0.9:
                            return None
                        set_width(a, px, kind)
                        return None
        n[0] -= 1
        return 0.2 if n[0] > 0 else None
    bpy.app.timers.register(go, first_interval=0.2)
