# Doodle Studio 3D: the guide

For the person making the videos, and for any AI assistant (Claude, ChatGPT or another) that drives the app through its MCP.

Written against build 20261030-195859: all 162 approved features, plus the fixes from the stress test. The moderator gate and the Blender rule check are retired (your call, 30 Oct), so the rules below are kept by the rig, the presets, preflight and your eye. When the app and this guide disagree, trust the app: `list_controls`, `library_list` and `apply_camera_preset {list:true}` always report what's actually there.

This is a map, not a recipe book. Each feature gets what it does, where it shines, and a few uses beyond the obvious one. The recipes at the end are starting points to remix. They're not templates to repeat.

---

## Contents

0. Read this first: the look and the hard rules
1. Getting started (for you)
2. Connecting an assistant
3. Feature reference
4. Cross-uses: made for one thing, great for another
5. Recipes to remix
6. For assistants: how to think, not what to make
7. Known limits and troubleshooting
8. Appendix: every MCP tool

---

## 0. Read this first

### What Doodle Studio 3D is

Doodle Studio 3D puts Bunny (and the Koala and the Frog) in a real 3D world. It has a real camera, real angles and real sets, and it renders in Blender in the background. It looks and feels like the 2D Doodle Studio: same buttons, same mustard and ink, plus a black-and-mustard dark mode. You never have to open Blender yourself.

| Use the 2D Doodle Studio when… | Use Doodle Studio 3D when… |
|---|---|
| It's a flat doodle storytime with drawn cutaways | You want real camera moves: orbits, whip pans, dolly zoom, low and high angles |
| You want its drawn mouth sets and frame-by-frame acting | Bunny walks through a set, or the camera travels with him |
| Hand-drawn frame-by-frame doodles carry the story | Several characters share the stage |
| | You want physics: cloth, jelly props, liquids, crowds, weather |

The two apps share the asset library, Bunny's look and the idea of an MCP. Each has its own MCP endpoint. **Nothing in 3D ever touches the 2D app's MCP, port or settings.** That's a hard rule, and the updater checks it on every update.

### The house look

- Brand colours only: ink `#1F1F1D`, mustard `#E0A64B`, with ochre `#B87D2E` for small details. Never white.
- One stroke weight. Bunny's line is the reference. Every prop, set piece and doodle at the same depth uses the same weight, and only far layers get thinner. `set_shot_look ink` scales every line in a shot together, so weights stay equal.
- No boxes or frames around things. Speech bubbles, labels and photo cut-ins get an ink outline, never a box.
- No shadows by default. Cel and halftone shadows are an opt-in style.
- Outfits are brand black only. Details are a few ochre strokes at line weight.

### The hard rules (from `docs/ANIMATION-RULES.md`)

Most of these are built into the app as defaults: the render shapes each frame so the rule holds, the way floor collision lifts a foot that would dig in. Nothing is checked frame by frame and nothing is blocked. Every default can be switched off for one shot (see **Built-in rules** below the table) when the idea needs to break it. The right-hand column says what keeps each one.

| # | Rule | Checked by |
|---|---|---|
| 1 | Hands and arms never cut into the head (outline and ears included). An arm crosses the face only when the whole arm is in front. | Built in: the rig solver turns an arm out of the head, and **Arms in front** brings a hand that would hide behind the head (as the camera sees it) forward in front of the face, eased over a few frames. A back view and a hand clearly over the face stay as keyed |
| 1a | No see-through lines: only the front part is drawn where parts overlap. | Built into the look; check stills by eye |
| 2 | Grounding: feet on the floor, nothing floats, no sitting on props unless asked. Bunny always stands on the floor. Floor collision: no leg, hand or hoodie, and none of their ink strokes, goes under the floor, from any camera angle. The floor you see in the scene is the base: the rig's ground, or the set's own floor (a raised park floor, a stage) up to 25 cm higher right under the feet. Nothing else counts as the floor: not a table, not a bench or a stone, and never a set's own outline (the ink around the ground floats several centimetres up in a high shot). A pose that would dig in (a sunk body, a deep kneel, a toe pushed down) lifts the whole character by exactly how deep it went. Standing and jumping poses are never moved. The outline is drawn a little behind each form, pushed away from the camera, and that push stops at the floor, so in a high or overhead shot the floor never cuts off the bottom of the foot strokes. This holds for Bunny, the Koala, the Frog and every co-star, and your keyed values stay as they are. | Floor collision in the live view and at render (`floor.json` logs every lift); the render check fails a frame with `stroke_in_floor` and reports `shell_low`, the outline as it renders, against the floor. `foot_low`, `grounded` and `floor_gap` are measurements for reports, not fails; the blocking fields are listed by the check. A shot can turn it off with `floorCollision: false` |
| 3 | Constant stroke weight per depth layer. | By construction; `set_shot_look ink` keeps weights equal |
| 4 | Smooth camera: eased moves, few cuts, counted across the whole video. Low and high angles only when the set moves with the lens (a real 3D camera does this). Bunny is always framed and never cut off. | Camera presets are eased; preflight warns when hard cuts come faster than one every 2.5 s |
| 5 | Minimal sets, clear of the character, no tangents. Props behind him. At least 35% of a cropped prop is visible. | Built in: the set auto-layout keeps a clear zone round his mark and hides slivers; **Face clear** slides any set piece or placed prop that would block his face or body sideways; **Props on floor** rests every standing prop's stroke a hair above the floor |
| 5a | Cinematic composition: thirds, frame within frame, depth-true scale, one horizon height across shots. | Camera presets (thirds placement), the `group` target for co-stars; preflight blocks a horizon spread over 4% |
| 6 | Real lip sync from the audio. The mouth is closed in silence. | `audio lipsync` keys it; preflight samples the mouth on loud frames |
| 7 | Eyes and mouth keep a constant size. Act with expression, gaze, head and body. | Built in: squash never scales the face; **Same eye size** keeps the Frog's eye bumps one size whatever EAR Scale says |
| 8 | Smooth, beat-matched, flowing motion. Act the meaning of the words, not literal mime. | Your eye; beat markers help |
| 9 | One folder per animation: `DeepInDoodles\<Name>\`. Only the final sits at the top; everything else goes in `work\`. | The app does this automatically |
| 10 | Token report after the user approves the final and says "done". | `production meter`, `production change_log`, plus Claude Code's usage stats |

**Built-in rules.** Render › Output has a row of toggles for the active shot: Arms in front, Face clear, Props on floor and Same eye size. All are on by default. Over MCP: `set_shot_look {"rules": {"armInFront": false}}` lets that shot break the rule on purpose (a hand scratching behind the head, a prop deliberately in front of him). Captions snap into the safe zone below the face and shrink to fit by default; `set_shot_look {"captionSnap": false}` or the Captions dialog keeps their exact height. Render logs say what each default did (`rules: ...` lines in blender.log).

House preferences that apply to every animation:
- Vary the expressions; Bunny isn't always smiling.
- Bunny stays centred and never sits behind props.
- His ears never stick together.
- Captions: short ones (1–3 words) stay on one line. Longer ones get two balanced lines. They sit inside the Instagram safe zone, below the face, never at the very bottom.
- Audio cuts only in real silence, and never change the meaning of what was said.
- Declutter. Not every prop has to be there.

---

## 1. Getting started (for you)

### Install, update, roll back

Doodle Studio 3D updates itself every hour from GitHub and keeps the previous version for rollback. Tools › Check for updates runs a check now. An update that would break either MCP (2D or 3D) rolls itself back.

When a new Blender version is picked, the app renders a test frame first. It only switches if that frame passes. Blender 4.5 and 5.0 both work.

### The screen

- **Viewport:** the live 3D Bunny and set. Click a body part to select it. Turn on IK drag (Animate menu) to drag hands and feet.
- **Shot strip:** the scene's shots in order, with their codes (sh010, sh020…) and status chips (blocking, splined, polish, approved).
- **Timeline / dope sheet:** keys, markers, the audio waveform, and the graph editor when it's on.
- **Side panels:** Pose, Face, Camera, Library (character, stage, outfit, mouth set, motions, props, effects).
- **Favourites bar:** horizontal and editable. Ctrl+K opens the command search for anything else.
- **View menu:** dark mode, fps meter, pop the viewport out to the Samsung screen (the Kamvas stays primary), saved layouts.

### Your first shot in ten minutes

1. File › New from template… › Quick take.
2. Library tab: pick a set (say, the bedroom) and a motion (search "wave"), then press Insert.
3. Camera menu or a preset button: Medium close-up, eye level.
4. Face tab: switch the expression on a beat. Turn on Auto blink and Auto ear twitch.
5. File › Import audio, then Tools › Check before export.
6. File › Render this shot (preview first). Renders land in `DeepInDoodles\<Scene>\work\renders`.

### Hardware

- The Huion Keydial 3D profile is written for "Doodle Studio 3D.exe". Quit the Huion driver once so it can load.
- Help › Keyboard shortcuts shows every key, and you can rebind them there.

---

## 2. Connecting an assistant

### Claude (Claude Code, Claude Desktop, Cowork)

The endpoint is `http://127.0.0.1:54190/mcp`. It uses Streamable HTTP and only accepts calls from this PC. Add it as an MCP server next to the 2D one, which keeps its own port. Keep the Script › Assistant switch on in the app.

