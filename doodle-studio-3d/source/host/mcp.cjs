// Doodle Studio 3D's own MCP endpoint: http://127.0.0.1:54190/mcp (Streamable HTTP, JSON responses).
// Separate from the 2D Doodle Studio MCP; nothing here reads or writes the 2D app's config.
const VERSION = '2025-06-18';

const TOOLS = [
  ['get_state', 'Read the open scene and its active shot: scene name, the ordered shot list, frame, length, fps, size, every current value and every key of the active shot.', {}],
  ['list_controls', 'List every controllable value (Bunny pose, face, camera) with its id, label, group and min/max. Expression, gaze and mouth names are included.', {}],
  ['set_values', 'Set Bunny pose, face and camera values, e.g. {"armL":90,"headYaw":20,"cam.lens":24}. With frame, jumps there first. key=true sets keys at that frame (default follows the app\'s Auto keys switch). Values are clamped to Bunny\'s joint limits.',
    { values: { type: 'object', additionalProperties: { type: 'number' } }, frame: { type: 'integer', minimum: 0 }, key: { type: 'boolean' } }, ['values']],
  ['key', 'Set keys for the current values of these ids at a frame (default: the whole Bunny pose and face).', { ids: { type: 'array', items: { type: 'string' } }, frame: { type: 'integer', minimum: 0 } }],
  ['delete_key', 'Remove one key.', { id: { type: 'string' }, frame: { type: 'integer', minimum: 0 } }, ['id', 'frame']],
  ['set_ease', 'Easing from a key to the next: ease, linear, in, out or hold.', { id: { type: 'string' }, frame: { type: 'integer' }, ease: { enum: ['ease', 'linear', 'in', 'out', 'hold'] } }, ['id', 'frame', 'ease']],
  ['goto', 'Move the playhead.', { frame: { type: 'integer', minimum: 0 } }, ['frame']],
  ['set_shot', 'Change the active shot\'s name (label) or length (frames), or the scene name, fps, width or height.', { scene: { type: 'string' }, name: { type: 'string' }, length: { type: 'integer', minimum: 1 }, fps: { type: 'integer', minimum: 12, maximum: 60 }, width: { type: 'integer' }, height: { type: 'integer' } }],
  ['add_shot', 'Add a shot right after the active one (auto-coded sh010, sh020, ...) and make it active. duplicate=true copies the active shot; otherwise it starts holding the pose and camera the active shot ends on.', { duplicate: { type: 'boolean' } }],
  ['select_shot', 'Make a shot active for editing, by code (e.g. "sh020") or 0-based index.', { shot: { type: ['string', 'integer'] } }, ['shot']],
  ['move_shot', 'Reorder: move a shot (code or index) to a new 0-based position in the scene.', { shot: { type: ['string', 'integer'] }, to: { type: 'integer', minimum: 0 } }, ['shot', 'to']],
  ['delete_shot', 'Delete a shot (code or index). Undo brings it back.', { shot: { type: ['string', 'integer'] } }, ['shot']],
  ['undo', 'Undo the last change.', {}],
  ['redo', 'Redo.', {}],
  ['save', 'Save the shot (to its file, or to DeepInDoodles\\<name>\\work\\ if it has none yet).', {}],
  ['render', 'Render the active shot in Blender in the background: cloth, springs, collision, then the 3D rule checks. The MP4 goes to DeepInDoodles\\<scene>\\work\\renders as <Scene>_<shot>_v###.mp4; logs and rule reports to work\\checks. still=frame renders one PNG; preview=true is half size without cloth.', { still: { type: 'integer', minimum: 0 }, preview: { type: 'boolean' } }],
  ['render_scene', 'Render every shot of the scene in order and join them into one video, work\\renders\\<Scene>_v###.mp4. Shots unchanged since their last render are reused. preview=true is half size without cloth.', { preview: { type: 'boolean' } }],
  ['apply_camera_preset', 'One-click camera presets. Pick a target (bunny, face, eyes, hands, feet or a registered object) and frame it in a shot size (ews, ws, fs, mfs, ms, mcu, cu, ecu) and angle (eye, shoulder, hip, knee, ground, low, worm, high, overhead, dutch-l/r, tq-l/r, profile-l/r, back), or a view (pov, ots-l, ots-r, oth). move keys a camera move from frame (default the playhead) for seconds (push-in, pull-out, pan-l, whip-in-l, crane-up, arc-r, orbit, vertigo-in, handheld, follow...). list=true returns every id. lookAtCamera=true makes Bunny keep looking into the lens for the whole shot (neck first, then he re-plants his body); false turns it off.',
    { list: { type: 'boolean' }, lookAtCamera: { type: 'boolean' }, target: { type: 'string' }, size: { type: 'string' }, angle: { type: 'string' }, placement: { enum: ['center', 'left', 'right'] }, view: { type: 'string' }, move: { type: 'string' }, seconds: { type: 'number', minimum: 0.1 }, frame: { type: 'integer', minimum: 0 } }],
  ['carousel', 'Snapshot carousel for Instagram: list the slides, snap a frame as a new slide, edit slides and speech bubbles, or export. action=list | snap (shot code/index and frame; default the playhead) | size (size: 4:5, 1:1 or 9:16) | move (slide, to) | remove (slide) | bubble (slide, bubble: {text, assetId: speech|thought|shout|whisper, tail: down-left|down-right|left|right|none, x, y as 0-1 fractions; index to edit an existing one, delete:true to remove it}) | export (renders every slide in Blender and saves numbered PNGs with bubbles to DeepInDoodles\\<scene>\\work\\carousel).',
    { action: { enum: ['list', 'snap', 'size', 'move', 'remove', 'bubble', 'export'] }, shot: { type: ['string', 'integer'] }, frame: { type: 'integer', minimum: 0 }, size: { enum: ['4:5', '1:1', '9:16'] }, slide: { type: 'integer', minimum: 0 }, to: { type: 'integer', minimum: 0 }, bubble: { type: 'object' } }, ['action']],
  ['set_idle', 'Idle life for the active shot (or every shot with allShots=true): blink=true turns Auto blink on, twitch=true turns Auto ear twitch on (the Frog\'s eye bumps pop instead). blinkEvery / twitchEvery are the average seconds between them (each gap is randomised); seed fixes the timing so renders repeat. Keyed blinks and ear moves always win. Returns the settings and the frames where blinks and twitches land.',
    { blink: { type: 'boolean' }, twitch: { type: 'boolean' }, blinkEvery: { type: 'number', minimum: 1.5, maximum: 12 }, twitchEvery: { type: 'number', minimum: 2, maximum: 30 }, seed: { type: 'integer', minimum: 1, maximum: 9999 }, allShots: { type: 'boolean' } }],
  ['render_status', 'Progress of the current render (frame, frames, minutes left, queue).', {}],
  ['set_character', 'Put Bunny, the Koala or the Frog on stage for the whole scene. They share one rig, so every key, motion and camera move carries over; the Koala adds nose controls, and the Frog\'s ears are rigid eye bumps.', { character: { enum: ['bunny', 'koala', 'frog'] } }, ['character']],
  ['library_list', 'Search the Doodle Library on this PC and the built-in Blender pieces. category: motion (757 incl. mocap and performance), expression (faces and story beats), prop, scenery, set, outfit, accessory, effect, reaction, story, sound. Returns ids for library_use, plus mouthSets for set_stage. Without a query it lists the first matches of the category.',
    { category: { type: 'string' }, query: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 500 } }],
  ['library_use', 'Use a library item in the active shot (or shot=code) at frame (default the playhead). A motion becomes editable keys from that frame (mirror=true swaps left and right; the shot grows to fit). A face keys the expression, gaze and ears. A prop, scenery piece, effect (fx:rain), reaction (react:heart), storytime piece (story:time_skip with text, story:journey with text "Home, School") or sound (sound:pop) is placed in the shot and built in Blender at render time; hold="L" or "R" puts a prop in that hand. A set, outfit or accessory changes the stage (shotOnly=true for this shot only).',
    { id: { type: 'string' }, frame: { type: 'integer', minimum: 0 }, shot: { type: ['string', 'integer'] }, mirror: { type: 'boolean' }, hold: { enum: ['L', 'R', ''] }, text: { type: 'string' }, at: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 }, shotOnly: { type: 'boolean' } }, ['id']],
  ['set_stage', 'Set the stage the scene renders on: set (room id, e.g. "bedroom"), setProps ({"rug": false} to hide pieces of the set), time (day, golden, night), sky (day, sunset, stars, storm), shadows (cel shadows, off unless true), outfit (track, ziphoodie, raincoat; brand black), accessories (["bowtie", "squareglasses", "necktie"]), mouthSet (an id from library_list mouthSets). null clears a key. shotOnly=true sets it for the active shot only, on top of the scene. Returns the merged stage.',
    { stage: { type: 'object' }, shotOnly: { type: 'boolean' } }, ['stage']],
  ['storyboard', 'Save a storyboard sheet PNG: every shot\'s first, middle and last frame from the live viewport, with its code, name, length, start time, set and outfit, in DeepInDoodles\\<scene>\\work\\storyboard.', {}],
  ['mirror_pose', 'Swap left and right in the whole pose and face and key it at frame (default the playhead).', { frame: { type: 'integer', minimum: 0 } }],
  ['blend_poses', 'Key an in-between of two poses at frame: a and b are value maps like set_values takes (e.g. from get_state values); t is 0 (all a) to 100 (all b). Faces switch at 50.', { a: { type: 'object' }, b: { type: 'object' }, t: { type: 'number', minimum: 0, maximum: 100 }, frame: { type: 'integer', minimum: 0 } }, ['a', 'b', 't']],
  ['set_shot_look', 'Per-shot look: horizonLock=true keeps the horizon level (roll and Dutch presets ignored); ink is the line weight in percent of Doodle Studio\'s ink (100 = normal, 40-250), applied to every line in the shot so weights stay equal. Rack focus is the cam.focus and cam.fstop values (focus 0 = all sharp).', { horizonLock: { type: 'boolean' }, ink: { type: 'number', minimum: 40, maximum: 250 } }],
  ['add_marker', 'Add (or re-label) a timeline marker with a note in the active shot, e.g. a beat, a cut point or an acting note. Markers show on the timeline ruler and the storyboard.', { frame: { type: 'integer', minimum: 0 }, note: { type: 'string' } }, ['note']],
  ['save_version', 'Save a named copy of the scene in DeepInDoodles\\<scene>\\work\\versions (the open scene and its file are not changed).', { label: { type: 'string' } }, ['label']],
  ['set_autosave', 'Autosave interval in minutes (0 = off) and how many copies to keep per scene. Returns the settings.', { minutes: { type: 'number', minimum: 0, maximum: 60 }, keep: { type: 'integer', minimum: 1, maximum: 50 } }],
  ['anim_tool', 'Animator tools on the active shot. action: breakdown (amount 0-100 favours previous..next key, -25..125 overshoots; keys at frame), overlap (part: body, head, ears, armL, armR, legL, legR; amount = frames of lag per control down the chain), simplify (amount = tolerance in degrees, default 0.75; removes keys the curves do not need), loop_check, make_loop (keys the last frame to match the first), retime (amount = speed, 0.8 slower / 1.25 faster, keys after frame move), stepped (on: blocking, keys hold), onion (on: ghost poses of the previous and next key), silhouette (on: figure in solid ink to check readability), mirror_view (on: flips the viewport only), playblast (viewport video with a frame counter to work\\playblast), turntable (the camera circles once over the shot).',
    { action: { enum: ['breakdown', 'overlap', 'simplify', 'loop_check', 'make_loop', 'retime', 'stepped', 'onion', 'silhouette', 'mirror_view', 'playblast', 'turntable'] }, amount: { type: 'number' }, part: { type: 'string' }, frame: { type: 'integer', minimum: 0 }, on: { type: 'boolean' } }, ['action']],
  ['audio', 'Scene audio. action=import with path (a wav/mp3/m4a/aac/ogg/flac on this PC) sets the voice or music for the whole scene: it plays with the timeline, shows as a waveform and goes into scene renders; action=remove clears it; action=drive keys a control from the loudness over the active shot (id, min = value when quiet, max = value when loud, step frames between keys, default 2). Returns the audio info or the keys made.',
    { action: { enum: ['import', 'remove', 'drive'] }, path: { type: 'string' }, id: { type: 'string' }, min: { type: 'number' }, max: { type: 'number' }, step: { type: 'integer', minimum: 1, maximum: 12 } }, ['action']],
  ['story', 'Storytime helpers for the whole scene. action=retention: hook strength of the first 2 s and every 4+ s stretch with no visual change; chapters: writes YouTube chapters (0:00 Title lines) from markers whose note starts with "Chapter:" to work\\<scene>_chapters.txt; loop_back: keys the last frame of the last shot to the opening pose so a Reel replays seamlessly; gags: running gags from markers noted "gag: ..."; bible: read the story bible, or update it with bible {premise, characters, rules}.',
    { action: { enum: ['retention', 'chapters', 'loop_back', 'gags', 'bible'] }, bible: { type: 'object' } }, ['action']],
  ['remove_item', 'Remove a placed library item from the active shot by its index in get_state items.', { index: { type: 'integer', minimum: 0 } }, ['index']],
];

