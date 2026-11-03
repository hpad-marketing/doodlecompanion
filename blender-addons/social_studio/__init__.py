"""Social Studio: turn a Bunny, Froggy, Koala (or any rigged character) scene into a ready-to-post reel.

View3D sidebar > Social. Every tool is one button with sensible defaults; finer settings sit in a
closed Advanced section under it.
"""
import importlib
import os

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty)

from . import core, formats, output, text_tools, timing

for _m in (core, text_tools, timing, formats, output):
    importlib.reload(_m)


def _upd_pacing(self, ctx):
    timing._redraw()


FORMAT_ITEMS = [(k, v[0], '') for k, v in formats.FORMATS.items()]


class SS_Settings(bpy.types.PropertyGroup):
    stroke_px: FloatProperty(name='Line weight (px)', default=14.0, min=2, max=60,
                             description='Stroke width of stickers and bubbles, in pixels on a 1920-tall frame')
    overlay_depth: FloatProperty(name='Overlay depth', default=0.5, min=0.05, max=10, subtype='DISTANCE',
                                 description='How far in front of the lens captions and stickers sit')
    # formats
    reel_format: EnumProperty(name='Format', items=FORMAT_ITEMS + [('NONE', 'None', '')], default='STORYTIME')
    use_script: BoolProperty(name='Use the "Reel Script" text', default=True,
                             description='One line per slot, in the text block called Reel Script')
    # reaction
    react_path: StringProperty(name='Clip or screenshot', subtype='FILE_PATH')
    react_layout: EnumProperty(name='Layout', items=[('PIP', 'Picture in picture', ''), ('SPLIT', 'Split screen', ''),
                                                     ('BOARD', 'Pointing at a board', '')])
    react_side: EnumProperty(name='Clip side', items=[('AUTO', 'Away from the character', ''), ('LEFT', 'Left', ''),
                                                      ('RIGHT', 'Right', '')])
    react_border: BoolProperty(name='Doodle border', default=True)
    # comment
    comment_user: StringProperty(name='Username', default='')
    comment_text: StringProperty(name='Comment', default='')
    comment_where: EnumProperty(name='Where', items=[('TOP', 'Pinned at the top', ''),
                                                     ('BESIDE', 'Beside the character', '')])
    comment_seconds: FloatProperty(name='Stays up (s)', default=3.0, min=0.5, max=60)
    comment_show_user: BoolProperty(name='Show username', default=True)
    comment_style: EnumProperty(name='Bubble', items=[('MUSTARD', 'Mustard', ''), ('INK', 'Ink', '')])
    # captions
    caption_file: StringProperty(name='SRT or transcript', subtype='FILE_PATH')
    caption_size: FloatProperty(name='Size', default=0.056, min=0.015, max=0.12)
    caption_max_words: IntProperty(name='Max words per caption', default=6, min=1, max=14)
    caption_nudge: FloatProperty(name='Nudge up/down', default=0.0, min=-0.2, max=0.2)
    auto_key_words: BoolProperty(name='Pick a key word when none is marked', default=True)
    key_words: StringProperty(name='Always key words', default='', description='Comma separated')
    # stickers
    sticker_kind: EnumProperty(name='Sticker', items=text_tools.STICKER_ITEMS)
    sticker_size: FloatProperty(name='Size', default=0.16, min=0.03, max=0.6)
    sticker_seconds: FloatProperty(name='Stays up (s)', default=1.5, min=0.2, max=30)
    draw_seconds: FloatProperty(name='Draw-on (s)', default=0.3, min=0.0, max=3)
    line_boil: FloatProperty(name='Line boil', default=1.0, min=0.0, max=3.0)
    # beats
    beat_file: StringProperty(name='Track', subtype='FILE_PATH', description='Leave empty to use the sequencer audio')
    beat_every: IntProperty(name='Every Nth beat', default=1, min=1, max=8)
    beat_offset: IntProperty(name='Offset (frames)', default=0, min=-30, max=30)
    beat_sensitivity: FloatProperty(name='Sensitivity', default=0.5, min=0.05, max=0.95)
    beat_steady: BoolProperty(name='Steady tempo grid', default=True)
    bpm: FloatProperty(name='BPM', default=0.0)
    snap_captions: BoolProperty(name='Snap caption pops too', default=True)
    snap_max: IntProperty(name='Max shift (frames)', default=4, min=1, max=15)
    # pacing
    dead_air_seconds: FloatProperty(name='Dead air after (s)', default=2.5, min=0.5, max=10, update=_upd_pacing)
    target_seconds: IntProperty(name='Target length (s)', default=0, min=0, max=600,
                                description='0 uses the format default')
    show_pacing: BoolProperty(name='Show strip on the timeline', default=True, update=_upd_pacing)
    pacing_report: StringProperty(default='')
    # loop
    loop_blend: FloatProperty(name='Blend (s)', default=1.0, min=0.1, max=5)
    loop_camera: BoolProperty(name='Loop the camera too', default=True)
    # sfx
    sfx_volume: FloatProperty(name='Volume', default=0.6, min=0, max=2)
    sfx_limit: IntProperty(name='Max suggestions', default=40, min=1, max=200)
    sfx_cut: EnumProperty(name='On cuts', items=[(k, k.title(), '') for k in timing.SFX_KINDS], default='whoosh')
    sfx_sticker: EnumProperty(name='On stickers', items=[(k, k.title(), '') for k in timing.SFX_KINDS], default='pop')
    # series
    series_name: StringProperty(name='Series', default='')
    series_intro: StringProperty(name='Title card', default='{series}', description='{series} and {ep} are filled in')
    series_intro_seconds: FloatProperty(name='Intro (s)', default=1.2, min=0.3, max=6)
    series_end: StringProperty(name='End card', default='Part {next} next', description='{next} = next episode number')
    numbering: EnumProperty(name='Numbering', items=[('EP', 'Ep 1', ''), ('PART', 'Part 1', ''), ('HASH', '#1', '')])
    episode: IntProperty(name='Episode', default=0, min=0)
    # end cards
    card_kind: EnumProperty(name='Card', items=[(k, v.replace('"{word}"', 'a word').replace("{word}", 'a word'), '')
                                                for k, v in text_tools.CARDS.items()])
    card_word: StringProperty(name='Word', default='LINK')
    card_custom: StringProperty(name='Own wording', default='')
    card_seconds: FloatProperty(name='Length (s)', default=1.8, min=0.5, max=10)
    card_behind: BoolProperty(name='Character stays on the card', default=False)
    # cover
    cover_title: StringProperty(name='Cover title', default='')
    cover_frame: IntProperty(name='Cover frame', default=-1)
    cover_candidates: StringProperty(default='')
    # carousel
    carousel_count: IntProperty(name='Slides', default=5, min=4, max=10)
    carousel_pos: EnumProperty(name='Text', items=[('BOTTOM', 'Bottom', ''), ('TOP', 'Top', '')])
    carousel_swipe: BoolProperty(name='Swipe arrow on slide 1', default=True)
    # reframe
    size_feed: BoolProperty(name='Feed 4:5', default=True)
    size_square: BoolProperty(name='Square 1:1', default=False)
    size_wide: BoolProperty(name='YouTube 16:9', default=True)
    size_reel: BoolProperty(name='Reels 9:16', default=True)
    # bts
    bts_speed: IntProperty(name='Speed-up', default=1, min=1, max=8, description='Use every Nth frame')
    bts_card: StringProperty(name='Card', default='See the full video on my profile')
    bts_use_interface: BoolProperty(name='Capture the real Blender interface', default=True)
    # cameo
    cameo_char: EnumProperty(name='Character', items=[('frog', 'Froggy', ''), ('koala', 'Koala', ''),
                                                      ('bunny', 'Bunny', '')])
    cameo_reaction: EnumProperty(name='Reaction', items=[(k, v[0], '') for k, v in formats.CAMEO_REACTIONS.items()])
    cameo_seconds: FloatProperty(name='Cut length (s)', default=1.2, min=0.3, max=6)
    # package
    hashtags: StringProperty(name='Hashtags', default='', description='Up to 5, space or comma separated')
    last_package: StringProperty(default='')
    postiz_when: StringProperty(name='Post at', default='', description='YYYY-MM-DD HH:MM, your local time')