### ChatGPT

ChatGPT connectors call remote HTTPS servers, so they can't reach `127.0.0.1` directly. Use one of these:
- A desktop client that supports local MCP servers.
- A tunnel you control that exposes port 54190 over HTTPS with authentication. Never open it to the public internet without a key.

The tools and their descriptions are the same whichever assistant connects. This route hasn't been tested yet; it's on the stress-test list.

### Driving it cheaply

- Read narrowly: `get_state` for the active shot, `list_controls` once per session, `library_list` with a query and a limit.
- Write in batches: one `set_values` with many controls beats many single calls. Motions from `library_use` beat hand-keying every joint.
- Check before you render. Use `workflow rules` at key frames, then preview renders (`preview:true`), and full renders only once the checks pass.
- Read `production change_log` and `production meter` for the token report.
- A call that would pop a confirmation in the app (replacing an unsaved scene, a template over your work) returns "Needs a yes first" instead of waiting on a dialog. Ask the user, then repeat the call with `force: true`. Never send `force` on your own.

---

## 3. Feature reference

Each entry covers: **what it does · how (UI / MCP) · where it fits · also try · watch out.** MCP calls are written as `tool action=… {args}`.

### 3.0 Open in Blender (live)

**The shot in a full Blender window, mirrored both ways.** Press **Open in Blender** above the canvas (or Ctrl+B, or Blender › Open in Blender). Blender opens the active shot with its set, props, outfit and camera. While the button reads **● Blender live**, a change on either side shows up on the other within about a tenth of a second.
- What syncs: Bunny's pose (turn the FK control bones: head, torso, arms, legs, ears, the root for placement and turn, or move the whole rig in Object Mode), the face (expression, gaze, mouth, blink on the face bone), the camera (move or turn it, change its lens), the playhead, props and scenery (move, turn, scale), set pieces (move, turn about Z, scale; anything standing on a piece follows it), and the sun's angle and strength.
- Keys: a change made in Blender keys at the playhead when Keys is on Auto, the same as a change made in the app. Each burst of Blender edits is one undo step, named "Blender: …".
- A new prop, another set, another character or another shot rebuilds the Blender scene. This takes a few seconds, and the header reads "rebuilding the shot".
- Blender works on its own copy, saved in `work\blender-live\<Scene>_<shot>\`. Ctrl+S in Blender saves there and never touches the app's files.
- Stop: click **● Blender live**, or use Blender › Stop the live Blender link. The Blender window stays open. MCP: `blender_live action=open|status|close`.
- Watch out: Blender shows the raw pose, without the render's rule nudges (arm in front, props on the floor, face clear), cloth or ear springs. Renders still apply all of them. Values stay inside Bunny's joint limits, so a bone turned past a limit snaps back to it, and a twist the rig has no control for is dropped. IK targets in Blender are not read: pose with the FK bones. Co-stars come across when the shot is rebuilt but are not posed live.

### 3.1 Characters

**Bunny, the Koala and the Frog.** All three share one rig, so every key, motion, face and camera move carries over. The Koala adds nose controls (`noseWiggle`, `noseSniff`). The Frog's "ears" are rigid eye bumps: ear controls do nothing, and an ear twitch makes the bumps pop.
- How: Library tab › Character; `set_character {character}`.
- Fits: different roles. The Koala works as the calm sceptic or narrator, the Frog as the hyper sidekick, and Bunny as the lead.
- Also try: retell the same scene with a different lead (`anim2 action=retarget`) to test which character sells the joke.
- Watch out: the Frog has no ear acting. Give him brows, eye darts and body instead.

**Co-stars.** Up to five more characters in a shot (six on stage with the lead). The render keeps bodies from touching with an eased push-apart.
- How: Shot › Co-stars…; `cast action=add|place|key|copy|motion|remove|list`.
- Fits: dialogue, reactions, a chorus, a crowd of named characters.
- Also try: `cast action=copy {mirror:true}` makes an instant mirror dance partner. Two Bunnies make an inner-voice or angel-and-devil argument.
- Watch out: camera presets and Look at camera follow the lead. For OTS shots, place the co-star first, then pick `view: ots-l` or `ots-r`.

### 3.2 Posing and acting

**Rig controls.** Whole body, torso, head, ears, arms, legs, face and camera are each a control with joint limits. Values outside the limits are clamped.
- How: Pose panel; `set_values {values, frame, key}`; ids from `list_controls`.
- Watch out: Bunny's shoulders sit under his big head, so a raised arm only clears the head when it also reaches forward. The render solver lowers arms that would clip. Pose arms forward-and-up, not straight up.

**IK drag and IK by numbers.** Move a hand or foot to a point, and the arm or leg keys follow inside the limits.
- How: Animate › IK drag; `anim2 action=ik {limb, target|offset}`, `action=end_point`.
- Also try: point at a prop by giving its position.
- Watch out: IK can key a pose that the rule lights flag. Check `workflow rules` after IK.

**Pin a hand or foot.** It stays fixed in the world while the body moves.
- How: `anim2 action=pin {limb, from, to}`.
- Fits: planted feet on turns, a hand on a table, pushing a door.

**Hand contact.** A paw rests on the hip, belly or chest and follows the body, never going into the head.
- How: `features action=contact {limb, where, from, to}`.
- Also try: a hand on the belly for "I'm full" or a laugh, a hand on the chest for "who, me?".

**Pose mirror and blend.** Mirror swaps left and right. Blend keys an in-between of two poses.
- How: `mirror_pose`, `blend_poses {a, b, t}`.
- Also try: blend at t=110 for a little overshoot pose.

**Pose library (partial poses).** Save and apply just the face, hands, ears, upper body or the whole pose.
- How: `anim2 action=save_pose|apply_pose|poses|delete_pose {name, part}`.
- Also try: a "signature" hands pose for a running gag.

**Pose from a stick figure.** Draw a stick figure and Bunny takes the pose.
- How: Animate › Pose from a stick figure; `features action=stick {strokes, aspect}`.
- Also try: an assistant can "draw" a pose from a description by writing the strokes itself.

**Squash and stretch.** Belly squash with anticipation and overshoot for a land, jump, bounce or recoil. The face never changes size.
- How: `features action=squash {kind, frame, amount}`.

**Balance marker.** Shows the centre of gravity over the feet. **Silhouette check** shows the figure in solid ink so you can read the pose.
- How: `anim2 action=balance`, `anim_tool action=silhouette`.

### 3.3 Face

**Expressions.** 88 faces in the face list, including the story-beat set with per-character versions (panic, duck-face pout, smug, dizzy, love…). There are also 9 gazes, 19 speech mouths, blinks and winks. The library holds 120 face rows (`library_list {category: expression}`).
- How: Face tab; `library_use {id: face-…}` keys expression, gaze and ears together; `set_values {expression, gaze, mouth, blink}`.
- Fits: one clear face per story beat. Change the face on the beat, not mid-word.
- Also try: a held face as a thumbnail or carousel cover. A face swap on a freeze-frame label makes the punchline.
- Watch out: eyes and mouth never scale. Act with the face choice, gaze, head and body.

**Mouth sets.** 14 approved styles plus the built-in set.
- How: Library tab › Mouths; `set_stage {stage: {mouthSet}}`.
- Also try: switch mouth sets per character so voices feel different.

**Idle life.** Auto blink and auto ear twitch with natural, seeded timing. Keyed blinks always win.
- How: Face tab toggles; `set_idle {blink, twitch, blinkEvery, twitchEvery, seed, allShots}`.

**Eye darts.** Quick glances, with eye size constant.
- How: Post › Eye darts; `story2 action=eye_darts {every, seed}`.
- Also try: nervous lies, suspicion, a horror beat before the reveal.

### 3.4 Motion

**The motion library: 757 motions.**
- 408 Doodle Studio motions with face beats.
- 233 mocap clips (CMU and Mesh2Motion: walks, runs, everyday actions, sports, idles, dance, gestures).
- 37 performance moves made for Bunny: rapper, talker, singer, storyteller gestures (air quotes, counting, "anyway" wave, thumb over the shoulder, "this small"), and low- and high-angle staging.
- How: Library tab › Motions; `library_list {category: motion, query}`, then `library_use {id, frame, mirror, blend}`.
- Fits: start every shot from a motion and then adjust it. It's faster and cheaper than hand-keying.
- Also try: mocap walks with a different face per stretch. The performance moves work for any confident talker, not just rap.
- Watch out: clips with lots of arm movement were filtered out, because his head blocks raised arms. That's why walks dominate the mocap set.

**Clip blending.** `blend:N` crossfades into a clip over N frames from the animation already there. Mix clips on one shot this way.

**Animation layers.** Add layers with weights, and key into a layer without touching the base.
- How: `anim2 action=add_layer|layers|layer {index, on, weight, edit}`.
- Also try: a "Gestures" layer at 50% to calm a performance down.

**Gestures from the voice.** Head nods and body leans on a Gestures layer, driven by the voice. Never the jaw.
- How: Post › Gestures from the voice; `story2 action=gestures {strength}`.

**Cycles.** Check and make seamless loops.
- How: `anim_tool action=loop_check|make_loop`.

**Retarget.** Carries the whole scene to another character, inside its limits.
- How: `anim2 action=retarget {character}`.

**Reference video.** A video plane in the viewport only (never rendered), for acting reference or mocap-by-eye.
- How: Animate › Reference video…; `anim2 action=reference {path, offset, opacity}`.

### 3.5 Timing and polish tools

All of these act on the active shot:

| Tool | How |
|---|---|
| Breakdown slider (Tween Machine style): favour the previous or next pose, or overshoot | `anim_tool action=breakdown {amount, frame}` |
| Ease per key: ease, linear, in, out, hold | `set_ease` |
| Stepped blocking | `anim_tool action=stepped {on}` |
| Graph editor | `anim2 action=curves {on}` |
| Time warp: slow start, slow end, slow middle, fast middle | `anim2 action=time_warp` |
| Retime | `anim_tool action=retime {amount}` |
| Moving hold | `anim2 action=moving_hold` |
| Overlap down a chain | `anim_tool action=overlap {part, amount}` |
| Motion paths with popping-arc fixer | `anim2 action=path`, `anim2 action=fix_arcs` |
| Move, copy and paste keys across shots and characters | `anim2 action=move_keys|copy_keys|paste_keys` |
| Key simplify | `anim_tool action=simplify` |
| Euler filter | `anim2 action=euler_filter` |
| Onion skin | `anim_tool action=onion` |
| Mirror view (viewport only) | `anim_tool action=mirror_view` |
| Playblast with frame counter and audio | `anim_tool action=playblast` or `anim2 action=playblast` |
| Turntable | `anim_tool action=turntable` |

Typical flow: block in stepped, spline it, then breakdowns and overlap, then fix arcs, simplify, and playblast.

### 3.6 Camera

**Real lens.** Lens (mm), distance, yaw, pitch, roll, target, focus and f-stop (rack focus), all keyable.
- How: Camera panel; `set_values {"cam.lens": 24, …}`.
- Dolly zoom: Camera › Dolly zoom wide or long, keeping the size the same.

**One-click presets.** Pick a target (bunny, face, eyes, hands, feet, a registered prop, or `group` for Bunny plus every co-star) and frame it:
- 8 sizes: `ews ws fs mfs ms mcu cu ecu`
- 16 angles: eye, shoulder, hip, knee, ground, low, worm, high, overhead, dutch-l/r, tq-l/r, profile-l/r, back
- Views: `pov ots-l ots-r oth`
- Placement on the thirds: center, left, right
- 44 eased moves: push-in, pull-out, pans, whips, crane, arcs, orbit, vertigo, handheld, follow…
- How: Camera menu; `apply_camera_preset {target, size, angle, view, placement, move, seconds, frame}`; `{list:true}` returns every id.
- Fits: fast coverage. Wide to set the place, mid for talk, close for the punchline.
- With co-stars on stage, frame the wide with `target: group`. A preset that cuts a co-star off returns a warning, and the render blocks a co-star under 60% in frame (over-the-shoulder views are exempt).
- Watch out: from a medium shot inward, Bunny's head is wider than a 9:16 frame and crops slightly at the sides. Eyes stay in frame except in the extreme close-up.

**Look at camera.** Bunny keeps looking into the lens. His neck turns first; past its limit, his body re-plants with an eased turn and two small steps.
- How: `apply_camera_preset {lookAtCamera: true}`.
- Also try: talking to the viewer through an orbit. Break it on the beat he "notices" something.

**Saved angles and cuts (multi-cam).** Save angles, cut between them, or cut on "cam: B" markers.
- How: `features action=save_angle|angles|cut_to|cam_markers`.

**Beat-synced camera.** Punch, sway or cut on the music's beats.
- How: `features action=beat_cam {style, amount, angles}`. Needs scene audio.

**Floor-plan camera path.** Draw the path from above, and the camera travels it with easing.
- How: `features action=plan_path {points, from, to}`, `action=plan_info`.

**One horizon height across shots.** The horizon's height on screen depends on the camera's pitch. Eye-level presets (eye, the ¾ views, profiles, from behind, dutch) keep the camera level, so the horizon sits at the same height on every shot and size, and preflight passes. Shoulder, hip, knee, ground, low and high angles tilt on purpose, so use them for a beat, not as the default.

**Horizon lock and line weight per shot.**
- How: `set_shot_look {horizonLock, ink}`.

**Camera shake, fisheye, 360.**
- How: handheld and shake moves come from presets; `powers action=fisheye {amount}`; `powers action=pano360 {on, width}` makes equirectangular 360 video tagged for VR players.

**Previz.** Grey viewport and a grey clay render for fast blocking.
- How: `features action=previz|render_previz`.

### 3.7 Worlds

**Sets.** 83 sets at real scale to Bunny:
- 17 rooms
- 42 approved locations: open-sky meadow, hill, cliff, lake, highway, campsite, sea, clouds, space, dreamscape, farm, funfair, chai stall, ghat, balcony, salon…
- plus more

**Stage controls.**
- How: Library tab › Stage; `set_stage {stage: {set, setProps, time, sky, shadows, halftone, outfit, accessories, mouthSet}, shotOnly}`.
- Time of day: day, golden, night (lamps switch on).
- Sky: day, sunset, stars, storm. The storm sky darkens everything under it, so mustard reads brown. Check a still before committing to it on a bright, happy beat.
- `setProps {"rug": false}` hides pieces. Declutter by default.
- Fits: one set suggests the place. Few props, pushed back, with Bunny in front.
- Also try: `shotOnly:true` for a dream or flashback shot in a different set inside the same scene. Night plus storm makes instant horror without touching the animation.
- Watch out: the render check doesn't yet catch props that touch, crowd or tangent him, or that get cropped to slivers. Look at the stills.

**Scenery, scatter and crowds.**
- 390 scenery pieces: `library_use {id}`.
- Scatter grass, pebbles, flowers or leaves, never near the feet: `powers action=scatter`.
- Crowds that cheer and never touch the character: `powers action=crowd`.

**Weather and effects.** Rain, downpour, snow, leaves, petals, wind, speed lines, steam, smoke, sparkles, confetti, streamers, fireworks, dust, poof.
- How: `library_use {id: fx:…}`; liquids with `powers action=liquid` (splash, pour, puddle).

**Transitions and fly-throughs.** Dip or flash into a shot. Location changes ease from one place to the next.
- How: Blender › Transition into this shot…; `powers action=transition {kind, frames}`.

### 3.8 Props

**90 props modelled in 3D with real grips, plus 124 asset-pack pieces.** The packs include:
- reveal props that open
- explainer boards
- signs and placards with typed words
- 3D speech bubbles
- 12 reactions
- screens and frames that show your own clip

How it works:
- `library_use {id, hold: "L"|"R"}` puts a prop in the correct grip. It touches the hand at the grip point and can't be moved into an impossible hold.
- Placed pieces go anywhere you want to frame them.
- All text is editable: you type it.

**Physics props.** Jelly wobble (`powers action=jelly {item}`), toon liquids, cloth props, and props that physically fall.

**Reactions.** `library_use {id: react:heart|question|…}` pops a reaction over the head.

Watch out: 85 of 90 props are clean in hand. The cake, lantern, light bulb, skateboard and flask still graze a sleeve.

### 3.9 Wardrobe

**Outfits.** Raincoat, track jacket, zip hoodie (plus the default hoodie), all brand black with ochre detail strokes. **Accessories:** bow tie, square glasses, necktie.
- How: Library tab; `set_stage {stage: {outfit, accessories}}` or `library_use {id: outfit-…}`.
- Fits: weather (raincoat), a sporty bit (track jacket), a formal bit (bow tie, tie), a nerdy narrator (glasses).
- Also try: change the outfit with `shotOnly` for time skips ("three days later").
- Watch out: cloth only simulates in full renders. Previews skip it.

### 3.10 Drawing in 3D

- **Drawings layer (the Draw workspace, File › Import SVG drawing…, Post › Draw on the screen…):** import an SVG or draw by hand, and the lines sit on their own layer, apart from the characters, like the 2D studio's cutaways. Every line and shape outline becomes one ink line at Bunny's weight (fills, text and images are left out; convert text to outlines first). It draws on stroke by stroke over *Draws on over* frames from *Starts at frame*, boils like a hand-drawn line (*Noise*, a new wobble every *Boil every* frames), and can leave at *Gone at frame*. **On the screen** lays it over everything in the render; **In the 3D scene** stands it in the world at *Depth* metres behind the character, facing the camera, so the character can be in front of it. Ink or mustard only. `drawings action=import {svg | path, layer, x, y, size, frame, build, noise, colour}`, `draw {strokes}`, `set`, `place`, `remove`, `list`.
- **Ink doodles in 3D space:** strokes in frame fractions at a depth, drawn on over N frames. `powers action=doodle {strokes, depth, draw}`.
- **Auto-ink:** Line Art at Bunny's stroke weight on imported models. `powers action=autoink`.
- **Headlines as 3D lettering**, and **story pieces:** time skip, journey map, chat, label and arrow, end screen. `library_use {id: story:…, text}`.

### 3.11 Look and finish

- **Shot looks:** flashback and VHS (`post action=look`), plus the mood strip (`story2 action=mood`: calm, happy, tense, sad, scary, dreamy).
- **Genre moments:** horror, action, romance, comedy, sad, mystery, triumph, in ink and mustard only. `story2 action=genre`.
- **Paper finish** for paper grain (`powers action=paper`). **Cel or halftone shadows** are opt-in (`set_stage {shadows, halftone}`).

### 3.12 Sound

- **Scene audio:** voice or music for the whole scene, with a waveform and in every render. `audio action=import {path}` (wav, mp3, m4a, aac, ogg, flac).
- **Lip sync from the voice:** keys the mouth across a shot or every shot, one mouth per syllable. The vowel's formants pick the shape. At every syllable edge the lips close or narrow (MBP on a clear stop, teeth or F/V on hiss), and the mouth rests in silence. Over music it estimates the voice from the mix. For the cleanest read over a beat, hand it a separated vocal of the same song: `audio action=lipsync {all: true, stem: "C:/.../vocals.wav"}`. The stem is kept with the scene for later runs, and `stem: ""` clears it. `engine: "classic"` brings back the older loudness reader. `gate` sets the silence level and `hold` the shortest mouth in frames. On the Bambi rap track (17.6 s, mix only) it made 168 mouth changes with all 10 mouths, and no mouth was held longer than 13 frames. Run it again after you retime the shot, because it keys the shot as it is now.
- **Audio drives a control:** any control follows loudness. `audio action=drive {id, min, max}`.
- **Beat markers** from the audio: `workflow action=beats`.
- **Split the voice into sentences**, one shot per sentence: `workflow action=split_sentences {transcript}`.
- **Music bed** with ducking under the voice: `post action=music {path, volume, duck}`.
- **Auto foley:** whooshes and landings. `story2 action=foley`.
- **Markers drive sound:**
  - `bleep: 0.6` is a censor bleep.
  - `voice: chipmunk` (high, low, giant, robot) shifts the voice until `voice: normal`.
  - `quiet` before `scare` hushes the music.
- **Library sounds:** `sound:pop` and more, all CC0.

### 3.13 Words on screen

- **Captions** in EN and HI, word-by-word highlight (opt-in), SRT import and export.
  - How: `post action=caption|captions|caption_lang|highlight|srt_import|srt_export|clear_captions`.
- **Freeze-frame name labels** in ink text, with no box: `story2 action=freeze_label {text, frame, seconds}`.
- **Chapter cards** from "Chapter:" markers: `story2 action=chapter_cards`. **YouTube chapters file:** `story action=chapters`.

### 3.14 Story tools

| Tool | What it does | MCP |
|---|---|---|
| Script to blocking | Scene headings become shots, lines become markers, (actions) pick motions and faces | `features action=script {text, captions}` |
| Templates | storytime-reel, quick-take, music-reel, youtube-storytime, carousel | `workflow action=from_template` |
| Beat map | hook, setup, rising, turn, climax, payoff, cta | `story2 action=beat_map|add_beat` |
| Story bible | Premise, characters and rules, kept with the scene | `story action=bible` |
| Running gags | Markers noted "gag: …" | `story action=gags` |
| Hook and retention check | Weak first 2 s, any 4+ s with no visual change | `story action=retention` |
| Retention overlay | Your YouTube Studio CSV drawn on the timeline | `story2 action=retention {csv}` |
| Cold open | Flash forward, then a rewind card | `story2 action=cold_open` |
| Loop-back ending | The last frame matches the first, for Reels | `story action=loop_back` |
| Imagination bubble, photo cut-ins, narrator picture-in-picture | | `post action=bubble|photo|pip` |
| Jump scare timing | | `story2 action=jump_scare` |
| Sponsor segue | | `story2 action=sponsor` |
| Long video to Shorts | Each "short:" marker or chapter becomes its own 9:16 scene with its slice of the voice | `story2 action=shorts_plan|shorts` |

### 3.15 Shots, review, output

- **Scenes and shots:** add, duplicate, split, reorder, delete, status chips, auto codes. `add_shot`, `select_shot`, `move_shot`, `delete_shot`, `workflow action=split|status`.
- **Scene files:** `new_scene {name, character, width, height, fps}`, `open_scene {path}` and `save_as {name}` (saves to `DeepInDoodles\<name>\work\<name>.ds3d`). Files stay inside the renders folder.
- **Markers and review notes:** `add_marker {frame, note}`.
- **Storyboard sheet:** the first, middle and last frame of every shot. `storyboard`.
- **Snapshot carousels for Instagram:** snap frames, add bubbles, export numbered PNGs (4:5, 1:1, 9:16). `carousel`.
- **Render:**

| What | MCP | Output |
|---|---|---|
| One shot | `render` | `work\renders\<Scene>_<shot>_v###.mp4` |
| One frame | `render {still}` | a PNG |
| The whole scene, joined | `render_scene` | Unchanged shots are reused |
| Half-size preview without cloth | add `preview:true` to either | |
| Progress | `render_status` | |
| Presets (Reel, Short, YouTube 16:9, draft) | `production action=preset` | |
| Time estimate | `production action=estimate` | |
| Overnight batch (sleeps the PC when done) | `production action=batch` | |

