// Doodle Studio 3D's own MCP endpoint: http://127.0.0.1:54190/mcp (Streamable HTTP, JSON responses).
// Separate from the 2D Doodle Studio MCP; nothing here reads or writes the 2D app's config.
const VERSION = '2025-06-18';

const TOOLS = [
  ['get_state', 'Read the open shot: name, frame, length, fps, size, every current value and every key.', {}],
  ['list_controls', 'List every controllable value (Bunny pose, face, camera) with its id, label, group and min/max. Expression, gaze and mouth names are included.', {}],
  ['set_values', 'Set Bunny pose, face and camera values, e.g. {"armL":90,"headYaw":20,"cam.lens":24}. With frame, jumps there first. key=true sets keys at that frame (default follows the app\'s Auto keys switch). Values are clamped to Bunny\'s joint limits.',
    { values: { type: 'object', additionalProperties: { type: 'number' } }, frame: { type: 'integer', minimum: 0 }, key: { type: 'boolean' } }, ['values']],
  ['key', 'Set keys for the current values of these ids at a frame (default: the whole Bunny pose and face).', { ids: { type: 'array', items: { type: 'string' } }, frame: { type: 'integer', minimum: 0 } }],
  ['delete_key', 'Remove one key.', { id: { type: 'string' }, frame: { type: 'integer', minimum: 0 } }, ['id', 'frame']],
  ['set_ease', 'Easing from a key to the next: ease, linear, in, out or hold.', { id: { type: 'string' }, frame: { type: 'integer' }, ease: { enum: ['ease', 'linear', 'in', 'out', 'hold'] } }, ['id', 'frame', 'ease']],
  ['goto', 'Move the playhead.', { frame: { type: 'integer', minimum: 0 } }, ['frame']],
  ['set_shot', 'Change the shot name, length (frames), fps, width or height.', { name: { type: 'string' }, length: { type: 'integer', minimum: 1 }, fps: { type: 'integer', minimum: 12, maximum: 60 }, width: { type: 'integer' }, height: { type: 'integer' } }],
  ['undo', 'Undo the last change.', {}],
  ['redo', 'Redo.', {}],
  ['save', 'Save the shot (to its file, or to DeepInDoodles\\<name>\\work\\ if it has none yet).', {}],
  ['render', 'Render in Blender in the background: cloth, springs, collision, then the 3D rule checks. The MP4 goes to DeepInDoodles\\<name>\\work\\renders. still=frame renders one PNG; preview=true is half size without cloth.', { still: { type: 'integer', minimum: 0 }, preview: { type: 'boolean' } }],
  ['apply_camera_preset', 'One-click camera presets. Pick a target (bunny, face, eyes, hands, feet or a registered object) and frame it in a shot size (ews, ws, fs, mfs, ms, mcu, cu, ecu) and angle (eye, shoulder, hip, knee, ground, low, worm, high, overhead, dutch-l/r, tq-l/r, profile-l/r, back), or a view (pov, ots-l, ots-r, oth). move keys a camera move from frame (default the playhead) for seconds (push-in, pull-out, pan-l, whip-in-l, crane-up, arc-r, orbit, vertigo-in, handheld, follow...). list=true returns every id.',
    { list: { type: 'boolean' }, target: { type: 'string' }, size: { type: 'string' }, angle: { type: 'string' }, placement: { enum: ['center', 'left', 'right'] }, view: { type: 'string' }, move: { type: 'string' }, seconds: { type: 'number', minimum: 0.1 }, frame: { type: 'integer', minimum: 0 } }],
  ['render_status', 'Progress of the current render (frame, frames, minutes left, queue).', {}],
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
    apply_camera_preset: a => call(a.list ? 'ds3dCameraPresets.list()' : `ds3dCameraPresets.apply(${JSON.stringify(a)})`),
    render_status: () => api['render-status'](),
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