class SS_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__
    renders_dir: StringProperty(name='Renders folder', subtype='DIR_PATH',
                                default=os.path.join(os.path.expanduser('~'), 'Documents', 'DeepInDoodles'))
    cast_dir: StringProperty(name='Cast folder (frog.blend, koala.blend...)', subtype='DIR_PATH', default='')
    postiz_url: StringProperty(name='Postiz address', default='', description='e.g. https://api.postiz.com')
    postiz_key: StringProperty(name='Postiz API key', default='', subtype='PASSWORD')
    postiz_channel: StringProperty(name='Postiz channel id', default='')

    def draw(self, ctx):
        l = self.layout
        l.prop(self, 'renders_dir')
        l.prop(self, 'cast_dir')
        b = l.box()
        b.label(text='Optional: schedule posts with Postiz (asks you before anything goes live)')
        b.prop(self, 'postiz_url')
        b.prop(self, 'postiz_key')
        b.prop(self, 'postiz_channel')


# ------------------------------------------------------------------ operators
def _run(op, fn, ok):
    try:
        r = fn()
    except Exception as e:  # tell the user plainly; never leave a half-made thing silently
        op.report({'ERROR'}, str(e))
        return {'CANCELLED'}
    op.report({'INFO'}, ok(r) if callable(ok) else ok)
    return {'FINISHED'}