- **Preflight, the export gate:** `production action=preflight` blocks a final export until all of these pass:
  - audio is imported
  - the lip sync is sampled: the mouth moves on loud frames, with more than a couple of different mouths
  - captions are short (1 to 3 words on one line, two lines at most), inside the Instagram safe zone and below the face
  - the horizon sits at one height across shots (within 4% of the frame)
- It also warns, without blocking, when hard cuts come faster than one every 2.5 s.

### 3.16 Safety and housekeeping

- **Autosave:** set the interval and number of copies with `set_autosave`. **Versions:** `save_version`. **Crash recovery** reopens at the same frame.
- **Undo history with labels:** `production action=history|undo_to`. **Claude change log** with per-change revert and a token meter: `production action=change_log|revert_change|meter`.
- **Health check with one-click fixes, pack project, cache cleanup:** `production action=health|fix|pack`.
- **Macros:** record a sequence and replay it from any frame. `powers action=macro_start`, `macro_stop {name}`, `macro_play {name, frame}`. Macros record app clicks and MCP calls alike, so an assistant can record a move once and replay it as one call.
- **Linked controls (drivers):** one control drives another. `powers action=link {from, to, factor, offset}`.
- **Master Bunny file:** your own Bunny .blend used by every render. `powers action=master`.

### 3.17 Babble voice (typed lines, cute gibberish)

