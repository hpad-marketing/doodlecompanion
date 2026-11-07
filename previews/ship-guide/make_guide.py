"""Build the Ship Builder visual guide (annotated screenshots + index.html).

python3 make_guide.py <shots dir> <out dir>
Coordinates are in full-size screenshot pixels (studio window 1920x1080).
"""
import html
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SHOTS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
INK = (31, 31, 29)
MUST = (224, 166, 75)
CREAM = (243, 208, 142)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ------------------------------------------------------------------ regions (studio window)
PANEL = (722, 0, 1100, 560)
LIB_BAR = (728, 26, 1090, 44)
TABS = (728, 113, 1090, 172)
ACTION = (728, 178, 1090, 199)        # big Build / Add / Apply button (tabs without the droid box)
ACTION_DROID = (728, 199, 1090, 214)  # Poses / Motions tabs (Droid row above it)
CAMROW = (728, 202, 1090, 221)
VIEW = (1112, 18, 1920, 842)
PREVIEW = (0, 18, 722, 842)
TIMELINE = (0, 842, 1920, 1080)


def tab(col, row):
    x0 = 728 + col * 90.5
    y0 = 113 + row * 19.7
    return (x0, y0, x0 + 90.5, y0 + 19.7)


T = {"Sets": tab(0, 0), "Rooms": tab(1, 0), "Droids": tab(2, 0), "Motions": tab(3, 0),
     "Props": tab(0, 1), "Cameras": tab(1, 1), "Moods": tab(2, 1), "Window views": tab(3, 1),
     "Hero ship": tab(0, 2), "Poses": tab(1, 2), "Camera moves": tab(2, 2), "In this scene": tab(3, 2)}


def union(*bs):
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def annotate(src, name, crop, marks, width=1500):
    fp = os.path.join(SHOTS, src)
    if not os.path.exists(fp):
        fp = fp[:-4] + ".jpg"
    im = Image.open(fp).convert("RGB")
    full = im.copy()
    d = ImageDraw.Draw(im, "RGBA")
    f = ImageFont.truetype(FONT, 22)
    for i, mk in enumerate(marks):
        box, lab = mk[0], mk[1]
        x0, y0, x1, y1 = box
        d.rounded_rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), radius=6, outline=MUST + (255,), width=4)
        r = 15
        cx, cy = max(x0 - 3, r + 2), max(y0 - 3, r + 2)
        if len(mk) > 2 and mk[2] == "r":
            cx = x1 + 3
        if crop:
            cx, cy = max(cx, crop[0] + r + 2), max(cy, crop[1] + r + 2)
            cx = min(cx, crop[2] - r - 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MUST + (255,), outline=INK + (255,), width=3)
        tw = d.textlength(lab, font=f)
        d.text((cx - tw / 2, cy - 13), lab, font=f, fill=INK + (255,))
    if crop:
        im = im.crop(crop)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, "img", name + ".jpg"), quality=88)
    fl = full
    if fl.width > 1920:
        fl = fl.resize((1920, round(fl.height * 1920 / fl.width)))
    return name


# ------------------------------------------------------------------ content
S = []   # sections: (id, title, intro, [steps]) ; step = (img or None, caption html, [(n, text)])


def sec(sid, title, intro, steps):
    S.append((sid, title, intro, steps))


sec("open", "1. Open Ship Studio",
    "Ship Builder is installed in Blender 4.5, 5.0 and 5.2 on Sushi. Use any of them. Your scenes are normal .blend files.",
    [(annotate("01_window_menu.png", "s01_menu", None,
               [((114, 2, 172, 18), "1"), ((1360, 832, 1520, 850), "2", "r")], 1500),
      "Open Blender, then use the Window menu at the top.",
      [("1", "Click <b>Window</b> in the top bar."),
       ("2", "Click <b>Ship Studio</b>, the last item. A new window opens with everything in it. You can also press <b>F3</b> and type <i>Ship Studio</i>.")])])