class SS_OT_format(bpy.types.Operator):
    bl_idname = 'social.build_format'
    bl_label = 'Build Reel'
    bl_description = 'Set up the whole reel: slots, shots, cuts and headline slots'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: formats.build_format(st.reel_format, st.use_script),
                    lambda r: '%s: %d slots, %.0f s' % r)


class SS_OT_script(bpy.types.Operator):
    bl_idname = 'social.script_text'
    bl_label = 'Write script'
    bl_description = 'Open a "Reel Script" text: one line per slot'

    name: StringProperty(default='Reel Script')

    def execute(self, ctx):
        t = bpy.data.texts.get(self.name) or bpy.data.texts.new(self.name)
        if not t.as_string().strip():
            st = core.settings(ctx.scene)
            if self.name == 'Reel Script':
                slots = formats.FORMATS.get(st.reel_format, formats.FORMATS['STORYTIME'])[1]
                t.write('\n'.join('%s line' % s[0] for s in slots))
            elif self.name == 'Carousel':
                t.write('\n'.join('Slide %d line' % (i + 1) for i in range(st.carousel_count)))
        for a in ctx.screen.areas:
            if a.type == 'TEXT_EDITOR':
                a.spaces.active.text = t
                break
        else:
            self.report({'INFO'}, 'Text "%s" ready: open it in a Text Editor' % self.name)
        return {'FINISHED'}


class SS_OT_react(bpy.types.Operator):
    bl_idname = 'social.reaction'
    bl_label = 'Add Reaction Layout'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        p = bpy.path.abspath(st.react_path)
        if not os.path.exists(p):
            self.report({'ERROR'}, 'Pick a clip or screenshot first')
            return {'CANCELLED'}
        return _run(self, lambda: formats.add_reaction(p, st.react_layout, st.react_side, st.react_border),
                    'Reaction layout added')


class SS_OT_react_cue(bpy.types.Operator):
    bl_idname = 'social.reaction_cue'
    bl_label = 'React here'
    bl_description = 'The character reacts at the playhead (surprise face + lines)'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        f = ctx.scene.frame_current

        def go():
            fid = core.lib_find('expression', ('surpris', 'shock', 'gasp', 'wow'))
            if fid:
                core.doodle_library().insert(fid, frame=f)
            text_tools.add_sticker('BURST', frame=f)
            return fid
        return _run(self, go, lambda fid: 'Reaction at frame %d%s' % (f, '' if fid else ' (lines only: Doodle Library not found)'))


class SS_OT_comment(bpy.types.Operator):
    bl_idname = 'social.comment'
    bl_label = 'Add Comment Bubble'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        if not st.comment_text.strip():
            self.report({'ERROR'}, 'Type or paste the comment first')
            return {'CANCELLED'}
        return _run(self, lambda: text_tools.add_comment(st.comment_user, st.comment_text, None, st.comment_where,
                                                         st.comment_seconds, st.comment_show_user, st.comment_style),
                    'Comment bubble added at the playhead')


class SS_OT_paste_comment(bpy.types.Operator):
    bl_idname = 'social.paste_comment'
    bl_label = 'Paste'
    bl_description = 'Paste a copied comment. "@name: text" fills both fields'

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        s = ctx.window_manager.clipboard.strip()
        if s.startswith('@') and ':' in s:
            u, t = s.split(':', 1)
            st.comment_user, st.comment_text = u.strip(), t.strip()
        else:
            st.comment_text = s
        return {'FINISHED'}


class SS_OT_captions(bpy.types.Operator):
    bl_idname = 'social.captions'
    bl_label = 'Place Captions'
    bl_description = 'Captions under the face, inside the safe zone, key words in the headline font'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        p = bpy.path.abspath(st.caption_file)
        if p and os.path.exists(p):
            src = open(p, encoding='utf-8-sig').read()
            srt = p.lower().endswith('.srt') or '-->' in src
        elif bpy.data.texts.get('Captions'):
            src = bpy.data.texts['Captions'].as_string()
            srt = '-->' in src
        else:
            self.report({'ERROR'}, 'Pick an .srt or transcript file (or a text block called "Captions")')
            return {'CANCELLED'}

        def go():
            made = text_tools.place_captions(src, srt)
            warn = sum(1 for r in made if r.get('ss_warn'))
            return len(made), warn
        return _run(self, go, lambda r: '%d captions placed%s' % (r[0], ', %d had no room under the face' % r[1] if r[1] else ''))


class SS_OT_clear_captions(bpy.types.Operator):
    bl_idname = 'social.clear_captions'
    bl_label = 'Remove captions'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        text_tools.clear_captions()
        return {'FINISHED'}


class SS_OT_sticker(bpy.types.Operator):
    bl_idname = 'social.sticker'
    bl_label = 'Add Sticker'
    bl_description = 'Draws itself on at the playhead'
    bl_options = {'REGISTER', 'UNDO'}
    kind: StringProperty(default='')

    def execute(self, ctx):
        k = self.kind or core.settings(ctx.scene).sticker_kind
        return _run(self, lambda: text_tools.add_sticker(k), 'Sticker added at the playhead')


