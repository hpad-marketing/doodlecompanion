"""Doodle UX helpers (same file in every Doodle add-on): keep names whole in a narrow sidebar.

wrap(layout, context, text)         a long label broken into lines that fit the sidebar
row_fits(context, texts, ...)       would these buttons fit side by side without cutting their names?
flow(layout, context, texts, ...)   a grid with as many columns as fit (most first), for button sets
"""
import blf
import bpy


def _scale(context):
    try:
        return context.preferences.system.ui_scale
    except Exception:
        return 1.0


def text_px(context, text):
    s = _scale(context)
    try:
        pts = context.preferences.ui_styles[0].widget.points
    except Exception:
        pts = 11
    blf.size(0, pts * s)
    return blf.dimensions(0, text)[0]


def width(context, inset=0):
    """Usable width of the current sidebar in pixels (tab strip and panel margins taken off)."""
    s = _scale(context)
    reg = getattr(context, "region", None)
    w = reg.width if reg is not None and reg.width > 1 else 280 * s
    return max(60 * s, w - 45 * s - inset * 12 * s)


def need(context, text, icon=False):
    s = _scale(context)
    return text_px(context, text) + (18 * s if icon else 0) + 22 * s  # roomy: never pack buttons edge to edge


def row_fits(context, texts, icon=False, inset=0):
    gap = 2 * _scale(context) * max(0, len(texts) - 1)
    return sum(need(context, t, icon) for t in texts) + gap <= width(context, inset)


def columns(context, texts, most=3, icon=False, inset=0):
    """Most columns (<= most) at which the longest text still fits."""
    w = width(context, inset)
    longest = max((need(context, t, icon) for t in texts), default=0)
    n = most
    while n > 1:
        # two side by side may sit a little closer than three or more
        each = longest - (10 * _scale(context) if n == 2 else 0)
        if each * n + 2 * _scale(context) * (n - 1) <= w:
            break
        n -= 1
    return n


def flow(layout, context, texts, most=3, icon=False, inset=0, align=True):
    return layout.grid_flow(row_major=True, columns=columns(context, texts, most, icon, inset),
                            even_columns=True, align=align)


def wrap(layout, context, text, icon="NONE", inset=0, active=True):
    """Label that breaks onto more lines instead of being cut short."""
    w = width(context, inset) - (18 * _scale(context) if icon != "NONE" else 0) - 16 * _scale(context)
    col = layout.column(align=True)
    col.active = active
    lines, line = [], ""
    for word in text.split():
        t = (line + " " + word).strip()
        if line and text_px(context, t) > w:
            lines.append(line)
            line = word
        else:
            line = t
    if line:
        lines.append(line)
    for i, ln in enumerate(lines or [""]):
        col.label(text=ln, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))
    return col