sec("tour", "2. Find your way around",
    "Ship Studio has four parts. The panel in the middle holds the library: twelve tabs, and every item has a picture.",
    [(annotate("02_sets_tab.png", "s02_tour", None,
               [(PREVIEW, "A"), (PANEL, "B"), (VIEW, "C"), (TIMELINE, "D")]),
      "The Ship Studio window.",
      [("A", "<b>Preview.</b> Click any picture in the library and it shows here, big. Nothing loads into your scene yet."),
       ("B", "<b>Library panel.</b> <i>Library</i> and <i>Episodes</i> at the top, then the twelve tabs, then one big button that adds the picked item."),
       ("C", "<b>Live view.</b> Your actual scene, through the active camera. Drag handles on droids appear here."),
       ("D", "<b>Timeline.</b> Play, scrub and set the start and end frames.")]),
     (annotate("02_sets_tab.png", "s02_tabs", PANEL, [(LIB_BAR, "1"), (TABS, "2")], 760),
      "The tabs, close up.",
      [("1", "<b>Library</b> builds scenes. <b>Episodes</b> runs the seven-station episode workflow, from script to upload (covered at the end)."),
       ("2", "Sets, Rooms, Droids, Motions, Props, Cameras, Moods, Window views, Hero ship, Poses, Camera moves, In this scene.")])])

sec("set", "3. Pick a set or a room",
    "A <b>set</b> is several rooms docked door to door, like a whole deck. A <b>room</b> is one room on its own. Either one is built in a new scene, so you never overwrite what you had.",
    [(annotate("03_rooms_tab.png", "s03_rooms", (0, 0, 1100, 842),
               [(T["Rooms"], "1"), ((728, 240, 845, 348), "2"), (ACTION, "3")]),
      "Rooms tab, with the Oil lounge picked.",
      [("1", "Open <b>Sets</b> or <b>Rooms</b>."),
       ("2", "Click a picture. It shows big on the left so you can check it."),
       ("3", "Press the big button: <b>Build room</b> (or <b>Build set</b>). It takes a few seconds.")]),
     (annotate("04_room_built.png", "s04_built", None, [(VIEW, "4")]),
      "The room is built.",
      [("4", "The live view now looks through the room's camera. <b>Set view: see into rooms</b> (the blue bar under the stations) hides walls in your way while you work. Renders always keep every wall.")])])

sec("droids", "4. Add droids",
    "Each droid comes in at set scale, standing on the floor, with its controls showing.",
    [(annotate("05_droids_tab.png", "s05_droids", PANEL,
               [(T["Droids"], "1"), ((728, 460, 905, 500), "2"), ((728, 222, 1090, 243), "3")], 760),
      "Droids tab.",
      [("1", "Open <b>Droids</b>."),
       ("2", "Click a droid: RX-07, Beacon, Hover drone or Tracked porter."),
       ("3", "Press <b>Add droid</b>. Repeat for every droid in the scene.")]),
     (annotate("06_droid_added.png", "s06_added", None, [(VIEW, "4"), ((728, 178, 1090, 480), "5")]),
      "RX-07 standing in the lounge.",
      [("4", "The droid stands in the room, its control rings showing."),
       ("5", "A <b>Droid controls</b> box appears in the Droids tab, one block per droid.")])])