class SS_OT_beats(bpy.types.Operator):
    bl_idname = 'social.find_beats'
    bl_label = 'Find Beats'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        p = bpy.path.abspath(st.beat_file) if st.beat_file else None
        return _run(self, lambda: timing.mark_beats(p, st.beat_every, st.beat_offset, st.beat_sensitivity, st.beat_steady),
                    lambda r: '%d beats marked (%.0f BPM)' % r)


class SS_OT_snap(bpy.types.Operator):
    bl_idname = 'social.snap_beats'
    bl_label = 'Snap to Beats'
    bl_description = 'Cuts, sticker hits and caption pops move to the nearest beat'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: timing.snap_to_beats(True, True, st.snap_captions, st.snap_max),
                    lambda n: '%d things snapped to the beat' % n)


class SS_OT_clear_beats(bpy.types.Operator):
    bl_idname = 'social.clear_beats'
    bl_label = 'Remove beat markers'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        timing.clear_beats(ctx.scene)
        return {'FINISHED'}


class SS_OT_pacing(bpy.types.Operator):
    bl_idname = 'social.pacing'
    bl_label = 'Check Pacing'
    bl_description = 'Marks stretches where nothing changes. It only flags; it never blocks a render'

    def execute(self, ctx):
        return _run(self, lambda: timing.check_pacing(ctx.scene),
                    lambda i: 'Pacing looks good' if not i else '%d things to look at' % len(i))


class SS_OT_jump(bpy.types.Operator):
    bl_idname = 'social.jump'
    bl_label = 'Go'
    frame: IntProperty()

    def execute(self, ctx):
        ctx.scene.frame_set(self.frame)
        return {'FINISHED'}


class SS_OT_loop(bpy.types.Operator):
    bl_idname = 'social.loop'
    bl_label = 'Make Loop'
    bl_description = 'The last second blends back into the first frame'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: timing.make_loop(st.loop_blend, st.loop_camera),
                    lambda n: 'Loop made (%d animated channels)' % n)


class SS_OT_sfx(bpy.types.Operator):
    bl_idname = 'social.auto_sfx'
    bl_label = 'Auto SFX'
    bl_description = 'Suggests a sound on each cut and sticker hit (strips named "SFX?")'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: timing.auto_sfx(st.sfx_volume, st.sfx_limit, st.sfx_cut, st.sfx_sticker),
                    lambda n: '%d sounds suggested. Delete any you don\'t want, then Keep all' % n)


class SS_OT_sfx_keep(bpy.types.Operator):
    bl_idname = 'social.sfx_keep'
    bl_label = 'Keep all'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        return _run(self, timing.keep_sfx, lambda n: '%d sounds kept' % n)


class SS_OT_sfx_clear(bpy.types.Operator):
    bl_idname = 'social.sfx_clear'
    bl_label = 'Remove suggestions'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        return _run(self, lambda: timing.clear_sfx(True), lambda n: '%d suggestions removed' % n)


class SS_OT_sfx_one(bpy.types.Operator):
    bl_idname = 'social.sfx_one'
    bl_label = 'Add sound'
    bl_description = 'Add this sound at the playhead'
    bl_options = {'REGISTER', 'UNDO'}
    kind: StringProperty()

    def execute(self, ctx):
        sc = ctx.scene
        core.strips(sc).new_sound('SFX ' + self.kind, timing.sfx_path(self.kind), timing.CHANNEL, sc.frame_current)
        return {'FINISHED'}


class SS_OT_series_save(bpy.types.Operator):
    bl_idname = 'social.series_save'
    bl_label = 'Save Series'
    bl_description = 'Remember this series: name, cards, numbering and this scene\'s look'

    def execute(self, ctx):
        return _run(self, formats.save_current_series, 'Series saved')


class SS_OT_series_pick(bpy.types.Operator):
    bl_idname = 'social.series_pick'
    bl_label = 'Pick series'
    bl_property = 'which'

    def items(self, ctx):
        return [(k, k, '') for k in sorted(formats.load_series())] or [('', 'No series yet', '')]
    which: EnumProperty(items=items)

    def invoke(self, ctx, ev):
        ctx.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, ctx):
        s = formats.load_series().get(self.which)
        if not s:
            return {'CANCELLED'}
        st = core.settings(ctx.scene)
        st.series_name = self.which
        st.series_intro = s.get('intro', '{series}')
        st.series_intro_seconds = s.get('intro_seconds', 1.2)
        st.series_end = s.get('end', 'Part {next} next')
        st.numbering = s.get('numbering', 'EP')
        st.episode = s.get('episode', 0)
        return {'FINISHED'}