Type what a character says and they "speak" it as cozy-game style gibberish. Every sound is made from scratch in the app (a pulse voice through three vowel filters plus breath), so nothing is sampled, and the same line always sounds the same. Bunny is high and bright, the Koala low, slow and breathy, the Frog croaky with a wobble.
- How: the Audio workspace (File › Babble voice opens it). Pick who speaks and a mood, type the line, press **Hear it**, then **Add at playhead**. MCP: `babble action=add {text, frame, who, mood}`, `babble action=voice {character, style, pitch, speed, range, breath, croak}`.
- What you get: one scene voice file (`work\audio\<Scene>_babble_<tag>.wav`) mixed over your recorded voice if there is one, mouth keys on every syllable for the speaker (lead or co-star), and timed captions that follow the caption rules.
- Styles: Syllables (one sound per syllable, most speech-like), Letters (a blip per letter, chattery), Chirps (pure beeps). Set per character; a line can override it.
- Punctuation acts: `?` lifts the end, `!` punches it, `.` drops it, commas pause.
- Watch out: a line longer than the rest of its shot keeps playing into the next shot, but the mouth keys stop at the shot's end (the toast says so). Importing or removing the recorded voice rebuilds the babble on top of it.

- Every character can be heard: pick Koala or Frog even if they are not in the shot, or press **Hear all voices**. A line given to a character who is not in the shot plays off screen, with no mouth keys. MCP: `who: "voice:frog"`.