sec("pose", "5. Pose droids with the drag handles",
    "The easiest way to pose: grab a ring on the droid and drag it.",
    [(annotate("07_handles.png", "s07_handles", VIEW, [], 1200),
      "Handles float on each droid's hands, feet, body and head.",
      [("•", "<b>Blue</b> rings are the droid's left side, <b>red</b> its right, <b>yellow</b> the middle. Each ring has a name tag."),
       ("•", "Drag a ring and that part follows the mouse. The dial under the droid turns the whole droid, and the dial at its head turns the head."),
       ("•", "Turn on auto-key (the record dot in the timeline) and each drag is keyed at the current frame. Move to another frame and drag again to animate.")]),
     (annotate("08_pose_mode.png", "s08_controls", (700, 150, 1100, 490),
               [((850, 178, 966, 194), "1"), ((732, 201, 900, 216), "2"), ((736, 221, 1088, 310), "3", "r"), ((736, 316, 1088, 470), "4"), ((970, 178, 1088, 194), "5")], 760),
      "The Droid controls box.",
      [("1", "<b>Handles on droids</b> turns the rings on or off."),
       ("2", "<b>Pose RX-07</b> lights up the droid's controls. <b>Move whole</b> moves it around the room."),
       ("3", "One-click parts (Whole droid, Body, Head, Left hand…) and show/hide buttons for each control group."),
       ("4", "The pose strip: click a picture to snap the droid into that pose."),
       ("5", "<b>Done</b> leaves posing.")])])

sec("presets", "6. Use pose presets and motions",
    "Every pose is collision-safe, so no part goes through another. Pick the droid in the <i>Droid</i> menu so you only see what that droid can do.",
    [(annotate("09_poses_tab.png", "s09_poses", (0, 0, 1100, 842),
               [(T["Poses"], "1"), ((790, 177, 1090, 191), "2", "r"), ((728, 238, 1090, 350), "3"), ((728, 199, 1090, 214), "4")]),
      "Poses tab.",
      [("1", "Open <b>Poses</b>."), ("2", "Pick the droid."), ("3", "Click a pose to preview it."),
       ("4", "Press <b>Pose droid</b>. Then fine-tune it with the handles.")]),
     (annotate("11_motions_tab.png", "s11_motions", (0, 0, 1100, 842),
               [(T["Motions"], "1"), (ACTION_DROID, "2")]),
      "Motions tab: walks, idles and actions made for each droid.",
      [("1", "Open <b>Motions</b> and click a clip. It plays in the preview."),
       ("2", "Press <b>Play on droid</b>. The timeline's start and end frames match the clip.")])])

sec("props", "7. Add props",
    "Nineteen props: couch, coffee table, pilot chair, consoles, lockers, telescope, tools, plants and more. Each one stands on the floor and moves as one piece.",
    [(annotate("12_props_tab.png", "s12_props", (0, 0, 1100, 842),
               [(T["Props"], "1"), ((728, 470, 905, 540), "2"), (ACTION, "3")]),
      "Props tab with the couch picked.",
      [("1", "Open <b>Props</b>."), ("2", "Click a prop."),
       ("3", "Press <b>Add prop</b>. It lands at the 3D cursor, so Shift + right-click in the live view first to place the cursor. Then press G to slide the prop and R to turn it. Keep props clear of the droids: nothing should pass through anything.")]),
     ])

sec("light", "8. Set the lighting and the view outside",
    "",
    [(annotate("14_moods_tab.png", "s14_moods", PANEL, [(T["Moods"], "1"), (ACTION, "2")], 760),
      "Moods tab: Normal, Night, Red alert, Power out, Docking.",
      [("1", "Open <b>Moods</b> and click one."), ("2", "Press <b>Apply mood</b>. The whole room relights.")]),
     (annotate("15_mood_applied.png", "s15_red", VIEW, [], 1200), "Red alert, applied in the live view.", []),
     (annotate("16_window_views.png", "s16_views", (0, 0, 1100, 842), [(T["Window views"], "1"), (ACTION, "2")]),
      "Window views: what the ship's windows look out on.",
      [("1", "Open <b>Window views</b> and pick one, such as Hyperspace."),
       ("2", "Press <b>Show outside</b>. With auto-key on, the switch is keyed on the current frame, so you can cut to hyperspace mid-scene.")])])