class SS_OT_episode(bpy.types.Operator):
    bl_idname = 'social.new_episode'
    bl_label = 'New Episode'
    bl_description = 'Title card, intro sting, next-part end card and the series look, numbered for you'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        if not core.settings(ctx.scene).series_name.strip():
            self.report({'ERROR'}, 'Name the series first')
            return {'CANCELLED'}
        return _run(self, formats.new_episode, lambda r: '%s set up' % r[0])


class SS_OT_endcard(bpy.types.Operator):
    bl_idname = 'social.end_card'
    bl_label = 'Add End Card'
    bl_description = 'A short mustard card with one clear ask, after the last shot'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: text_tools.add_end_card(st.card_kind, st.card_word, st.card_seconds, st.card_behind,
                                                          st.card_custom), 'End card added')


class SS_OT_cover_pick(bpy.types.Operator):
    bl_idname = 'social.pick_cover'
    bl_label = 'Pick Cover'
    bl_description = 'Suggests three frames where the face is clear and the expression is big'

    def execute(self, ctx):
        return _run(self, output.suggest_covers, lambda f: 'Pick one of frames %s' % ', '.join(map(str, f)))


class SS_OT_cover_use(bpy.types.Operator):
    bl_idname = 'social.use_cover'
    bl_label = 'Use'
    frame: IntProperty()

    def execute(self, ctx):
        core.settings(ctx.scene).cover_frame = self.frame
        ctx.scene.frame_set(self.frame)
        return {'FINISHED'}


class SS_OT_cover_make(bpy.types.Operator):
    bl_idname = 'social.make_cover'
    bl_label = 'Make Cover + Grid Preview'
    bl_description = 'Renders cover.png (1080x1920) and shows it in your profile grid crop'

    def execute(self, ctx):
        def go():
            p, g = output.make_cover()
            im = bpy.data.images.get('SS Grid preview')
            for a in ctx.screen.areas:
                if a.type == 'IMAGE_EDITOR' and im:
                    a.spaces.active.image = im
            return p, g
        return _run(self, go, lambda r: 'Cover saved. Grid preview: %s' % r[1])


class SS_OT_carousel(bpy.types.Operator):
    bl_idname = 'social.carousel'
    bl_label = 'Make Carousel'
    bl_description = 'Matching 1080x1350 stills, one pose and one line per slide'

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: output.make_carousel(st.carousel_count, st.carousel_pos, st.carousel_swipe),
                    lambda r: '%d slides saved in the carousel folder' % len(r))


class SS_OT_reframe_cams(bpy.types.Operator):
    bl_idname = 'social.reframe_cams'
    bl_label = 'Make size cameras'
    bl_description = 'One camera per size, so you can adjust each by hand'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        return _run(self, lambda: output.make_reframe_cameras(_sizes(ctx)), lambda m: '%d cameras ready' % len(m))


def _sizes(ctx):
    st = core.settings(ctx.scene)
    return [k for k, on in (('REEL', st.size_reel), ('FEED', st.size_feed), ('SQUARE', st.size_square),
                            ('WIDE', st.size_wide)) if on]


class SS_OT_reframe(bpy.types.Operator):
    bl_idname = 'social.render_sizes'
    bl_label = 'Render All Sizes'
    bl_description = 'One render per ticked size, character centred, captions inside each safe area'

    def execute(self, ctx):
        return _run(self, lambda: output.render_sizes(_sizes(ctx)), lambda r: '%d videos rendered' % len(r))


class SS_OT_bts(bpy.types.Operator):
    bl_idname = 'social.bts'
    bl_label = 'Record BTS'
    bl_description = 'Vertical BTS: the Blender view from the front on top, the camera view below, then a mustard card'

    def execute(self, ctx):
        return _run(self, output.make_bts, lambda p: 'BTS saved: %s' % p)


class SS_OT_cameo(bpy.types.Operator):
    bl_idname = 'social.cameo'
    bl_label = 'Add Cameo'
    bl_description = 'A quick reaction cut to Froggy, Koala or Bunny, then back to the main shot'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        st = core.settings(ctx.scene)
        return _run(self, lambda: formats.add_cameo(st.cameo_char, st.cameo_reaction, st.cameo_seconds),
                    lambda r: '%s cameo added%s' % (r[0], '' if r[1] else ' (simple head move: Doodle Library not found)'))


class SS_OT_package(bpy.types.Operator):
    bl_idname = 'social.package'
    bl_label = 'Package Post'
    bl_description = 'Video, cover, caption (up to 5 hashtags) and BTS in one Ready to post folder'

    def execute(self, ctx):
        def go():
            return output.package_post()
        return _run(self, go, lambda r: 'Ready: %s%s' % (r[0], ('  Missing: ' + ', '.join(r[2])) if r[2] else ''))