module.exports = ({ call, api }) => {
  const handlers = {
    get_state: () => call('ds3d.state()'),
    list_controls: async () => ({ controls: await call('ds3d.controls()'), ...(await call('ds3d.names()')) }),
    set_values: a => call(`ds3d.setValues(${JSON.stringify(a.values || {})}, ${a.frame ?? 'null'}, ${a.key ?? 'null'})`),
    key: a => call(`ds3d.key(${JSON.stringify(a.ids || null)}, ${a.frame ?? 'null'})`),
    delete_key: a => call(`ds3d.deleteKey(${JSON.stringify(a.id)}, ${Number(a.frame)})`),
    set_ease: a => call(`ds3d.setEase(${JSON.stringify(a.id)}, ${Number(a.frame)}, ${JSON.stringify(a.ease)})`),
    goto: a => call(`(ds3d.goto(${Number(a.frame)}), ds3d.state())`),
    set_shot: a => call(`ds3d.setShot(${JSON.stringify(a)})`),
    undo: () => call('(ds3d.undo(), ds3d.state())'),
    redo: () => call('(ds3d.redo(), ds3d.state())'),
    save: () => call('ds3d.save()'),
    render: a => call(`ds3d.render(${JSON.stringify(a || {})})`),
    render_scene: a => call(`ds3d.renderScene(${JSON.stringify(a || {})})`),
    add_shot: a => call(`ds3d.addShot(${!!a.duplicate})`),
    select_shot: a => call(`ds3d.selectShot(${JSON.stringify(a.shot)})`),
    move_shot: a => call(`ds3d.moveShot(${JSON.stringify(a.shot)}, ${Number(a.to)})`),
    delete_shot: a => call(`ds3d.deleteShot(${JSON.stringify(a.shot)})`),
    apply_camera_preset: a => call(a.list ? 'ds3dCameraPresets.list()' : `ds3dCameraPresets.apply(${JSON.stringify(a)})`),
    carousel: a => {
      const op = { list: 'ds3d.carousel()', snap: `ds3d.carouselSnap(${JSON.stringify(a.shot ?? null)}, ${a.frame ?? 'null'})`, export: '(ds3d.carouselExport(), ds3d.carousel())' }[a.action];
      if (op) return call(op);
      const edit = a.action === 'size' ? { size: a.size } : a.action === 'move' ? { slide: a.slide, to: a.to } : a.action === 'remove' ? { slide: a.slide, remove: true } : { slide: a.slide, bubble: a.bubble || {} };
      return call(`ds3d.carouselEdit(${JSON.stringify(edit)})`);
    },
    set_idle: a => call(`ds3d.setIdle(${JSON.stringify(a || {})})`),
    render_status: () => api['render-status'](),
    set_character: a => call(`ds3d.setCharacter(${JSON.stringify(a.character)})`),
    library_list: async a => {
      const r = await api.library();
      const extra = await call('ds3dLibraryExtra()');
      const words = String(a.query || '').toLowerCase().split(/\s+/).filter(Boolean);
      const rows = [...r.items, ...extra].filter(x => (!a.category || x.category === a.category) && words.every(w => (x.name + ' ' + (x.sub || '') + ' ' + (x.tags || []).join(' ') + ' ' + x.id).toLowerCase().includes(w)));
      return { found: r.found, dir: r.dir, total: rows.length, items: rows.slice(0, a.limit || 50).map(x => ({ id: x.id, name: x.name, category: x.category, sub: x.sub, frames: x.frames, loop: x.loop, description: x.description, ...(x.category === 'set' ? { room: x.data?.room, pieces: (x.data?.props || []).map(p => p.id) } : {}) })), mouthSets: r.mouthSets };
    },
    library_use: a => { const { id, ...opts } = a; return call(`ds3d.libraryUse(${JSON.stringify(id)}, ${JSON.stringify(opts)})`); },
    set_stage: a => call(`ds3d.setStage(${JSON.stringify(a.stage || {})}, ${!!a.shotOnly})`),
    storyboard: () => call('ds3d.storyboard()'),
    mirror_pose: a => call(`ds3d.mirrorPose(${a.frame ?? 'null'})`),
    blend_poses: a => call(`ds3d.blendPoses(${JSON.stringify(a.a)}, ${JSON.stringify(a.b)}, ${Number(a.t)}, ${a.frame ?? 'null'})`),
    set_shot_look: a => call(`ds3d.setShotLook(${JSON.stringify(a || {})})`),
    add_marker: a => call(`ds3d.addMarker(${a.frame ?? 'null'}, ${JSON.stringify(a.note || '')})`),
    save_version: a => call(`ds3d.saveVersion(${JSON.stringify(a.label)})`),
    set_autosave: a => call(`ds3d.autosave(${JSON.stringify(a || {})})`),
    anim_tool: a => call(`ds3d.animTool(${JSON.stringify(a || {})})`),
    audio: a => a.action === 'drive' ? call(`ds3d.audioDrive(${JSON.stringify(a.id)}, ${Number(a.min ?? 0)}, ${Number(a.max ?? 10)}, ${JSON.stringify({ step: a.step || 2 })})`)
      : call(`ds3d.importAudio(${a.action === 'remove' ? 'null' : JSON.stringify(a.path || '')})`),
    story: a => call(`ds3d.story(${JSON.stringify(a || {})})`),
    remove_item: a => call(`ds3d.removeItem(${Number(a.index)})`),
  };
  const tools = TOOLS.map(([name, description, props, required]) => ({ name, description, inputSchema: { type: 'object', properties: props, ...(required ? { required } : {}) } }));

  async function rpc(msg) {
    const { id, method, params } = msg;
    const ok = result => ({ jsonrpc: '2.0', id, result });
    try {
      if (method === 'initialize') return ok({ protocolVersion: params?.protocolVersion || VERSION, capabilities: { tools: {} }, serverInfo: { name: 'doodle-studio-3d', version: '1.0.0' },
        instructions: 'Doodle Studio 3D: pose Bunny in 3D, move a real camera, key it on a timeline and render in Blender. Track ids match the 2D Doodle Studio (armL, headYaw, ...); camera ids start with cam. Every final animation still needs the moderator gate before export.' });
      if (method === 'ping') return ok({});
      if (method === 'tools/list') return ok({ tools });
      if (method === 'tools/call') {
        const fn = handlers[params?.name];
        if (!fn) return { jsonrpc: '2.0', id, error: { code: -32602, message: 'Unknown tool ' + params?.name } };
        try {
          const out = await fn(params.arguments || {});
          return ok({ content: [{ type: 'text', text: JSON.stringify(out ?? { ok: true }) }] });
        } catch (e) { return ok({ isError: true, content: [{ type: 'text', text: String(e && e.message || e) }] }); }
      }
      if (id === undefined) return null;   // notifications
      return { jsonrpc: '2.0', id, error: { code: -32601, message: 'Method not found: ' + method } };
    } catch (e) { return { jsonrpc: '2.0', id, error: { code: -32603, message: String(e && e.message || e) } }; }
  }

  return async function handle(req, res, body) {
    if (req.method === 'GET') { res.writeHead(405, { allow: 'POST' }); return res.end(); }
    if (req.method === 'DELETE') { res.writeHead(200); return res.end(); }
    // only local callers; refuse browser pages from other origins
    const origin = req.headers.origin;
    if (origin && !/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(origin)) { res.writeHead(403); return res.end('Forbidden origin'); }
    let msg;
    try { msg = JSON.parse(body); } catch { res.writeHead(400); return res.end('Bad JSON'); }
    const out = Array.isArray(msg) ? (await Promise.all(msg.map(rpc))).filter(Boolean) : await rpc(msg);
    if (!out || (Array.isArray(out) && !out.length)) { res.writeHead(202); return res.end(); }
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(out));
  };
};