### 3.17b Voice effects and the transcriber (Audio workspace)

- **Voice effects:** presets (Squeaky, Tiny, Deep, Giant, Robot, Radio, Phone call, Megaphone, Echo, Cave, Underwater, Alien) or your own pitch, effect and amount, over the whole scene voice. Your recording stays untouched and the timing does not change. MCP: `audio action=effect {preset, pitch, effect, mix, on, reset}`.
- **Transcribe:** Whisper runs on this PC, so nothing leaves it. The model downloads once, about 90 MB. It gives timed words, then **Make timed captions** or **Split into shots**. MCP: `audio action=transcribe {language}`, `transcript`, `captions`.

### 3.17c Timeline blocks and layers

Every character and drawing on a shot is a layer with blocks above the keys, as in the 2D studio. Drag a block to move it with its keys, drag an end to trim, use the scissors (or right-click) to cut. A gap hides the character there, in the render too. Each layer has an eye (show or hide, render too) and S to isolate it while you work (never in the render). A drawing's menu sets where it sits: Over all, In front, Through or Behind the characters. Babble lines are blocks too: drag one to retime it. MCP: `blocks`.

### 3.18 Materials (looks, colours, look add-ons)

The Materials tab (the last tab) dresses the shot in a material instead of the flat Ink & Mustard look. Blender draws it, so you see it in renders, in **Preview this frame** and in **Open in Blender**; the 3D view keeps its quick ink look.
- **Apply to:** Whole scene, Characters, Set, All props, or the Picked prop (click it in the 3D view first). The narrower choice wins: a picked prop beats All props, and Characters, Set and All props beat Whole scene. **For:** Every shot, or This shot only.
- **Looks** (picture cards): Ink & Mustard (flat, unlit), Clay, Cel toon, Soft vinyl toy, Felt, Plush (real fur strands on characters, face kept clear; fur length, density and messiness sliders), Paper cut-out, Glazed ceramic. Each has its own sliders (clay: roughness, thumb dents, dent size, colour wobble, soft glow; cel: bands, shadow depth, shadow hue, edge softness; and so on). Double-click a slider's name for its default.
- **Colours** (palette cards, each named for its colour-theory idea): Brand mustard, Sunbaked (analogous warm), Teal & coral (complementary), Playroom (triadic), Dusk (split-complementary), Sage (monochrome), Nursery (pastel), Midnight (analogous cool with a warm accent). Walls, floor and ceiling take their own colours; furniture and props take the palette's piece colours; rugs, lamps, clocks and cushions take the accent. Ink & Mustard with a palette repaints the flat look in those colours.
- **Brand guards, all switchable:** Keep Bunny mustard (on), outfits take the palette's ink (near-black), the body outline is off for textured looks and on for Ink & Mustard (the Ink outline button switches it; face lines always stay), and lit looks cast no shadows unless you turn on Cast shadows.
- **Light for lit looks** (every shot): key, fill, ambient, height, side and softness. Defaults: key 3.2, fill 0.3, ambient 0.5, height 28°, side 40°, softness 0.5, no shadows.
- **Look add-ons** (for example ClayDoh): drop the add-on's folder or .zip into the Doodle Library's `looks` folder, or install it in Blender. It shows up as cards; the first click renders one test frame of Bunny wearing it, and only a look that passes can be picked. If it is later missing on a PC, that target renders Ink & Mustard and the log says so. The recipe an add-on needs is in `blender/addons/doodle_looks/CONTRACT.md`.
- MCP: `materials action=list`, `materials action=apply {target, look, addon, params, palette, ink, keepCharacter, color, scope, item}`, `materials action=clear {target}`, `materials action=light {key, fill, ambient, height, angle, softness, shadows}`.