class SS_OT_open_folder(bpy.types.Operator):
    bl_idname = 'social.open_folder'
    bl_label = 'Open folder'
    path: StringProperty()

    def execute(self, ctx):
        p = self.path or core.project_dir(ctx.scene)
        bpy.ops.wm.path_open(filepath=p)
        return {'FINISHED'}


class SS_OT_postiz(bpy.types.Operator):
    bl_idname = 'social.postiz'
    bl_label = 'Schedule with Postiz'
    bl_description = 'Shows what will be posted and when, and only sends it after you press OK'

    def invoke(self, ctx, ev):
        p = core.prefs()
        st = core.settings(ctx.scene)
        if not (p and p.postiz_url and p.postiz_key and p.postiz_channel):
            self.report({'ERROR'}, 'Add your Postiz address, key and channel in the add-on preferences')
            return {'CANCELLED'}
        if not st.last_package or not os.path.isdir(st.last_package):
            self.report({'ERROR'}, 'Package the post first')
            return {'CANCELLED'}
        if not st.postiz_when.strip():
            self.report({'ERROR'}, 'Set "Post at" first (YYYY-MM-DD HH:MM)')
            return {'CANCELLED'}
        return ctx.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.label(text='This schedules a real post. Check it:')
        l.label(text='Folder: ' + os.path.basename(st.last_package))
        l.label(text='When: ' + st.postiz_when + ' (your time)')
        cap = output.caption_text(ctx.scene).split('\n')[0][:60]
        l.label(text='Caption starts: ' + cap)

    def execute(self, ctx):
        import datetime
        st = core.settings(ctx.scene)
        try:
            local = datetime.datetime.strptime(st.postiz_when.strip(), '%Y-%m-%d %H:%M').astimezone()
            when = local.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            r = output.postiz_schedule(st.last_package, when, core.prefs().postiz_channel)
        except Exception as e:
            self.report({'ERROR'}, 'Postiz: %s' % e)
            return {'CANCELLED'}
        self.report({'INFO'}, 'Scheduled with Postiz')
        return {'FINISHED'}


class SS_OT_layout(bpy.types.Operator):
    bl_idname = 'social.relayout'
    bl_label = 'Re-place overlays'
    bl_description = 'Pin every caption, sticker and card to the active camera again'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        core.layout()
        return {'FINISHED'}


# ------------------------------------------------------------------ UI
class _P:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Social'


def advanced(layout, idname):
    """A closed-by-default Advanced section."""
    try:
        head, body = layout.panel(idname, default_closed=True)
        head.label(text='Advanced')
        return body
    except AttributeError:
        return layout.box()


class SS_PT_main(_P, bpy.types.Panel):
    bl_label = 'Social Studio'

    def draw(self, ctx):
        sc = ctx.scene
        l = self.layout
        lead = core.lead_character(sc)
        l.label(text='Lead: %s' % (lead.name if lead else 'no character found'), icon='ARMATURE_DATA')
        r = l.row(align=True)
        r.operator('social.relayout', icon='FILE_REFRESH')
        r.operator('social.open_folder', text='', icon='FILE_FOLDER')
        b = advanced(l, 'ss_adv_main')
        if b:
            st = core.settings(sc)
            b.prop(st, 'stroke_px')
            b.prop(st, 'overlay_depth')


class SS_PT_formats(_P, bpy.types.Panel):
    bl_label = 'Reel Formats'
    bl_parent_id = 'SS_PT_main'

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.prop(st, 'reel_format', text='')
        r = l.row(align=True)
        r.operator('social.build_format', icon='SEQ_STRIP_DUPLICATE')
        r.operator('social.script_text', text='', icon='TEXT').name = 'Reel Script'
        b = advanced(l, 'ss_adv_formats')
        if b:
            b.prop(st, 'use_script')
            b.label(text='Edit a slot\'s shot by moving the camera at its marker')


class SS_PT_react(_P, bpy.types.Panel):
    bl_label = 'Reaction and Duet'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.prop(st, 'react_path', text='')
        l.prop(st, 'react_layout', text='')
        r = l.row(align=True)
        r.operator('social.reaction', icon='IMAGE_PLANE')
        r.operator('social.reaction_cue', text='', icon='LIGHT_SUN')
        b = advanced(l, 'ss_adv_react')
        if b:
            b.prop(st, 'react_side')
            b.prop(st, 'react_border')


class SS_PT_comment(_P, bpy.types.Panel):
    bl_label = 'Reply to a Comment'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.prop(st, 'comment_user', text='', icon='USER')
        r.operator('social.paste_comment', text='', icon='PASTEDOWN')
        l.prop(st, 'comment_text', text='')
        l.operator('social.comment', icon='OUTLINER_OB_FONT')
        b = advanced(l, 'ss_adv_comment')
        if b:
            b.prop(st, 'comment_where')
            b.prop(st, 'comment_style')
            b.prop(st, 'comment_show_user')
            b.prop(st, 'comment_seconds')


