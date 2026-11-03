# Social Studio (Blender add-on)

Turns a Bunny, Froggy, Koala or any rigged character scene into a ready-to-post reel.
Blender 4.5 to 5.2. Install: Edit › Preferences › Get Extensions › Install from Disk › `social_studio-1.0.0.zip`.
Panel: 3D Viewport sidebar (N) › **Social**. Each tool is one button; finer settings sit in a closed **Advanced** section.

| Tool | Button | What it does |
|---|---|---|
| Reel Formats | Build Reel | Storytime, POV skit, 3 things, myth vs fact, before and after, hot take: slots as markers, camera shots with hard cuts, headline slots. One line per slot in the "Reel Script" text times the slots. |
| Reaction and Duet | Add Reaction Layout | Clip or screenshot as picture in picture, split screen or a board. The camera moves so the clip never covers the eyes or mouth. "React here" adds a surprise face (Doodle Library) and lines. |
| Reply to a comment | Add Comment Bubble | Doodle bubble with "Replying to @name", pinned at the top (shrinks before it would cover the eyes) or beside the character. |
| Caption Studio | Place Captions | From an .srt (or plain transcript). Condensed, 1–3 words on one line, longer ones on two lines, below the face in the safe zone, never at the very bottom. Key words (*starred*, CAPS, your list, or the strongest word) in the headline font. |
| Doodle stickers | 12 buttons | Arrows, circle, underline, sparkle, surprise lines, ? and !, and sound words. Same line weight everywhere, draw-on and gentle line boil. |
| Beat Sync | Find Beats / Snap to Beats | Beat markers from the sequencer music; cuts, sticker hits and caption pops snap to the nearest beat (max shift in Advanced). |
| Pacing check | Check Pacing | Red strip on the timeline where nothing changes for 2.5 s, plus slow-hook and too-long flags. Flags only, never blocks. |
| Loop ending | Make Loop | Last second blends back to the first frame (camera too, optional). |
| Sound effects | Auto SFX | Original pop / whoosh / boing / scratch / ding / tick, suggested on cuts and stickers as "SFX?" strips. Keep all or remove. |
| Series Kit | New Episode | Series name, title card, intro sting, "Part N next" end card, numbering and look, saved once and reused. |
| End cards | Add End Card | Mustard card, black sentence-case text: follow for part 2, comment a word, full video on my profile, save this. |
| Cover and grid | Pick Cover / Make Cover | Three suggested frames (face clear, big, mid-expression), cover title, cover.png and a profile-grid (3:4 crop) preview next to your last posts. |
| Carousel | Make Carousel | 4–10 slides at 1080×1350, one line each from the "Carousel" text, swipe arrow on slide 1. |
| Smart reframe | Render All Sizes | 9:16, 4:5, 1:1, 16:9 from one scene: a camera per size (adjustable), captions re-placed inside each safe area. |
| BTS Maker | Record BTS | Vertical: Blender's view from the front on top, the camera view below, then the mustard "See the full video on my profile" card. |
| Cast cameos | Add Cameo | Quick reaction cut to Froggy / Koala / Bunny (side-eye, gasp, slow clap, laugh) and back. Uses the Doodle Library when installed. Cast .blend files: Preferences › Cast folder. |
| Post package | Package Post | Video, cover, caption.txt (up to 5 hashtags), BTS, other sizes and carousel in `DeepInDoodles\Ready to post\<date> <name>`. Optional Postiz scheduling always shows a confirm dialog first. |

Renders land in `Documents\DeepInDoodles\<name>\` (final files at the top, working files in `work\`).
Fonts: Bangers, Patrick Hand, Anton (SIL Open Font License). Sounds are synthesized by the add-on.