---

## 4. Cross-uses: made for one thing, great for another

This list is meant to grow. Add to it whenever a feature surprises you.

| Feature | Made for | Also great for |
|---|---|---|
| Camera shake | horror | landing a punchline; a heavy prop drop; bass hits in a music piece |
| Snapshot carousel | Instagram carousels | storyboards to pitch an idea; comic strips; thumbnail A/B sets |
| 360 turntable / 360 video | showing props | a character intro card; a sponsor product reveal; a VR "stand in Bunny's room" post |
| Audio drives a control | dance | ears twitching on bass; blinking on hi-hats; a lamp pulsing with music; a nervous jiggle on a loud voice |
| Linked controls | rig tidiness | ears that lag the head turn; a tail wag tied to happiness |
| Jelly props and squash | comedy impacts | "this is fine" wobble; an emotional sag; anything that should feel soft |
| Imagination bubble | daydreams | explaining a concept; a memory; a plan versus how it actually went; a lie being acted out |
| Reference video plane | mocap by eye | reacting to a real clip; matching timing to a meme |
| Crowds | audiences | a commute; a protest sign gag; a horde of identical Bunnies |
| Co-stars with mirrored copy | duets | inner voice; good and bad conscience; "me vs me" |
| Story-beat faces | acting | reaction stickers; thumbnails; carousel covers; emoji-style replies in comments |
| Look at camera | talking to the viewer | breaking the fourth wall mid-scene; a creepy stare in horror |
| Previz grey | blocking | a deliberate "behind the scenes" or "loading the simulation" gag |
| Flashback / VHS / paper finish | genre looks | genre switches inside one video; marking unreliable narration |
| Freeze-frame label | introducing people | fake stats ("confidence: 3%"); time stamps; ironic captions |
| Floor-plan camera path | fly-throughs | a "tour of my mess"; a chase; an orbit that reveals a second character |
| Mood strip | colour scripting | planning the emotional arc before animating anything |
| Hook / retention check | Reels | any edit, music or talk: it finds dead air fast |
| Pose from a stick figure | quick posing | letting the user sketch on the Kamvas and have Bunny copy it |
| Script to blocking | storytime | turning a tweet, a comment or a rant into a first cut in one call |
| Long video to Shorts | YouTube | trailers; teasers; a highlight per character |
| Halftone shadows | a print look | a "newspaper headline" moment; a retro comic flashback |
| Speech bubble assets | carousels | in-video thought bubbles; sign-language-style captions for silent bits |
| Koala nose controls | the Koala | sniffing out a secret; a running "smells suspicious" gag |
| Frog eye-bump pop | the Frog's ear twitch | surprise takes; comic double takes |