class SS_PT_captions(_P, bpy.types.Panel):
    bl_label = 'Caption Studio'
    bl_parent_id = 'SS_PT_main'

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.prop(st, 'caption_file', text='')
        r = l.row(align=True)
        r.operator('social.captions', icon='SYNTAX_OFF')
        r.operator('social.clear_captions', text='', icon='X')
        n = len(core.items('caption'))
        if n:
            warn = sum(1 for c in core.items('caption') if c.get('ss_warn'))
            l.label(text='%d captions%s' % (n, ', %d need a look' % warn if warn else ''),
                    icon='ERROR' if warn else 'CHECKMARK')
        b = advanced(l, 'ss_adv_captions')
        if b:
            b.prop(st, 'caption_size')
            b.prop(st, 'caption_nudge')
            b.prop(st, 'caption_max_words')
            b.prop(st, 'auto_key_words')
            b.prop(st, 'key_words')
            b.label(text='Mark key words in the SRT with *stars* or CAPS')


class SS_PT_stickers(_P, bpy.types.Panel):
    bl_label = 'Doodle Stickers'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        g = l.grid_flow(columns=3, align=True)
        for k, label, _ in text_tools.STICKER_ITEMS:
            g.operator('social.sticker', text=label).kind = k
        b = advanced(l, 'ss_adv_stickers')
        if b:
            b.prop(st, 'sticker_size')
            b.prop(st, 'sticker_seconds')
            b.prop(st, 'draw_seconds')
            b.prop(st, 'line_boil')


class SS_PT_beats(_P, bpy.types.Panel):
    bl_label = 'Beat Sync'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.operator('social.find_beats', icon='SOUND')
        r.operator('social.snap_beats', icon='SNAP_ON')
        if st.bpm:
            l.label(text='%d beats · %.0f BPM' % (len(timing.beat_frames()), st.bpm))
        b = advanced(l, 'ss_adv_beats')
        if b:
            b.prop(st, 'beat_file')
            b.prop(st, 'beat_every')
            b.prop(st, 'beat_offset')
            b.prop(st, 'beat_steady')
            if not st.beat_steady:
                b.prop(st, 'beat_sensitivity')
            b.prop(st, 'snap_captions')
            b.prop(st, 'snap_max')
            b.operator('social.clear_beats', icon='X')


class SS_PT_pacing(_P, bpy.types.Panel):
    bl_label = 'Pacing Check'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.operator('social.pacing', icon='TIME')
        for row in [r for r in st.pacing_report.split('\n') if r][:8]:
            kind, f, msg = row.split('|', 2)
            rr = l.row(align=True)
            rr.label(text=msg, icon='ERROR' if kind != 'LONG' else 'INFO')
            rr.operator('social.jump', text='', icon='PLAY').frame = int(f)
        b = advanced(l, 'ss_adv_pacing')
        if b:
            b.prop(st, 'dead_air_seconds')
            b.prop(st, 'target_seconds')
            b.prop(st, 'show_pacing')


class SS_PT_loop(_P, bpy.types.Panel):
    bl_label = 'Loop Ending'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.operator('social.loop', icon='FILE_REFRESH')
        b = advanced(l, 'ss_adv_loop')
        if b:
            b.prop(st, 'loop_blend')
            b.prop(st, 'loop_camera')


class SS_PT_sfx(_P, bpy.types.Panel):
    bl_label = 'Sound Effects on Cuts'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.operator('social.auto_sfx', icon='SPEAKER')
        n = sum(1 for s in core.all_strips() if s.name.startswith('SFX?'))
        if n:
            r = l.row(align=True)
            r.label(text='%d suggestions' % n)
            r.operator('social.sfx_keep', icon='CHECKMARK')
            r.operator('social.sfx_clear', text='', icon='X')
        b = advanced(l, 'ss_adv_sfx')
        if b:
            b.prop(st, 'sfx_volume')
            b.prop(st, 'sfx_limit')
            b.prop(st, 'sfx_cut')
            b.prop(st, 'sfx_sticker')
            g = b.grid_flow(columns=3, align=True)
            for k in timing.SFX_KINDS:
                g.operator('social.sfx_one', text=k.title()).kind = k


class SS_PT_series(_P, bpy.types.Panel):
    bl_label = 'Series Kit'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.prop(st, 'series_name', text='', icon='BOOKMARKS')
        r.operator('social.series_pick', text='', icon='DOWNARROW_HLT')
        l.operator('social.new_episode', icon='ADD')
        if st.episode:
            l.label(text='This file: %s' % core.episode_label(st, st.episode))
        b = advanced(l, 'ss_adv_series')
        if b:
            b.prop(st, 'series_intro')
            b.prop(st, 'series_intro_seconds')
            b.prop(st, 'series_end')
            b.prop(st, 'numbering')
            b.operator('social.series_save', icon='FILE_TICK')