sec("camera", "9. Frame it with cameras and camera moves",
    "Every room comes with its own cameras: a wide master, singles and two-shots.",
    [(annotate("17_cameras_tab.png", "s17_cams", (0, 0, 1100, 842),
               [(T["Cameras"], "1"), (ACTION, "2"), (CAMROW, "3", "r")]),
      "Cameras tab.",
      [("1", "Open <b>Cameras</b> and click one."), ("2", "Press <b>Look through</b>. The live view and the render use it."),
       ("3", "The arrow and <b>Camera</b> buttons step through the room's cameras. <b>Walk mode</b> lets you drive a droid around the ship with WASD or the DualSense (Esc to stop).")]),
     (annotate("18_camera_moves.png", "s18_moves", (0, 0, 1100, 842), [(T["Camera moves"], "1"), (ACTION, "2")]),
      "Camera moves: 16 moves, each with a preview clip.",
      [("1", "Open <b>Camera moves</b> and click one, such as Push in."),
       ("2", "Press <b>Key on camera</b>. The move is keyed on the active camera, starting at the current frame.")]),
     (annotate("19_in_this_scene.png", "s19_scene", PANEL, [(T["In this scene"], "1")], 760),
      "In this scene: everything you've added so far.",
      [("1", "Click any scene, droid, prop or camera, then <b>Go to</b> to select it or look through it.")])])

sec("export", "10. Save and export",
    "Save first with <b>File › Save As</b>, in the scene's own folder under DeepInDoodles. Then render.",
    [(None,
      "In the main Blender window, open the <b>Output</b> tab (the printer icon) in the Properties editor.",
      [("1", "<b>Frame Range</b>: Start and End. A motion or camera move sets these for you."),
       ("2", "<b>Output</b>: choose the folder and file name. For a video, set File Format to <b>FFmpeg Video</b> and Container to <b>MPEG-4</b>."),
       ("3", "<b>Render › Render Image</b> (F12) for one still. <b>Render › Render Animation</b> (Ctrl+F12) for the clip. Rendering uses Sushi's RTX 5080.")]),
     ("RENDER", "The finished frame from the scene built in this guide: RX-07 in the Oil lounge under Red alert, rendered with Cycles on Sushi.", []),
     (annotate("20_episodes_board.png", "s20_board", (700, 0, 1100, 420),
               [((906, 27, 1088, 43), "1", "r"), ((728, 46, 1090, 92), "2"), ((728, 128, 1090, 335), "3")], 760),
      "For full episodes, use the Episodes board.",
      [("1", "Click <b>Episodes</b>."),
       ("2", "The seven stations: Write, Voice, Stage, Perform, Check, Render, Publish. They unlock once an episode is open."),
       ("3", "Start an episode from a template card (Ship malfunction, Strange planet, Droid rivalry, Bottle episode or Blank). The Render station then queues every shot on Sushi's GPU and mixes the cut, and Publish makes the thumbnail and the YouTube upload pack.")])])

json.dump([s[0] for s in S], open(os.path.join(OUT, "sections.json"), "w"))

# ------------------------------------------------------------------ html
render_img = None
for c in ("22_render_result.png",):
    p = os.path.join(SHOTS, c)
    if os.path.exists(p):
        im = Image.open(p).convert("RGB")
        im.thumbnail((1500, 1500))
        im.save(os.path.join(OUT, "img", "s22_render.jpg"), quality=90)
        render_img = "s22_render"

nav = "".join(f'<a href="#{sid}">{html.escape(t)}</a>' for sid, t, _i, _s in S)
body = []
for sid, title, intro, steps in S:
    body.append(f'<section id="{sid}"><h2>{html.escape(title)}</h2>')
    if intro:
        body.append(f'<p class="intro">{intro}</p>')
    for img, cap, items in steps:
        if img == "RENDER":
            if not render_img:
                continue
            img = render_img
        if img is None:
            body.append(f'<p class="intro">{cap}</p>')
            if items:
                body.append('<ol class="marks">' + "".join(
                    f'<li><span class="n">{html.escape(n)}</span><span>{t}</span></li>' for n, t in items) + '</ol>')
            continue
        body.append('<figure>')
        body.append(f'<a class="zoom" href="img/{img}.jpg"><img src="img/{img}.jpg" alt="{html.escape(cap)}" loading="lazy"></a>')
        body.append(f'<figcaption>{cap}</figcaption></figure>')
        if items:
            body.append('<ol class="marks">' + "".join(
                f'<li><span class="n">{html.escape(n)}</span><span>{t}</span></li>' for n, t in items) + '</ol>')
    body.append('</section>')