---

## 5. Recipes to remix

Each recipe ends with "push it further", which points at features the recipe didn't use. Swap in, mix and match.

**Storytime Reel (45–60 s, 9:16)**
1. Start from the voice, not the template. `new_scene`, then `audio import`, then `set_shot {length}` to the voice's length (seconds × fps), then `workflow split_sentences {shot: 0, transcript}`. That gives one shot per sentence, cut at the pauses. Read the shot labels against the audio, because a long sentence with no pause stays in one shot.
   - `from_template storytime-reel` is for when you have a structure but no voice yet: it lays out about 60 s of Hook, Setup, Build, Twist and Payoff shots. `split_sentences` only splits inside the shot you name, so on a template it leaves the other template shots as they were.
2. Per shot: a set (`set_stage`), a motion (`library_use`), one face per beat (`face-…` ids from `library_list {category: expression}`), and a camera preset. Use eye-level presets so the horizon stays put (see the horizon tip in 3.6).
3. `story retention`: fix weak openings and dead air. `story2 add_beat` for the beat map.
4. Captions (`post caption`, short and below the face), then `story2 foley`, then `post music {duck}`.
5. `production preflight`, then `render_scene`.
- Push it further: cold open, freeze-frame label, imagination bubble, loop-back ending.

**Music piece (rap or song)**
1. `audio import`, `workflow beats`, then `features beat_cam`.
2. Performance moves (rapper, singer) from the library, with a fresh pose on each beat. `anim2 time_warp` for swagger.
3. Real low and high angles (the set moves with the lens), whip pans and orbits from presets. Lyric captions with a few headline words.
- Push it further: crowd cheer on the drop, co-star hype-man with a mirrored copy, paper finish, 360 version.

**Two- or three-character skit**
1. The lead plus `cast add` co-stars. OTS presets for the dialogue, with Look at camera off.
2. Per-character mouth sets and outfits, and story-beat faces on reaction shots.
- Push it further: retarget the whole skit to swap who's the lead; a freeze-frame label per character.

**Explainer**
1. An explainer board or sign prop with typed text. Hand contact to point.
2. An imagination bubble for the concept, doodles in 3D for diagrams, chapter cards.
- Push it further: the Koala as the sceptic asking the viewer's question.

**Horror short (opt-in kit)**
1. Night plus storm sky, the scary mood, eye darts, `quiet` then `scare` markers, jump scare timing.
2. VHS look, a slow push-in, then a camera shake on the reveal.
- Push it further: Look at camera for a final stare, a loop-back so it replays.

**Carousel**
1. Pose key moments, then `carousel snap` each one, add bubbles, then `carousel export` (4:5).
- Push it further: a 360 turntable still as the cover; a story-beat face per slide.

**Long video to Shorts**
1. A youtube-storytime template, "Chapter:" markers, `story chapters`, `story2 chapter_cards`.
2. `story2 shorts_plan`, then `story2 shorts`. Each Short gets its own 9:16 scene and its slice of the voice.

---

## 6. For assistants: how to think, not what to make