class SS_PT_endcards(_P, bpy.types.Panel):
    bl_label = 'End Cards'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.prop(st, 'card_kind', text='')
        if st.card_kind == 'COMMENT':
            l.prop(st, 'card_word')
        l.operator('social.end_card', icon='IMAGE_RGB')
        b = advanced(l, 'ss_adv_cards')
        if b:
            b.prop(st, 'card_custom')
            b.prop(st, 'card_seconds')
            b.prop(st, 'card_behind')


class SS_PT_cover(_P, bpy.types.Panel):
    bl_label = 'Cover and Grid Preview'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.operator('social.pick_cover', icon='RESTRICT_RENDER_OFF')
        frames = [int(f) for f in st.cover_candidates.split(',') if f]
        if frames:
            r = l.row()
            for i, f in enumerate(frames):
                c = r.column(align=True)
                im = bpy.data.images.get('SS Cover %d' % (i + 1))
                if im and im.preview:
                    c.template_icon(icon_value=im.preview.icon_id, scale=4)
                op = c.operator('social.use_cover', text=('✓ %d' if st.cover_frame == f else '%d') % f, depress=st.cover_frame == f)
                op.frame = f
        l.prop(st, 'cover_title')
        l.operator('social.make_cover', icon='IMAGE_DATA')
        b = advanced(l, 'ss_adv_cover')
        if b:
            b.prop(st, 'cover_frame', text='Use frame')


class SS_PT_carousel(_P, bpy.types.Panel):
    bl_label = 'Carousel Maker'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.operator('social.carousel', icon='RENDERLAYERS')
        r.operator('social.script_text', text='', icon='TEXT').name = 'Carousel'
        b = advanced(l, 'ss_adv_carousel')
        if b:
            b.prop(st, 'carousel_count')
            b.prop(st, 'carousel_pos')
            b.prop(st, 'carousel_swipe')
            b.label(text='Markers named "Slide" pick the frames')


class SS_PT_reframe(_P, bpy.types.Panel):
    bl_label = 'Smart Reframe'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        g = l.grid_flow(columns=2, align=True)
        for p in ('size_reel', 'size_feed', 'size_square', 'size_wide'):
            g.prop(st, p, toggle=True)
        l.operator('social.render_sizes', icon='RENDER_ANIMATION')
        b = advanced(l, 'ss_adv_reframe')
        if b:
            b.operator('social.reframe_cams', icon='CAMERA_DATA')
            b.label(text='Adjust any "· feed / · wide" camera by hand')


class SS_PT_bts(_P, bpy.types.Panel):
    bl_label = 'BTS Maker'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        l.operator('social.bts', icon='REC')
        b = advanced(l, 'ss_adv_bts')
        if b:
            b.prop(st, 'bts_speed')
            b.prop(st, 'bts_card')
            b.prop(st, 'bts_use_interface')


class SS_PT_cameo(_P, bpy.types.Panel):
    bl_label = 'Cast Cameos'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.prop(st, 'cameo_char', text='')
        r.prop(st, 'cameo_reaction', text='')
        l.operator('social.cameo', icon='OUTLINER_OB_ARMATURE')
        b = advanced(l, 'ss_adv_cameo')
        if b:
            b.prop(st, 'cameo_seconds')


class SS_PT_package(_P, bpy.types.Panel):
    bl_label = 'Post Package'
    bl_parent_id = 'SS_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        st = core.settings(ctx.scene)
        l = self.layout
        r = l.row(align=True)
        r.prop(st, 'hashtags', text='', icon='LINKED')
        r.operator('social.script_text', text='', icon='TEXT').name = 'Post Caption'
        r = l.row(align=True)
        r.operator('social.package', icon='PACKAGE')
        if st.last_package:
            r.operator('social.open_folder', text='', icon='FILE_FOLDER').path = st.last_package
        b = advanced(l, 'ss_adv_package')
        if b:
            b.prop(st, 'postiz_when')
            b.operator('social.postiz', icon='TIME')


CLASSES = [SS_Settings, SS_Prefs] + [c for n, c in sorted(globals().items()) if n.startswith('SS_OT_')] + [
    SS_PT_main, SS_PT_formats, SS_PT_captions, SS_PT_stickers, SS_PT_react, SS_PT_comment, SS_PT_beats, SS_PT_pacing,
    SS_PT_loop, SS_PT_sfx, SS_PT_series, SS_PT_endcards, SS_PT_cover, SS_PT_carousel, SS_PT_reframe, SS_PT_bts,
    SS_PT_cameo, SS_PT_package]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.social_studio = bpy.props.PointerProperty(type=SS_Settings)
    if output.follow_camera not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(output.follow_camera)
    if not bpy.app.background:
        timing.register_draw()


def unregister():
    timing.unregister_draw()
    if output.follow_camera in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(output.follow_camera)
    del bpy.types.Scene.social_studio
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