page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ship Builder: build a scene and export it</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1F1F1D;--ink2:#2a2a27;--must:#E0A64B;--cream:#F3D08E;--text:#ece6da;--mute:#a9a296}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ink);color:var(--text);font:16px/1.6 Inter,system-ui,sans-serif}}
header{{padding:48px 24px 24px;max-width:1100px;margin:0 auto}}
h1{{font-size:clamp(28px,4vw,44px);line-height:1.1;margin:0 0 10px;color:var(--cream);font-weight:800}}
header p{{color:var(--mute);margin:0;max-width:720px}}
nav{{position:sticky;top:0;z-index:5;background:rgba(31,31,29,.95);border-bottom:1px solid #3a3934;backdrop-filter:blur(6px)}}
nav .in{{max-width:1100px;margin:0 auto;display:flex;gap:6px;overflow-x:auto;padding:10px 24px}}
nav a{{white-space:nowrap;color:var(--text);text-decoration:none;font-size:13px;padding:6px 10px;border-radius:99px;background:var(--ink2)}}
nav a:hover{{background:var(--must);color:var(--ink)}}
main{{max-width:1100px;margin:0 auto;padding:8px 24px 80px}}
section{{padding-top:40px;scroll-margin-top:56px}}
h2{{font-size:26px;margin:0 0 8px;color:var(--must);font-weight:800}}
.intro{{color:var(--text);max-width:760px;margin:0 0 18px}}
figure{{margin:22px 0 10px}}
figure img{{display:block;max-width:100%;height:auto;border-radius:10px;border:1px solid #3a3934;cursor:zoom-in}}
figcaption{{color:var(--mute);font-size:14px;margin-top:8px}}
ol.marks{{list-style:none;padding:0;margin:8px 0 18px;display:grid;gap:8px;max-width:820px}}
ol.marks li{{display:flex;gap:12px;align-items:flex-start}}
.n{{flex:none;width:28px;height:28px;border-radius:50%;background:var(--must);color:var(--ink);font-weight:800;display:grid;place-items:center;font-size:14px;margin-top:1px}}
b{{color:var(--cream)}}
.lb{{position:fixed;inset:0;background:rgba(10,10,9,.92);display:none;align-items:center;justify-content:center;z-index:20;cursor:zoom-out;padding:16px}}
.lb.on{{display:flex}}.lb img{{max-width:100%;max-height:100%;border-radius:8px}}
footer{{max-width:1100px;margin:0 auto;padding:0 24px 48px;color:var(--mute);font-size:13px}}
</style></head><body>
<header><h1>Ship Builder: build a scene and export it</h1>
<p>Every screenshot here comes from Ship Builder 0.7.0 running in Blender 5.0 on Sushi. Click any picture to see it full size.</p></header>
<nav><div class="in">{nav}</div></nav>
<main>{''.join(body)}</main>
<footer>Ship Builder 0.7.0 · screenshots taken on Sushi, 7 Nov 2026.</footer>
<div class="lb" id="lb"><img alt=""></div>
<script>
const lb=document.getElementById('lb'),li=lb.querySelector('img');
document.querySelectorAll('a.zoom').forEach(a=>a.addEventListener('click',e=>{{e.preventDefault();li.src=a.getAttribute('href');lb.classList.add('on')}}));
lb.addEventListener('click',()=>lb.classList.remove('on'));
document.addEventListener('keydown',e=>{{if(e.key==='Escape')lb.classList.remove('on')}});
</script></body></html>"""
open(os.path.join(OUT, "index.html"), "w").write(page)
print("ok", len(S), "sections")
