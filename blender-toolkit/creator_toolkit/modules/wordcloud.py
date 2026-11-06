"""Word cloud: paste any text and the most-used words pack into a cloud that pops in word by word.

Bigger words are used more. Words never overlap (each one is measured and placed on a spiral),
some turn upright for a classic cloud look, and colours stay on brand: ink and mustard."""
import math
import re
from collections import Counter
import bpy
from mathutils import Vector
from . import _util, kinetic

LABEL, ICON, GROUP = 'Word cloud', 'OUTLINER_OB_FONT', 'Motion design'

STOP = set('''a an the and or but if then than so of to in on at by for with from up down out over
into onto off about as is am are was were be been being it its it's this that these those there here
i me my we our you your he him his she her they them their what which who whom whose when where why
how all any both each few more most other some such no nor not only own same too very can will just
do does did done have has had having would should could may might must shall let lets get got
im youre dont isnt cant wont thats also like really one two'''.split())

COLOURS = [('BOTH', 'Ink + mustard', 'Biggest words in ink, the rest alternate'),
           ('INK', 'Ink only', ''), ('MUSTARD', 'Mustard only', 'For dark backdrops')]


def count_words(text, limit=40, min_len=3):
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text.lower())
    words = [w.strip("'-") for w in words]
    c = Counter(w for w in words if len(w) >= min_len and w not in STOP)
    return c.most_common(limit)


def _overlap(a, b, pad):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _mat(kind):
    return kinetic._mat(_util.hex_to_linear('#1F1F1D' if kind == 'ink' else '#E0A64B'))


def build(context, text, limit=40, size=0.6, upright=0.25, colours='BOTH', frame=None, gap=2,
          font=None, seed=3):
    """Make the cloud at the 3D cursor, standing up and facing -Y. Returns the parent empty."""
    import random
    rnd = random.Random(seed)
    words = count_words(text, limit)
    if not words:
        raise RuntimeError('No words to count (common words like "the" and "and" are skipped)')
    sc = context.scene
    frame = sc.frame_current if frame is None else frame
    top = words[0][1]
    root = bpy.data.objects.new('Word cloud', None)
    root.empty_display_type = 'PLAIN_AXES'
    root.location = sc.cursor.location
    sc.collection.objects.link(root)
    placed, objs = [], []
    for rank, (w, n) in enumerate(words):
        s = size * (0.28 + 0.72 * math.sqrt(n / top))
        cu = bpy.data.curves.new('Cloud ' + w, 'FONT')
        cu.body = w
        cu.size = s
        cu.align_x, cu.align_y = 'CENTER', 'CENTER'
        if font:
            cu.font = font
        o = bpy.data.objects.new('Cloud ' + w, cu)
        sc.collection.objects.link(o)
        o.parent = root
        kind = ('ink' if colours != 'MUSTARD' else 'mustard')
        if colours == 'BOTH' and rank >= 3 and rank % 2:
            kind = 'mustard'
        cu.materials.append(_mat(kind))
        up = rank > 0 and rnd.random() < upright
        o.rotation_euler = (math.radians(90), math.radians(90) if up else 0.0, 0.0)
        context.view_layer.update()
        # the word's real ink box (descenders included), turned the way it will stand
        rot = o.rotation_euler.to_matrix()
        pts = [rot @ Vector(c) for c in o.bound_box]
        x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
        z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
        # walk out along a spiral until this word's box is free
        t, step = 0.0, max(0.01, size * 0.04)
        while True:
            r = 0.18 * size * t / math.tau
            x, z = r * math.cos(t) * 1.6, r * math.sin(t)
            box = (x + x0, z + z0, x + x1, z + z1)
            if not any(_overlap(box, b, size * 0.04) for b in placed):
                break
            t += step / max(r, step)
            if t > 4000:
                break
        placed.append(box)
        o.location = (x, 0.0, z)
        # pop in, one word after another, biggest first
        f = frame + rank * gap
        o.scale = (0, 0, 0)
        o.keyframe_insert('scale', frame=f)
        o.scale = (1.15, 1.15, 1.15)
        o.keyframe_insert('scale', frame=f + 4)
        o.scale = (1, 1, 1)
        o.keyframe_insert('scale', frame=f + 7)
        objs.append(o)
    root['ctk_wordcloud'] = len(objs)
    return root


class CTK_WordCloudProps(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty(name='Text', description='Words to count. Or pick a Text block below')
    source: bpy.props.PointerProperty(name='Text block', type=bpy.types.Text)
    limit: bpy.props.IntProperty(name='Words', default=40, min=3, max=200)
    size: bpy.props.FloatProperty(name='Biggest word', default=0.6, min=0.05, max=10, unit='LENGTH')
    upright: bpy.props.FloatProperty(name='Upright words', default=0.25, min=0, max=1, subtype='FACTOR')
    colours: bpy.props.EnumProperty(name='Colours', items=COLOURS, default='BOTH')
    gap: bpy.props.IntProperty(name='Frames between words', default=2, min=0, max=24)
    seed: bpy.props.IntProperty(name='Shuffle', default=3)


class CTK_OT_word_cloud(bpy.types.Operator):
    """Count the words and build a cloud that pops in at the 3D cursor"""
    bl_idname = 'ctk.word_cloud'
    bl_label = 'Make word cloud'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = context.scene.ctk_wordcloud
        text = p.source.as_string() if p.source else p.text
        try:
            root = build(context, text, p.limit, p.size, p.upright, p.colours, gap=p.gap, seed=p.seed)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Word cloud with {root['ctk_wordcloud']} words")
        return {'FINISHED'}


CLASSES = (CTK_WordCloudProps, CTK_OT_word_cloud)


def register_extra():
    bpy.types.Scene.ctk_wordcloud = bpy.props.PointerProperty(type=CTK_WordCloudProps)


def unregister_extra():
    del bpy.types.Scene.ctk_wordcloud


def draw(layout, context):
    p = context.scene.ctk_wordcloud
    col = layout.column(align=True)
    col.prop(p, 'text', text='')
    col.prop(p, 'source', text='or Text')
    row = layout.row(align=True)
    row.prop(p, 'limit')
    row.prop(p, 'size')
    row = layout.row(align=True)
    row.prop(p, 'upright')
    row.prop(p, 'gap', text='Gap')
    row = layout.row(align=True)
    row.prop(p, 'colours', text='')
    row.prop(p, 'seed')
    row.operator('ctk.word_cloud', text='Make', icon='OUTLINER_OB_FONT')