1. **Start from the brief, then pick the form.** Reel, carousel, skit, explainer, music piece, still, 360. Don't default to the last format that worked.
2. **Reach across the studio.** Before you call a piece finished, list the feature families you used: character, acting, face, motion, camera, world, props, wardrobe, drawing, look, sound, words, story, output. Ask yourself which unused family would serve this story, and try one. Don't add features for their own sake. Declutter wins ties.
3. **Treat every feature as a verb, not a label.** The cross-uses in section 4 are examples of the habit, not the full list.
4. **Act the meaning, not the words.** Choose faces per story beat, gestures over mime, and strong readable poses. Run the silhouette check to confirm they read.
5. **Rules are not optional.**
   - Check rule lights at key frames, then preview, then full render.
   - Run preflight before any final.
   - Report the rule results with every render you show.
   - Keep files in `DeepInDoodles\<Name>\work\`.
   - Give the token report only after the user says "done".
6. **Be cheap.** Batch writes, use library motions, keep reads narrow, keep renders short, and don't screenshot the desktop. Never control the user's PC screen; everything goes through the MCP.
7. **Ask only about taste.** When you have options for the user, make a tickable pick page (Approve / Maybe / Reject, Push to build), never a plain list in chat. Decide everything else yourself and say what you chose.
8. **Leave things better.** Save useful poses to the pose library and useful motions to the library, and note new cross-uses in this guide.

---

## 7. Known limits and troubleshooting

As of build 20261030-195859. The live list is `doodle-studio/stress-3d/BUGS.md`.

- **Small held props come out small.** One-hand props are capped at his hand's length (a mug is about 14 cm), so at a side angle they can read as a round blob in his hand. Turn the prop or the camera until its shape reads, and check a still. On bent-arm frames a held prop can still touch his shirt by about 1 cm.
- **Raised arms clip the head** unless they also reach forward. The solver lowers them, and the user chose to keep the arms as they are. `anim2 ik` now warns when a pose puts the arm in the head.
- **From a medium shot inward, 9:16 crops the sides of his head.** The eyes stay in frame.
- **5 props graze a sleeve when held:** cake, lantern, light bulb, skateboard, flask.
- **Cloth is skipped in previews.** Check outfits in a full still.
- **Lip sync keys the shot as it is.** Retime or split a shot, then run `audio lipsync` again. Sample a few frames by eye: the engine reads the sound, not the words.
- **A missing library item is skipped.** If a stage names an outfit or accessory that isn't in the library, the render leaves it out and says so in `work\checks\<render>\blender.log`. `library_list` shows the real ids.
- **"Blender was not found":** set it under Render › Blender location, or run `production action=fix {fix: pick-blender}`.
- **Open in Blender: the button stays on "Blender opening…"** Blender is still building the shot (long shots take longer). If it never goes live, read `work\blender-live\<Scene>_<shot>\blender.log`.
- **"Needs a yes first":** the call would replace unsaved work. Ask the user, then repeat it with `force: true`.

---

## 8. Appendix: every MCP tool

These are the 48 tools on build 20261030-192645. Ask the app with `tools/list` for the full argument schemas.

`babble`, `blocks`, `get_state`, `list_controls`, `set_values`, `key`, `delete_key`, `set_ease`, `goto`, `get_guide`, `set_shot`, `add_shot`, `select_shot`, `move_shot`, `delete_shot`, `new_scene`, `open_scene`, `save_as`, `undo`, `redo`, `save`, `render`, `render_scene`, `render_status`, `apply_camera_preset`, `carousel`, `set_idle`, `set_character`, `library_list`, `library_use`, `remove_item`, `blender_live`, `set_stage`, `storyboard`, `mirror_pose`, `blend_poses`, `set_shot_look`, `materials`, `add_marker`, `save_version`, `set_autosave`, `anim_tool`, `anim2`, `audio`, `story`, `story2`, `post`, `cast`, `drawings`, `powers`, `features`, `production`, `workflow`.

### Control ids

| Group | Ids |
|---|---|
| Whole body | `bodyX bodyY depth s turn bodyRot breath legReach bodyTilt torsoBow torsoTwist squashBody` |
| Head | `headYaw headNod rot` |
| Ears | `earLFold earLForward earLScale earLSquash` (and R) |
| Koala nose | `noseWiggle noseSniff` |
| Arms | `armL armLForward elbowL wristL` (and R) |
| Legs | `legL legLOut kneeL footL` (and R) |
| Face | `expression gaze mouth blink` |
| Camera | `cam.yaw cam.pitch cam.dist cam.lens cam.roll cam.tx cam.ty cam.tz cam.focus cam.fstop` |

## Light, shadows and outlines

Stage › Set & light › Shadows turns light and shadow on for the whole scene, characters included. It is off by default: the doodle look is flat. The lighting presets (Classic, Soft, Dramatic, Rim, Overhead, Rembrandt, Loop, Butterfly, Split, Clamshell, High key, Low key, Silhouette, Under light, plus any you save) put a key, a fill and a back light round whoever is selected, or whatever you pick under Centre on, and they follow it as it moves. The sliders show live in the 3D view. Blender builds the same lights in the render, using the Tri-lighting add-on's TriLamp lights if it is installed. A plain background has no floor to catch a shadow.

Click anything in the Stage to get the Outline strip over the 3D view: 100% is Bunny's line, 40% thins it (the park's flowers read much better), 0 takes it off. It is saved with the scene and used in the render. Materials › Outlines: on / off does the same for a whole target in any look, and the colours stay. Face lines always stay.

A palette paints a model part by part: parts of the same shape share a colour and each shape takes the palette's next one, so a flower has its own stems, petals and centres. Materials › Colours › + Your palette makes your own: a colour picker for each role, pasted hex codes, or an imported file (.ase, .aco, .gpl, .pal, .hex, .txt, .json). Materials › Character colours sets Bunny and the outfit to a palette colour or any colour. Brand mustard and black stay the default.

## Speech bubbles

Library › Speech bubbles has 14 animated presets: Talk, Whisper, Think, Surprise and Shaky bubbles, Star burst, Letter slam, Boing, Zoom, Splat and Drift bursts, and Stepped, Name tab and Doodle dialogue boxes for subtitles. Every one pops in from small with an overshoot (Soft, Bouncy or Snap) and sizes to its text.

- Add one: drag a card onto the timeline or the Stage, or double-click it to add it at the playhead. Each bubble is its own layer with one block you can move, trim, cut, hide and isolate.
- Type: double-click the bubble on the Stage, or use the text box in the panel. Enter starts a new line. Esc or clicking away keeps it.
- Place: a speech bubble sits above its speaker and the tail stays on them from every side. Drag it anywhere round them. Pull the round handle to make it wider or narrower, and the words reflow.
- Time: set Seconds, or set Ends with to the Babble line or the voice. The Babble choice says the text as a Babble line, and moving the block moves the line. Speak it does the same.
- Stay off the face keeps it inside the Instagram safe zone and off the eyes and mouth. Turn it off to place a bubble exactly. Follow the character off keeps it where it is.
- Colours are mustard or ink, in Bunny's line weight, with no shadows. Bubbles show on the Stage and in the final render, not in Blender's live view.
- MCP: `bubbles` action=presets|list|add|set|match|remove|clear. `blocks` lists them as layers `b:<id>`.
